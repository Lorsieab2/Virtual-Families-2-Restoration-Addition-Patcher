"""Scan every user-submitted translation file with VirusTotal before anything else looks at it.

    python -I scripts/virustotal_scan.py <work folder>

The owner's rule: "PLEASE RUN EVERY SINGLE USER-SUBMITTED FILE THROUGH VIRUSTOTAL AND REJECT
ANYTHING THAT IS FLAGGED." Run by .github/workflows/translations.yml after
scripts/translation_pr_files.py has fetched the files into <work folder> (manifest.json beside them).

For each file (already pre-checked: a UTF-8 "<code>.tsv" in translations/, at most 2 MB):
  1. look its SHA-256 up: GET https://www.virustotal.com/api/v3/files/{sha256};
  2. if VirusTotal does not know it, upload it (POST /api/v3/files) and poll
     GET /api/v3/analyses/{id} until the analysis completes, within an overall time limit;
  3. if ANY engine says "malicious" or "suspicious" the file is FLAGGED and the check fails,
     naming the engines.
If VirusTotal cannot be reached, times out, refuses the key, or there is no key, the file is
NOT SCANNED and the check fails too: nothing ever passes by default.

Requests are spaced to respect the free API's limit of 4 a minute (one every 15 seconds), and a
"429 Too Many Requests" reply waits a minute and tries again. Only www.virustotal.com is ever asked.
The key comes only from the VT_API_KEY environment variable (the repository secret); it is sent
only in the x-apikey header and never printed.

Writes <work>/scan.json, <work>/scan-comment.md and <work>/scan-result.txt ("clean", "flagged" or
"not scanned"), and "hashes=<sha256,...>" (the clean files) to $GITHUB_OUTPUT. Exit code 0 when
every file is clean, 1 otherwise, 2 when the work folder is unusable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HOST = "www.virustotal.com"
API = f"https://{HOST}/api/v3"
MIN_INTERVAL = 15.0           # seconds between requests: 4 a minute
QUOTA_WAIT = 60.0             # after a 429
MAX_QUOTA_RETRIES = 5
POLL_LIMIT = 15 * 60.0        # overall time for one file's upload and analysis
BAD = ("malicious", "suspicious")
MISSING_KEY = ("The VirusTotal key is missing: the repository secret VT_API_KEY is not set, so no file "
               "could be scanned. The owner adds it under Settings > Secrets and variables > Actions.")


class NotScanned(Exception):
    """VirusTotal could not give an answer (unreachable, timed out, key refused...)."""


@dataclass
class Result:
    path: str
    sha256: str
    status: str                                   # "clean", "flagged" or "not scanned"
    engines: list[str] = field(default_factory=list)
    detail: str = ""


class _HostOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NotScanned("VirusTotal redirected the request elsewhere")


def _urllib_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(_HostOnly())
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as reply:
            return reply.status, reply.read(8 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(64 * 1024) if exc.fp else b""


class VirusTotal:
    def __init__(self, key: str, transport=_urllib_transport, sleep=time.sleep, clock=time.monotonic,
                 min_interval: float = MIN_INTERVAL, quota_wait: float = QUOTA_WAIT, poll_limit: float = POLL_LIMIT):
        if not key:
            raise NotScanned(MISSING_KEY)
        self._key = key
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self.min_interval = min_interval
        self.quota_wait = quota_wait
        self.poll_limit = poll_limit
        self._last: float | None = None

    def _redact(self, text: str) -> str:
        return text.replace(self._key, "***") if self._key else text

    def _wait_turn(self) -> None:
        if self._last is not None:
            gap = self._clock() - self._last
            if gap < self.min_interval:
                self._sleep(self.min_interval - gap)
        self._last = self._clock()

    def request(self, method: str, path: str, body: bytes | None = None, content_type: str = "") -> tuple[int, dict]:
        url = API + path
        if urllib.parse.urlparse(url).hostname != HOST:
            raise NotScanned("only www.virustotal.com is ever asked")
        headers = {"x-apikey": self._key, "accept": "application/json", "User-Agent": "vf2-translation-scan"}
        if content_type:
            headers["content-type"] = content_type
        for _attempt in range(MAX_QUOTA_RETRIES + 1):
            self._wait_turn()
            try:
                status, raw = self._transport(method, url, headers, body, 60.0)
            except NotScanned:
                raise
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                raise NotScanned(self._redact(f"VirusTotal could not be reached ({type(exc).__name__})")) from None
            if status == 429:
                self._sleep(self.quota_wait)
                continue
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, ValueError):
                payload = {}
            return status, payload if isinstance(payload, dict) else {}
        raise NotScanned("VirusTotal's request limit was still reached after waiting")

    @staticmethod
    def _engines(results: dict) -> list[str]:
        found = []
        for name, verdict in sorted((results or {}).items()):
            verdict = verdict if isinstance(verdict, dict) else {}
            if verdict.get("category") in BAD:
                label = verdict.get("result") or verdict.get("category")
                found.append(f"{name} ({label})")
        return found

    def _verdict(self, path: str, digest: str, attributes: dict, results_key: str, stats_key: str) -> Result:
        engines = self._engines(attributes.get(results_key) or {})
        stats = attributes.get(stats_key) or {}
        bad_count = sum(int(stats.get(k) or 0) for k in BAD)
        if engines or bad_count:
            return Result(path, digest, "flagged", engines or [f"{bad_count} engine(s), not named by VirusTotal"])
        return Result(path, digest, "clean")

    def scan(self, path: str, data: bytes) -> Result:
        digest = hashlib.sha256(data).hexdigest()
        try:
            status, payload = self.request("GET", f"/files/{digest}")
            if status == 200:
                attributes = (payload.get("data") or {}).get("attributes") or {}
                if attributes.get("last_analysis_results") or attributes.get("last_analysis_stats"):
                    return self._verdict(path, digest, attributes, "last_analysis_results", "last_analysis_stats")
            elif status in (401, 403):
                raise NotScanned("VirusTotal refused the key (VT_API_KEY)")
            elif status != 404:
                raise NotScanned(f"VirusTotal answered {status} to the lookup")
            analysis = self._upload(path, data)
            return self._poll(path, digest, analysis)
        except NotScanned as why:
            return Result(path, digest, "not scanned", detail=self._redact(str(why)))

    def _upload(self, path: str, data: bytes) -> str:
        boundary = "vf2-" + uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"translation.tsv\"\r\n"
                "Content-Type: text/tab-separated-values\r\n\r\n").encode("ascii") + data + \
            f"\r\n--{boundary}--\r\n".encode("ascii")
        status, payload = self.request("POST", "/files", body, f"multipart/form-data; boundary={boundary}")
        if status in (401, 403):
            raise NotScanned("VirusTotal refused the key (VT_API_KEY)")
        analysis = str((payload.get("data") or {}).get("id") or "")
        if status != 200 or not analysis or not all(c.isalnum() or c in "-_=" for c in analysis):
            raise NotScanned(f"VirusTotal did not accept the upload (answer {status})")
        return analysis

    def _poll(self, path: str, digest: str, analysis: str) -> Result:
        deadline = self._clock() + self.poll_limit
        while True:
            status, payload = self.request("GET", f"/analyses/{urllib.parse.quote(analysis, safe='')}")
            if status != 200:
                raise NotScanned(f"VirusTotal answered {status} while analysing the file")
            attributes = (payload.get("data") or {}).get("attributes") or {}
            if attributes.get("status") == "completed":
                return self._verdict(path, digest, attributes, "results", "stats")
            if self._clock() >= deadline:
                raise NotScanned("VirusTotal did not finish analysing the file in time")


def comment(results: list[Result], refused: list[dict], key_missing: bool) -> str:
    bad = [r for r in results if r.status != "clean"] or refused or key_missing
    lines = ["### VirusTotal scan: " + ("FAILED" if bad else "clean"), ""]
    if key_missing:
        lines += [MISSING_KEY, ""]
    for item in refused:
        lines.append(f"- **{item.get('path', '?')}**: refused before scanning: {item.get('reason', '')}")
    for r in results:
        if r.status == "clean":
            lines.append(f"- **{r.path}**: clean (no engine reports it as malicious or suspicious)")
        elif r.status == "flagged":
            lines.append(f"- **{r.path}**: FLAGGED by " + ", ".join(r.engines) + ". It is rejected.")
        else:
            lines.append(f"- **{r.path}**: not scanned: {r.detail}. It cannot be accepted until it is scanned.")
    if not results and not refused and not key_missing:
        lines.append("No translation file to scan.")
    lines += ["", "Files shared here are sent to VirusTotal, where VirusTotal's partners can see them."]
    return "\n".join(lines) + "\n"


def run(work: Path, key: str, client_factory=VirusTotal) -> tuple[bool, list[Result]]:
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    refused = manifest.get("refused", [])
    results: list[Result] = []
    key_missing = not key and bool(files)
    client = None
    if files and key:
        client = client_factory(key)
    for item in files:
        data = (work / item["local"]).read_bytes()
        if client is None:
            results.append(Result(item["path"], hashlib.sha256(data).hexdigest(), "not scanned", detail=MISSING_KEY))
        else:
            results.append(client.scan(item["path"], data))
    clean = not refused and not key_missing and all(r.status == "clean" for r in results)
    state = "clean" if clean else ("flagged" if any(r.status == "flagged" for r in results) else "not scanned")
    if refused and not any(r.status == "flagged" for r in results):
        state = "refused"
    (work / "scan.json").write_text(json.dumps([r.__dict__ for r in results], indent=1), encoding="utf-8")
    (work / "scan-comment.md").write_text(comment(results, refused, key_missing), encoding="utf-8")
    (work / "scan-result.txt").write_text(state, encoding="utf-8")
    return clean, results


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    work = Path(argv[0])
    if not (work / "manifest.json").is_file():
        print("no manifest.json in the work folder")
        return 2
    key = os.environ.get("VT_API_KEY", "").strip()
    if not key:
        print("::error::" + MISSING_KEY)
    clean, results = run(work, key)
    for r in results:
        print(f"{r.path}: {r.status}" + (": " + ", ".join(r.engines) if r.engines else "")
              + (f": {r.detail}" if r.detail and r.detail != MISSING_KEY else ""))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("hashes=" + ",".join(r.sha256 for r in results if r.status == "clean") + "\n")
    print("clean" if clean else "FAILED: " + (work / "scan-result.txt").read_text(encoding="utf-8"))
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
