"""Collect the translation files a workflow run has to check, as DATA only.

    python -I scripts/translation_pr_files.py <event.json> <work folder>

Used by .github/workflows/translations.yml. Nothing fetched here is ever executed or checked out.

* pull_request_target: the pull request's changed files are listed through the GitHub REST API,
  and each changed file under translations/ is downloaded through the API at the pull request's
  head commit, at most 2 MB, into <work>/files/. Anything that is not a UTF-8 "<code>.tsv" directly
  in translations/ is refused before it is downloaded or scanned (validate_translation.pre_check).
  The repository's owner and collaborators may also edit translations/README.md and remove files.
* push / workflow_dispatch: the base branch's own checkout is trusted; the .tsv files the push
  changed (or, for a manual run, every .tsv in translations/) are copied from it.

Writes <work>/manifest.json: {"mode", "head_sha", "files": [{path, local, sha256, size}],
"refused": [{path, reason}], "skipped": [{path, reason}]}. Exit code 0, or 2 when the event is unusable.
The token comes from the GH_TOKEN environment variable and is only ever sent to api.github.com.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_translation as vt  # noqa: E402

API = "https://api.github.com"
ALLOWED_HOSTS = ("api.github.com",)
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Unusable(Exception):
    pass


class _NoForeignRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).hostname not in ALLOWED_HOSTS:
            raise Unusable("a GitHub API reply redirected outside api.github.com")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def api_get(url: str, token: str, accept: str = "application/vnd.github+json", limit: int | None = None) -> bytes:
    parts = urllib.parse.urlparse(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise Unusable("only api.github.com is ever asked")
    headers = {"Accept": accept, "User-Agent": "vf2-translation-check", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    opener = urllib.request.build_opener(_NoForeignRedirect())
    with opener.open(urllib.request.Request(url, headers=headers), timeout=60) as reply:
        return reply.read() if limit is None else reply.read(limit + 1)


def changed_pr_files(repo: str, number: int, token: str, get=api_get) -> list[dict]:
    files: list[dict] = []
    for page in range(1, 31):                    # the API lists at most 3000 files
        batch = json.loads(get(f"{API}/repos/{repo}/pulls/{number}/files?per_page=100&page={page}", token))
        files.extend(batch)
        if len(batch) < 100:
            break
    return files


def file_at(repo: str, path: str, sha: str, token: str, get=api_get) -> bytes:
    url = f"{API}/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={sha}"
    return get(url, token, accept="application/vnd.github.raw", limit=vt.MAX_BYTES)


def _store(work: Path, path: str, data: bytes, manifest: dict) -> None:
    folder = work / "files"
    folder.mkdir(parents=True, exist_ok=True)
    local = f"files/{len(manifest['files']):03d}.tsv"          # never the submitted name
    (work / local).write_bytes(data)
    manifest["files"].append({"path": path, "local": local, "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data)})


def collect_pr(event: dict, work: Path, token: str, get=api_get) -> dict:
    pr = event.get("pull_request") or {}
    number = int(pr.get("number") or 0)
    repo = str((event.get("repository") or {}).get("full_name") or "")
    head = pr.get("head") or {}
    sha = str(head.get("sha") or "")
    head_repo = str((head.get("repo") or {}).get("full_name") or repo)
    if number <= 0 or not REPO_RE.match(repo) or not SHA_RE.match(sha) or not REPO_RE.match(head_repo):
        raise Unusable("the event has no usable pull request")
    trusted = str(pr.get("author_association") or "") in TRUSTED
    manifest: dict = {"mode": "pr", "head_sha": sha, "files": [], "refused": [], "skipped": []}
    for item in changed_pr_files(repo, number, token, get):
        path = str(item.get("filename") or "")
        status = str(item.get("status") or "")
        old = str(item.get("previous_filename") or "")
        if not path.startswith(vt.FOLDER + "/") and not old.startswith(vt.FOLDER + "/"):
            continue
        if status == "removed" or (old.startswith(vt.FOLDER + "/") and not path.startswith(vt.FOLDER + "/")):
            if trusted:
                manifest["skipped"].append({"path": old or path, "reason": "removed by the owner"})
            else:
                manifest["refused"].append({"path": old or path, "reason": "only the owner removes translation files"})
            continue
        if path == vt.README and trusted:
            manifest["skipped"].append({"path": path, "reason": "the folder's guide, edited by the owner"})
            continue
        why = vt.pre_check(path, size=None)
        if why:
            manifest["refused"].append({"path": path, "reason": why})
            continue
        try:
            data = file_at(head_repo, path, sha, token, get)
        except (urllib.error.URLError, OSError, Unusable) as exc:
            manifest["refused"].append({"path": path, "reason": f"{path}: the file could not be fetched ({type(exc).__name__})"})
            continue
        why = vt.pre_check(path, data)
        if why:
            manifest["refused"].append({"path": path, "reason": why})
            continue
        _store(work, path, data, manifest)
    return manifest


def collect_branch(event: dict, work: Path, root: Path = ROOT) -> dict:
    """push / workflow_dispatch: files from the trusted checkout."""
    before = str(event.get("before") or "")
    after = str(event.get("after") or "")
    manifest: dict = {"mode": "branch", "head_sha": after, "files": [], "refused": [], "skipped": []}
    paths: list[str]
    if SHA_RE.match(before) and SHA_RE.match(after) and set(before) != {"0"}:
        out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=d", before, after, "--", vt.FOLDER],
                             cwd=root, capture_output=True, text=True, check=True).stdout
        paths = [p for p in out.splitlines() if p]
    else:
        paths = sorted(p.relative_to(root).as_posix() for p in (root / vt.FOLDER).glob("*") if p.is_file())
    for path in paths:
        if path == vt.README:
            continue
        data = (root / path).read_bytes()
        why = vt.pre_check(path, data)
        if why:
            manifest["refused"].append({"path": path, "reason": why})
            continue
        _store(work, path, data, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        event = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("the event file cannot be read")
        return 2
    work = Path(argv[1])
    work.mkdir(parents=True, exist_ok=True)
    try:
        if event.get("pull_request"):
            manifest = collect_pr(event, work, os.environ.get("GH_TOKEN", ""))
        else:
            manifest = collect_branch(event, work)
    except (Unusable, urllib.error.URLError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"cannot collect the files: {type(exc).__name__}: {exc}")
        return 2
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"{len(manifest['files'])} file(s) to check, {len(manifest['refused'])} refused, "
          f"{len(manifest['skipped'])} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
