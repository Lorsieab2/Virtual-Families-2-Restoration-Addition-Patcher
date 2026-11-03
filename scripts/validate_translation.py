"""Check a translation file shared to the public translations/ folder, as DATA only.

    python -I scripts/validate_translation.py <work folder>

Run by .github/workflows/translations.yml after scripts/translation_pr_files.py has fetched the
changed files into <work folder> (manifest.json beside them) and scripts/virustotal_scan.py has
scanned them. Nothing in a submitted file is ever executed: it is read as bytes and parsed as text
by src/vf2_translation_format.py, the base branch's own copy.

A file passes when
  * it is a UTF-8 "<language code>.tsv" directly in translations/, at most 2 MB (pre_check);
  * it is the very file VirusTotal scanned (its SHA-256 is in the SCANNED environment variable);
  * it reads as format 1 for Virtual Families 2, with no error on any line: keys, placeholders,
    gender and plural choices, escapes -- and no email address anywhere (the line is named);
  * its @code row matches its file name, it names its language, translates at least one line,
    and its credit name (@translator) is plain text with no email address.

Writes <work>/validate-comment.md (the report for the pull request) and <work>/validate-result.txt
("passed" or "refused"). Exit code 0 when every file passes, 1 when any is refused, 2 when the work
folder is unusable.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vf2_translation_format as tfmt  # noqa: E402

MAX_BYTES = 2 * 1024 * 1024
FOLDER = "translations"
README = "translations/README.md"
# "<code>.tsv", or "<code>-<credit slug>.tsv" when the language already has a file (the stem is
# matched against the file's own @code in check_file).
PATH_RE = re.compile(r"^translations/([A-Za-z]{2,3}(?:-[A-Za-z0-9]+)*)\.tsv$")
STEM_MAX = 80
CREDIT_MAX = 60
CREDIT_BAD = "<>[]`|\\"


def pre_check(path: str, data: bytes | None = None, size: int | None = None) -> str:
    """Why a changed file may not be in a translation pull request, or "" when it may.

    Only UTF-8 "<code>.tsv" files directly in translations/, at most 2 MB, are allowed: that
    rules out programs, archives, scripts and every other kind of file before anything else."""
    match = PATH_RE.match(path or "")
    if not match or len(match.group(1)) > STEM_MAX:
        return (f"{path}: only translation files named \"<language code>.tsv\" (for example fr.tsv) directly in "
                "the translations/ folder can be shared")
    size = len(data) if data is not None else size
    if size is not None and size > MAX_BYTES:
        return f"{path}: the file is larger than 2 MB; a translation is much smaller"
    if data is not None:
        if b"\x00" in data:
            return f"{path}: the file is not text (save it as UTF-8 text)"
        try:
            (data[3:] if data.startswith(b"\xef\xbb\xbf") else data).decode("utf-8")
        except UnicodeDecodeError as exc:
            return f"{path}: the file is not UTF-8 text (byte {exc.start} could not be read); save it as UTF-8"
    return ""


def credit_problem(name: str) -> str:
    name = tfmt.normalise_credit(name or "")
    if not name:
        return ""
    if tfmt.contains_email(name) or "@" in name or "＠" in name:
        return "the credit name (@translator) looks like an email address. " + tfmt.EMAIL_MESSAGE
    if len(name) > CREDIT_MAX or any(c in name for c in CREDIT_BAD):
        return f"the credit name (@translator) must be plain text of at most {CREDIT_MAX} letters"
    return ""


def name_problem(stem: str, code: str, credit: str) -> str:
    """Why "<stem>.tsv" is not a right name for a file whose @code is `code`, or ""."""
    code = code.strip()
    if not code or not tfmt.CODE_RE.match(code):
        return f"the @code row says {code or 'nothing'!r}, which is not a language code (fr, pt-BR...)"
    if stem.lower() == code.lower():
        return ""
    prefix = code.lower() + "-"
    rest = stem.lower()[len(prefix):] if stem.lower().startswith(prefix) else None
    slug = tfmt.credit_slug(credit)
    if rest is not None:
        if rest == slug:
            return ""
        numbered = re.fullmatch(r"(.+)(-[0-9]+)", rest)
        if numbered and numbered.group(1) == slug[:tfmt.SLUG_MAX - len(numbered.group(2))].rstrip("-"):
            return ""
    return (f"the file is named {stem}.tsv, but its @code row says {code!r}: name it {code}.tsv, or "
            f"{code}-{slug}.tsv when {code}.tsv already exists")


def credit_of(data: bytes) -> str:
    return tfmt.normalise_credit(tfmt.parse_bytes(data).translator)


def overwrite_problem(path: str, data: bytes, existing: bytes | None, names: set[str]) -> str:
    """Refuse replacing a file already in the folder that is credited to someone else."""
    if existing is None:
        return ""
    old = credit_of(existing)
    new = credit_of(data)
    if not old or old.casefold() == new.casefold():
        return ""
    parsed = tfmt.parse_bytes(data)
    code = parsed.value("@code").strip() or PATH_RE.match(path).group(1)
    try:
        suggestion = tfmt.shared_file_name(code, new, names)
    except ValueError:
        suggestion = f"<language code>-{tfmt.credit_slug(new)}.tsv"
    return (f"{path} already exists and is credited to someone else; it is never overwritten. Share your "
            f"translation as translations/{suggestion} (the <language code>-<credit name>.tsv form) instead.")


def check_file(path: str, data: bytes, existing: bytes | None = None,
               names: set[str] | None = None) -> tuple[bool, str]:
    """(passed, report) for one submitted file. `existing` is the base branch's file at the same path
    (None when it is new), `names` the file names already in the folder."""
    why = pre_check(path, data)
    if why:
        return False, why
    stem = PATH_RE.match(path).group(1)
    parsed = tfmt.parse_bytes(data, tfmt.GAME)
    report = tfmt.validate(parsed)
    problems: list[str] = []
    overwrite = overwrite_problem(path, data, existing, names or set())
    if overwrite:
        problems.append("File: error: " + overwrite)
    if parsed.fatal:
        problems.append("The file cannot be used: " + parsed.fatal)
    else:
        naming = name_problem(stem, parsed.value("@code"), parsed.translator)
        if naming:
            problems.append("File: error: " + naming)
        if not parsed.language.strip():
            problems.append("File: error: the @language row (the language's own name) is empty")
        credit = credit_problem(parsed.translator)
        if credit:
            problems.append("File: error: " + credit)
        if report.translated == 0:
            problems.append("File: error: no line is translated yet")
    problems.extend(str(p) for p in report.errors if str(p) not in problems)
    lines = [f"**{path}**: " + ("passed" if not problems else "refused")]
    lines.append("")
    lines.append("```")
    body = "\n".join(problems + ([""] if problems else []) + [report.summary()])
    lines.append(body.replace("```", "'''")[:20000])
    lines.append("```")
    return not problems, "\n".join(lines)


def run(work: Path, scanned: set[str], root: Path = ROOT) -> bool:
    """Check the manifest's files. For a pull request, `root` is the base branch's checkout: a file
    already there is what the submission would replace."""
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    folder = root / FOLDER
    names = {p.name for p in folder.glob("*.tsv")} if folder.is_dir() else set()
    pull_request = manifest.get("mode") == "pr"
    sections: list[str] = []
    passed = True
    for item in manifest.get("refused", []):
        passed = False
        sections.append(f"**{item.get('path', '?')}**: refused\n\n```\n{str(item.get('reason', ''))[:2000]}\n```")
    for item in manifest.get("files", []):
        path = str(item["path"])
        data = (work / item["local"]).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest not in scanned:
            passed = False
            sections.append(f"**{path}**: refused\n\n```\nThis is not the file VirusTotal scanned; nothing is "
                            "accepted unscanned.\n```")
            continue
        base = root / path
        existing = base.read_bytes() if pull_request and PATH_RE.match(path) and base.is_file() else None
        ok, text = check_file(path, data, existing, names)
        passed = passed and ok
        sections.append(text)
    if not sections:
        sections.append("No translation file to check.")
    head = ("### Translation check: passed\n\nEvery file reads as a Virtual Families 2 translation (format 1). "
            "The owner accepts it by merging, or with the `accept-translation` label."
            if passed else
            "### Translation check: refused\n\nPlease fix the lines named below and push again (or upload the "
            "fixed file to this pull request). " + tfmt.EMAIL_MESSAGE)
    (work / "validate-comment.md").write_text(head + "\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8")
    (work / "validate-result.txt").write_text("passed" if passed else "refused", encoding="utf-8")
    return passed


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    work = Path(argv[0])
    if not (work / "manifest.json").is_file():
        print("no manifest.json in the work folder")
        return 2
    scanned = {h for h in re.split(r"[,\s]+", os.environ.get("SCANNED", "")) if re.fullmatch(r"[0-9a-f]{64}", h)}
    passed = run(work, scanned)
    print("passed" if passed else "refused")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
