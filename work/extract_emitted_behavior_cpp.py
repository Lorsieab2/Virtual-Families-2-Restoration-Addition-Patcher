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


# The generator's own post-processing. `patch_spontaneous_behaviors` writes
# vf2_spontaneous_behaviors.cpp only AFTER substituting these placeholders, and
# two of them ARE the object prerequisites the contract test pins. Review
# found that reading the raw literal therefore asserts placeholder text while
# the build compiles resolved numbers -- the same "verify the shipped thing,
# not the source" rule this repository keeps relearning, applied to a test.
#
# The built file lives in the generator's scratch directory, which the matrix
# build owns and wipes, so it cannot be read while a build is running. These
# substitutions reproduce it from the constants instead, and
# `assert_substitutions_match_generator` keeps this table honest.
_SUBSTITUTIONS = (
    ("__VF2_EXERCISE_BIKE_OBJECT__", "MOBILE_EXERCISE_BIKE_OBJECT"),
    ("__VF2_EXERCISE_BIKE_DONOR_OBJECT__", "MOBILE_EXERCISE_BIKE_DONOR_OBJECT"),
    ("__VF2_PING_PONG_OBJECT__", "MOBILE_PING_PONG_OBJECT"),
    ("__VF2_PING_PONG_DONOR_OBJECT__", "MOBILE_PING_PONG_DONOR_OBJECT"),
)


def emitted_cpp(path=GENERATOR, resolve=True):
    """The emitted C++ containing the clone table.

    With `resolve` (the default) the object placeholders are substituted the
    way the generator substitutes them before writing the .cpp, so callers
    see the numbers the compiler will see. Pass resolve=False for the raw
    literal, which is only useful for checking the placeholders themselves.
    """
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
    body = text[body_start:end]
    if not resolve:
        return body

    import patch_mobile_furniture_pack as patcher
    for placeholder, constant in _SUBSTITUTIONS:
        body = body.replace(placeholder, "%#x" % getattr(patcher, constant))
    # Any object placeholder left unresolved means the generator gained a
    # substitution this module does not know about, so the test would again
    # be asserting text the build does not compile. Fail loudly instead.
    leftover = re.findall(r"__VF2_[A-Z0-9_]*OBJECT__", body)
    if leftover:
        raise RuntimeError(
            "unresolved object placeholders %s; add them to _SUBSTITUTIONS"
            % sorted(set(leftover)))
    return body


def assert_substitutions_match_generator(path=GENERATOR):
    """Fail if the generator substitutes an object placeholder we don't.

    Without this, a future placeholder added to the generator would leave
    this module resolving a stale subset while the contract test reported a
    pass. Returns the placeholder names checked.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("def patch_spontaneous_behaviors(manifest):")
    body = text[start:text.index("\ndef ", start + 10)]
    generator_placeholders = set(re.findall(
        r'helper_cpp\.replace\(\s*"(__VF2_[A-Z0-9_]*OBJECT__)"', body))
    known = {name for name, _ in _SUBSTITUTIONS}
    missing = generator_placeholders - known
    if missing:
        raise RuntimeError(
            "the generator substitutes %s but this module does not; the "
            "contract test would assert placeholder text while the build "
            "compiles resolved values" % sorted(missing))
    return sorted(generator_placeholders)


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
        # Preprocessing removes `#if 0` but NOT a false runtime guard, and not
        # a call sitting after an unconditional `return`. Review pointed out
        # that preprocessor survival is therefore still not execution: the
        # optimizer would emit nothing and the autonomous action would vanish
        # while this function happily counted twelve argument lists.
        #
        # So reject a call whose immediately-preceding context makes it
        # unreachable. This is deliberately conservative -- it recognises the
        # shapes that would actually be used to disable a call, rather than
        # attempting real control-flow analysis.
        before = text[max(0, match.start() - 400):match.start()]
        tail = before[before.rfind("\n} else") + 1:] if "\n} else" in before \
            else before
        if re.search(r"if\s*\(\s*(?:false|0)\s*\)\s*$", tail.rstrip()):
            continue
        if re.search(r"\breturn\s*;\s*$", tail.rstrip()):
            continue
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
