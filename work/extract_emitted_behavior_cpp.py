# -*- coding: utf-8 -*-
"""Extract the emitted C++ that contains the autonomous-candidate clone table,
and optionally run it through the real MSVC preprocessor.

WHY THIS EXISTS

The contract tests used to assert against the generator's own Python source
text. Review showed twice that text presence is not execution:

  1. a call prefixed with `//` still satisfied every `assertIn`
  2. a call wrapped in `#if 0` still satisfied every assertion, including the
     comment-stripped ones, because the preprocessor -- not the text -- is
     what removes it

Stripping comments fixed (1) but cannot fix (2): no amount of regex tells you
whether a statement survives preprocessing. Only a preprocessor does.

So this module pulls the emitted C++ out of the generator's raw string literal
and hands it to `cl /EP /P`, whose output contains exactly the statements the
compiler would actually see. A test can then assert against *reachable* code.

If MSVC is unavailable the caller gets `None` for the preprocessed text and
must say so rather than silently falling back to the weaker text check -- a
skipped check that reports as a pass is the failure mode this whole line of
review has been about.
"""
import glob
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.join(_HERE, "patch_mobile_furniture_pack.py")

# A statement that only appears in the block we want, so the correct literal
# is located by content rather than by a line number that drifts.
ANCHOR = "CloneAutonomousCandidateWithWeight(data, 0x034"


def emitted_cpp(path=GENERATOR):
    """The raw C++ string literal containing the clone table."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    index = text.index(ANCHOR)
    start = text.rfind("r'''", 0, index)
    if start < 0:
        raise RuntimeError("clone table is not inside an r''' literal")
    body_start = start + len("r'''")
    end = text.index("'''", body_start)
    if end < index:
        raise RuntimeError("literal ends before the clone table")
    return text[body_start:end]


def find_cl():
    """The x86 MSVC compiler driver, or None."""
    pattern = os.path.join(
        "C:\\", "Program Files", "Microsoft Visual Studio", "*", "*", "VC",
        "Tools", "MSVC", "*", "bin", "Hostx64", "x86", "cl.exe")
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


def preprocessed_cpp(source=None):
    """`source` after the real C preprocessor, or None if cl.exe is absent.

    Uses /EP /P so the output is pure preprocessed text with no #line noise.
    The emitted block is not a standalone translation unit -- it references
    game types declared elsewhere -- but preprocessing does not need them:
    it only resolves directives, which is precisely the question.
    """
    compiler = find_cl()
    if compiler is None:
        return None
    if source is None:
        source = emitted_cpp()
    work = tempfile.mkdtemp(prefix="vf2pp_")
    try:
        src = os.path.join(work, "emitted.cpp")
        with open(src, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source)
        out = os.path.join(work, "emitted.i")
        result = subprocess.run(
            [compiler, "/nologo", "/EP", "/P", "/Fi" + out, src],
            cwd=work, capture_output=True, text=True)
        if not os.path.exists(out):
            raise RuntimeError(
                "preprocessing produced no output: %s%s"
                % (result.stdout[-400:], result.stderr[-400:]))
        with open(out, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    finally:
        for name in os.listdir(work):
            try:
                os.remove(os.path.join(work, name))
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass


def clone_calls(text):
    """Every CloneAutonomousCandidateWithWeight invocation in `text`.

    Matches on the HELPER NAME and parses the argument list, rather than
    requiring the first argument to be spelled `data`. Review found that
    anchoring on `data,` let a live call with a cast first argument slip past
    the completeness count entirely.
    """
    found = []
    for match in re.finditer(
            r"CloneAutonomousCandidateWithWeight\s*\(([^;]*?)\)\s*;", text,
            re.DOTALL):
        args = split_args(match.group(1))
        found.append(tuple(arg.strip() for arg in args))
    return found


def split_args(text):
    """Split an argument list on top-level commas only."""
    args, depth, current = [], 0, []
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        args.append("".join(current))
    return args


def main():
    source = emitted_cpp()
    print("emitted C++ block: %d chars" % len(source))
    raw = clone_calls(source)
    print("clone calls in emitted text: %d" % len(raw))

    text = preprocessed_cpp(source)
    if text is None:
        print("cl.exe not found; preprocessed check UNAVAILABLE")
        return 2
    live = clone_calls(text)
    print("clone calls after preprocessing: %d" % len(live))
    print()
    for args in live:
        print("  (%s)" % ", ".join(args))
    if len(live) != len(raw):
        print()
        print("%d call(s) are present in the text but removed by the "
              "preprocessor" % (len(raw) - len(live)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
