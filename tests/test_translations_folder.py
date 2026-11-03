#!/usr/bin/env python3
"""The public translations/ folder: its guide (translations/README.md), the format validator
(scripts/validate_translation.py, src/vf2_translation_format.py), the VirusTotal scan
(scripts/virustotal_scan.py, with VirusTotal mocked), the file collector
(scripts/translation_pr_files.py, with the GitHub API mocked) and the workflow that runs them
(.github/workflows/translations.yml)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vf2_translation_format as tf  # noqa: E402
import validate_translation as vt  # noqa: E402
import virustotal_scan as vs  # noqa: E402
import translation_pr_files as tp  # noqa: E402

try:
    import yaml
except ImportError:            # CI installs only pytest; the text checks below still run
    yaml = None

WORKFLOW = ROOT / ".github" / "workflows" / "translations.yml"
README = ROOT / "translations" / "README.md"

ENTRIES = [
    tf.Entry(tf.make_key("ui", "menu.play", "Play"), "Play"),
    tf.Entry(tf.make_key("exe", "0x1000", "%s has %d children."), "%s has %d children.",
             "%1 = person's name (person), %2 = number"),
    tf.Entry(tf.make_key("ui", "house.welcome", "Welcome to {house}"), "Welcome to {house}"),
]
GOOD = ("Jouer", "%s a %d {%2: one=enfant | other=enfants}. {%1: m=Il | f=Elle | o=Iel} est content.",
        "Bienvenue à {house}")


def make(translations=GOOD, code="fr", language="Français", translator="Marie") -> bytes:
    f = tf.new_file(tf.GAME, ENTRIES, language, code, translator)
    for row, text in zip(f.rows, translations):
        row.translation = text
    return tf.to_bytes(f)


def line_of(data: bytes, needle: str) -> int:
    text = data.decode("utf-8-sig").replace("\r\n", "\n")
    return next(n for n, line in enumerate(text.split("\n"), 1) if needle in line)


# ------------------------------------------------------------------------------------------ the format
class FormatTests(unittest.TestCase):
    def test_good_file_round_trips_with_bom(self):
        data = make()
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        parsed = tf.parse_bytes(data, tf.GAME)
        self.assertEqual(parsed.errors, [])
        self.assertEqual(parsed.game, "Virtual Families 2")
        self.assertEqual(tf.to_bytes(parsed), data)
        self.assertEqual(tf.file_name("pt-BR"), "pt-BR.tsv")
        with self.assertRaises(ValueError):
            tf.file_name("../x")

    def test_selects_choose_by_person_and_number(self):
        text = GOOD[1]
        self.assertEqual(tf.evaluate(text, "fr", {"%2": 1}, {"%1": "f"}), "%s a %d enfant. Elle est content.")
        self.assertEqual(tf.evaluate(text, "fr", {"%2": 3}, {"%1": "m"}), "%s a %d enfants. Il est content.")


# ------------------------------------------------------------------------------------------ the validator
class ValidatorTests(unittest.TestCase):
    def check(self, data: bytes, path="translations/fr.tsv"):
        return vt.check_file(path, data)

    def test_good_file_passes(self):
        ok, report = self.check(make())
        self.assertTrue(ok, report)
        self.assertIn("passed", report)

    def test_placeholder_mismatch_is_refused_with_its_line(self):
        data = make(("Jouer", "%d enfants de %s", ""))
        ok, report = self.check(data)
        self.assertFalse(ok)
        self.assertIn(f"Line {line_of(data, '%d enfants de %s')}: error: the placeholders must be the same", report)

    def test_missing_variable_is_refused(self):
        ok, report = self.check(make(("Jouer", "", "Bienvenue")))
        self.assertFalse(ok)
        self.assertIn("missing {house}", report)

    def test_bad_select_is_refused(self):
        for bad, why in (("{%1: m=Il | x=Elle} %s %d", "unknown key"),
                         ("%s %d {%2: m=Il | f=Elle}", "is a number"),
                         ("%s %d {%1: one=a | other=b}", "is a person"),
                         ("%s %d {%2: one=a | other=b", "no closing")):
            with self.subTest(bad=bad):
                ok, report = self.check(make(("Jouer", bad, "")))
                self.assertFalse(ok)
                self.assertIn(why, report)

    def test_edited_english_or_bad_key_is_refused(self):
        data = make().replace(b"\tPlay\t", b"\tPlay!\t")
        ok, report = self.check(data)
        self.assertFalse(ok)
        self.assertIn("does not match the key", report)
        data = make().replace(b"ui/menu.play~", b"UI/menu.play~")
        ok, report = self.check(data)
        self.assertFalse(ok)
        self.assertIn("is not a valid key", report)

    def test_email_anywhere_is_refused_naming_the_line(self):
        for email in ("someone@example.com", "someone＠example.com", "someone [at] example [dot] com",
                      "someone at example dot com"):
            with self.subTest(email=email):
                data = make(("Jouer", "", "Bienvenue à {house} " + email))
                ok, report = self.check(data)
                self.assertFalse(ok)
                self.assertIn(f"Line {line_of(data, 'Bienvenue')}: error: this line has an email address", report)
                self.assertIn(tf.EMAIL_MESSAGE, report)

    def test_email_in_the_credit_is_refused(self):
        data = make(translator="marie@example.com")
        ok, report = self.check(data)
        self.assertFalse(ok)
        self.assertIn(f"Line {line_of(data, '@translator')}: error: this line has an email address", report)
        ok, report = self.check(make(translator="marie@home"))
        self.assertFalse(ok)
        self.assertIn("looks like an email address", report)
        self.assertTrue(self.check(make(translator=""))[0])
        self.assertFalse(self.check(make(translator="x" * 61))[0])

    def test_code_must_match_the_file_name(self):
        ok, report = self.check(make(code="de"))
        self.assertFalse(ok)
        self.assertIn("named fr.tsv", report)
        self.assertTrue(self.check(make(code="pt-BR"), "translations/pt-BR.tsv")[0])

    def test_wrong_game_or_nothing_translated_is_refused(self):
        data = make().replace(b"\tVirtual Families 2\t", b"\tVirtual Villagers\t")
        self.assertFalse(self.check(data)[0])
        ok, report = self.check(make(("", "", "")))
        self.assertFalse(ok)
        self.assertIn("no line is translated", report)

    def test_pre_check_allows_only_small_utf8_tsv_in_the_folder(self):
        for path in ("translations/fr.txt", "translations/fr.tsv.exe", "translations/sub/fr.tsv", "fr.tsv",
                     "translations/../fr.tsv", "translations/run.py", "translations/fr.zip", "translations/x1.tsv"):
            with self.subTest(path=path):
                self.assertTrue(vt.pre_check(path, b"Key\tEnglish\tTranslation\n"))
        self.assertEqual(vt.pre_check("translations/fr.tsv", make()), "")
        self.assertIn("2 MB", vt.pre_check("translations/fr.tsv", b"a" * (vt.MAX_BYTES + 1)))
        self.assertIn("not UTF-8", vt.pre_check("translations/fr.tsv", b"Key\tCaf\xe9\n"))
        self.assertIn("not text", vt.pre_check("translations/fr.tsv", "Key".encode("utf-16-le")))
        self.assertIn("not text", vt.pre_check("translations/fr.tsv", b"MZ\x90\x00\x03"))

    def test_run_checks_only_the_scanned_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "files").mkdir()
            data = make()
            (work / "files" / "000.tsv").write_bytes(data)
            (work / "manifest.json").write_text(json.dumps({"files": [
                {"path": "translations/fr.tsv", "local": "files/000.tsv"}], "refused": []}), encoding="utf-8")
            self.assertFalse(vt.run(work, set()))
            self.assertIn("not the file VirusTotal scanned", (work / "validate-comment.md").read_text(encoding="utf-8"))
            self.assertTrue(vt.run(work, {hashlib.sha256(data).hexdigest()}))
            self.assertEqual((work / "validate-result.txt").read_text(encoding="utf-8"), "passed")


# ------------------------------------------------------------------------------------------ names, overwrites
class NamingTests(unittest.TestCase):
    def test_credit_slug(self):
        self.assertEqual(tf.credit_slug("Marie (Lyon)"), "marie-lyon")
        self.assertEqual(tf.credit_slug("Zoë  Ångström"), "zoe-angstrom")
        self.assertEqual(tf.credit_slug("日本語"), "anonymous")
        self.assertEqual(tf.credit_slug(""), "anonymous")
        long = tf.credit_slug("A very long credit name that goes on and on and on")
        self.assertLessEqual(len(long), 40)
        self.assertRegex(long, r"^[a-z0-9-]+$")
        self.assertFalse(long.endswith("-"))

    def test_shared_file_name_never_takes_an_existing_name(self):
        self.assertEqual(tf.shared_file_name("fr", "Marie", set()), "fr.tsv")
        self.assertEqual(tf.shared_file_name("fr", "Marie", {"fr.tsv"}), "fr-marie.tsv")
        self.assertEqual(tf.shared_file_name("fr", "Marie", {"fr.tsv", "fr-marie.tsv"}), "fr-marie-2.tsv")
        self.assertEqual(tf.shared_file_name("fr", "Marie", {"FR.tsv", "fr-marie.tsv", "fr-marie-2.tsv"}),
                         "fr-marie-3.tsv")
        name = tf.shared_file_name("fr", "x" * 60, {"fr.tsv", "fr-" + "x" * 40 + ".tsv"})
        self.assertEqual(name, "fr-" + "x" * 38 + "-2.tsv")
        self.assertLessEqual(len(name[3:-4]), 40)

    def test_slug_names_pass_and_wrong_names_are_refused(self):
        self.assertTrue(vt.check_file("translations/fr-marie.tsv", make())[0])
        self.assertTrue(vt.check_file("translations/fr-marie-2.tsv", make())[0])
        self.assertTrue(vt.check_file("translations/fr-marie-lyon.tsv", make(translator="Marie (Lyon)"))[0])
        ok, report = vt.check_file("translations/fr-paul.tsv", make())
        self.assertFalse(ok)
        self.assertIn("fr-marie.tsv", report)
        self.assertFalse(vt.check_file("translations/de-marie.tsv", make())[0])

    def test_overwriting_someone_elses_file_is_refused(self):
        theirs = make(translator="Paul")
        mine = make(translator="Marie")
        ok, report = vt.check_file("translations/fr.tsv", mine, existing=theirs, names={"fr.tsv"})
        self.assertFalse(ok)
        self.assertIn("credited to someone else", report)
        self.assertIn("translations/fr-marie.tsv", report)
        # the same translator improving their own file, or a file with no credit, is fine
        self.assertTrue(vt.check_file("translations/fr.tsv", mine, existing=make(translator="marie"),
                                      names={"fr.tsv"})[0])
        self.assertTrue(vt.check_file("translations/fr.tsv", mine, existing=make(translator=""), names={"fr.tsv"})[0])

    def test_run_compares_with_the_base_branch_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base"
            (base / "translations").mkdir(parents=True)
            (base / "translations" / "fr.tsv").write_bytes(make(translator="Paul"))
            work = Path(tmp) / "work"
            (work / "files").mkdir(parents=True)
            data = make(translator="Marie")
            (work / "files" / "000.tsv").write_bytes(data)
            scanned = {hashlib.sha256(data).hexdigest()}
            for mode, expected in (("pr", False), ("branch", True)):
                (work / "manifest.json").write_text(json.dumps({"mode": mode, "files": [
                    {"path": "translations/fr.tsv", "local": "files/000.tsv"}], "refused": []}), encoding="utf-8")
                with self.subTest(mode=mode):
                    self.assertIs(vt.run(work, scanned, base), expected)
            (work / "manifest.json").write_text(json.dumps({"mode": "pr", "files": [
                {"path": "translations/fr.tsv", "local": "files/000.tsv"}], "refused": []}), encoding="utf-8")
            self.assertFalse(vt.run(work, scanned, base))
            self.assertIn("translations/fr-marie.tsv", (work / "validate-comment.md").read_text(encoding="utf-8"))

    def test_test_files_are_marked(self):
        self.assertTrue(tf.is_test_file(tf.parse_bytes(make(translator="(TEST) Marie"))))
        self.assertTrue(tf.is_test_file(tf.parse_bytes(make(language="(test) Français"))))
        self.assertFalse(tf.is_test_file(tf.parse_bytes(make())))

    def test_no_test_translation_is_packaged_into_a_release(self):
        try:
            sys.path.insert(0, str(ROOT / "work"))
            import export_offline_patch_bundle as exporter
        except Exception as exc:    # the exporter's own imports are the release tests' business
            self.skipTest(f"release exporter not importable here: {exc}")
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "VF2-B999-Release"
            bundle.mkdir()
            written = exporter.write_bundle_runner_files(bundle, "B999")
            for rel in written:
                if rel.lower().endswith(".tsv"):
                    with self.subTest(rel=rel):
                        self.assertFalse(tf.is_test_file(tf.parse_bytes((bundle / rel).read_bytes())))
            self.assertFalse([p for p in bundle.rglob("*") if "(TEST)" in p.name.upper()])


# ------------------------------------------------------------------------------------------ VirusTotal
class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FakeVT:
    """Answers in order; records every request."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str, dict, bytes | None]] = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, dict(headers), body))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, payload = answer
        return status, json.dumps(payload).encode("utf-8")


def file_report(results=None, stats=None):
    return 200, {"data": {"attributes": {"last_analysis_results": results or {"EngineA": {"category": "undetected"}},
                                          "last_analysis_stats": stats or {"malicious": 0, "suspicious": 0}}}}


def analysis(status, results=None):
    return 200, {"data": {"attributes": {"status": status, "results": results or {},
                                          "stats": {"malicious": 0, "suspicious": 0}}}}


KEY = "test-key-not-real-123"


class VirusTotalTests(unittest.TestCase):
    def client(self, fake, **kw):
        self.time = FakeTime()
        return vs.VirusTotal(KEY, transport=fake, sleep=self.time.sleep, clock=self.time.clock, **kw)

    def test_clean_known_file(self):
        fake = FakeVT(file_report())
        result = self.client(fake).scan("translations/fr.tsv", b"data")
        self.assertEqual(result.status, "clean")
        method, url, headers, _ = fake.calls[0]
        self.assertEqual((method, url), ("GET", "https://www.virustotal.com/api/v3/files/"
                                         + hashlib.sha256(b"data").hexdigest()))
        self.assertEqual(headers["x-apikey"], KEY)

    def test_flagged_file_fails_and_names_the_engines(self):
        fake = FakeVT(file_report({"EngineA": {"category": "undetected"},
                                   "EngineB": {"category": "malicious", "result": "Trojan.X"},
                                   "EngineC": {"category": "suspicious", "result": None}},
                                  {"malicious": 1, "suspicious": 1}))
        result = self.client(fake).scan("translations/fr.tsv", b"data")
        self.assertEqual(result.status, "flagged")
        self.assertEqual(result.engines, ["EngineB (Trojan.X)", "EngineC (suspicious)"])
        text = vs.comment([result], [], False)
        self.assertIn("FAILED", text)
        self.assertIn("EngineB (Trojan.X)", text)
        self.assertIn("EngineC", text)

    def test_unknown_file_is_uploaded_and_polled(self):
        fake = FakeVT((404, {"error": {"code": "NotFoundError"}}), (200, {"data": {"id": "abc123=="}}),
                      analysis("queued"), analysis("in-progress"),
                      analysis("completed", {"EngineA": {"category": "undetected"}}))
        result = self.client(fake).scan("translations/fr.tsv", b"hello\tworld")
        self.assertEqual(result.status, "clean")
        self.assertEqual([c[0] for c in fake.calls], ["GET", "POST", "GET", "GET", "GET"])
        self.assertEqual(fake.calls[1][1], "https://www.virustotal.com/api/v3/files")
        self.assertIn(b"hello\tworld", fake.calls[1][3])
        self.assertTrue(fake.calls[1][2]["content-type"].startswith("multipart/form-data; boundary="))
        self.assertTrue(fake.calls[2][1].endswith("/analyses/abc123%3D%3D"))
        for call in fake.calls:
            self.assertTrue(call[1].startswith("https://www.virustotal.com/api/v3/"))

    def test_uploaded_file_flagged_after_analysis(self):
        fake = FakeVT((404, {}), (200, {"data": {"id": "a1"}}),
                      analysis("completed", {"Bad": {"category": "malicious", "result": "Eicar"}}))
        result = self.client(fake).scan("translations/fr.tsv", b"x")
        self.assertEqual((result.status, result.engines), ("flagged", ["Bad (Eicar)"]))

    def test_analysis_that_never_finishes_times_out_as_not_scanned(self):
        fake = FakeVT((404, {}), (200, {"data": {"id": "a1"}}), *[analysis("queued")] * 50)
        result = self.client(fake, poll_limit=120).scan("translations/fr.tsv", b"x")
        self.assertEqual(result.status, "not scanned")
        self.assertIn("in time", result.detail)

    def test_unreachable_or_refused_key_is_not_scanned(self):
        result = self.client(FakeVT(OSError("down"))).scan("translations/fr.tsv", b"x")
        self.assertEqual(result.status, "not scanned")
        result = self.client(FakeVT((401, {}))).scan("translations/fr.tsv", b"x")
        self.assertEqual(result.status, "not scanned")
        result = self.client(FakeVT((500, {}))).scan("translations/fr.tsv", b"x")
        self.assertEqual(result.status, "not scanned")

    def test_rate_limit_spacing_and_429_waiting(self):
        fake = FakeVT((429, {}), (429, {}), (404, {}), (200, {"data": {"id": "a1"}}), analysis("completed"))
        result = self.client(fake).scan("translations/fr.tsv", b"x")
        self.assertEqual(result.status, "clean")
        self.assertEqual(self.time.slept.count(vs.QUOTA_WAIT), 2)
        # never more than 4 requests a minute
        stamps = []
        fake2 = FakeVT(file_report(), file_report(), file_report(), file_report(), file_report())
        client = self.client(fake2)
        original = fake2.__call__

        def stamped(*a):
            stamps.append(self.time.now)
            return original(*a)
        client._transport = stamped
        for n in range(5):
            client.scan(f"translations/f{n}.tsv", bytes([n]))
        self.assertTrue(all(b - a >= vs.MIN_INTERVAL for a, b in zip(stamps, stamps[1:])), stamps)

    def test_quota_never_lifting_is_not_scanned(self):
        fake = FakeVT(*[(429, {})] * (vs.MAX_QUOTA_RETRIES + 1))
        self.assertEqual(self.client(fake).scan("translations/fr.tsv", b"x").status, "not scanned")

    def test_missing_key_fails_and_says_so(self):
        with self.assertRaises(vs.NotScanned):
            vs.VirusTotal("")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "files").mkdir()
            (work / "files" / "000.tsv").write_bytes(b"x")
            (work / "manifest.json").write_text(json.dumps({"files": [
                {"path": "translations/fr.tsv", "local": "files/000.tsv"}], "refused": []}), encoding="utf-8")
            clean, results = vs.run(work, "")
            self.assertFalse(clean)
            self.assertEqual(results[0].status, "not scanned")
            self.assertIn("VT_API_KEY is not set", (work / "scan-comment.md").read_text(encoding="utf-8"))
            self.assertEqual((work / "scan-result.txt").read_text(encoding="utf-8"), "not scanned")

    def test_refused_files_fail_the_scan_and_the_key_never_appears(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "manifest.json").write_text(json.dumps({"files": [], "refused": [
                {"path": "translations/x.exe", "reason": "only .tsv"}]}), encoding="utf-8")
            clean, _ = vs.run(work, KEY)
            self.assertFalse(clean)
            for name in ("scan-comment.md", "scan.json", "scan-result.txt"):
                self.assertNotIn(KEY, (work / name).read_text(encoding="utf-8"))
        result = self.client(FakeVT(OSError("boom " + KEY))).scan("translations/fr.tsv", b"x")
        self.assertNotIn(KEY, result.detail)

    def test_redirects_are_never_followed(self):
        with self.assertRaises(vs.NotScanned):
            vs._HostOnly().redirect_request(None, None, 302, "", {}, "https://elsewhere.example/")

    def test_no_key_in_the_source(self):
        source = (ROOT / "scripts" / "virustotal_scan.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("VT_API_KEY"', source)
        self.assertNotRegex(source, r"x-apikey\"?\s*:\s*\"[0-9a-f]{20,}")
        self.assertEqual(set(re.findall(r"https://([A-Za-z0-9.-]+)", source)), {"www.virustotal.com"} | set())


# ------------------------------------------------------------------------------------------ the collector
class CollectorTests(unittest.TestCase):
    def event(self, association="NONE"):
        return {"pull_request": {"number": 7, "author_association": association,
                                 "head": {"sha": "a" * 40, "repo": {"full_name": "someone/fork"}}},
                "repository": {"full_name": "Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher"}}

    def fake_get(self, files, contents):
        asked = []

        def get(url, token, accept="", limit=None):
            asked.append(url)
            if "/pulls/7/files" in url:
                return json.dumps(files).encode("utf-8")
            for path, data in contents.items():
                if url.startswith(f"{tp.API}/repos/someone/fork/contents/{path}?ref={'a' * 40}"):
                    return data[:limit + 1] if limit else data
            raise AssertionError(url)
        return get, asked

    def test_pr_files_are_fetched_as_data_and_others_refused(self):
        good = make()
        files = [{"filename": "translations/fr.tsv", "status": "added"},
                 {"filename": "translations/evil.exe", "status": "added"},
                 {"filename": "translations/README.md", "status": "modified"},
                 {"filename": "translations/de.tsv", "status": "removed"},
                 {"filename": "translations/big.tsv", "status": "added"},
                 {"filename": "src/other.py", "status": "modified"}]
        get, asked = self.fake_get(files, {"translations/fr.tsv": good,
                                           "translations/big.tsv": b"a" * (vt.MAX_BYTES + 10)})
        with tempfile.TemporaryDirectory() as tmp:
            manifest = tp.collect_pr(self.event(), Path(tmp), "token", get)
            self.assertEqual([f["path"] for f in manifest["files"]], ["translations/fr.tsv"])
            self.assertEqual(manifest["files"][0]["local"], "files/000.tsv")
            self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(good).hexdigest())
            refused = {r["path"] for r in manifest["refused"]}
            self.assertEqual(refused, {"translations/evil.exe", "translations/README.md", "translations/de.tsv",
                                       "translations/big.tsv"})
            self.assertFalse(any("evil.exe" in url for url in asked))    # never downloaded
        with tempfile.TemporaryDirectory() as tmp:
            manifest = tp.collect_pr(self.event("OWNER"), Path(tmp), "token", get)
            self.assertEqual({s["path"] for s in manifest["skipped"]},
                             {"translations/README.md", "translations/de.tsv"})

    def test_only_api_github_com_is_asked(self):
        with self.assertRaises(tp.Unusable):
            tp.api_get("https://example.com/x", "t")
        with self.assertRaises(tp.Unusable):
            tp.api_get("http://api.github.com/x", "t")


# ------------------------------------------------------------------------------------------ the guide
WARNING = (
    "This button allows you to share your game translation to the patcher's Public Github. IF ACCEPTED, everyone "
    "who uses this patcher will be able to see your translation in the game and your username will be included in "
    "the credits. Please DO NOT put ANY PRIVATE DETAILS YOU DO NOT WANT TO MAKE PUBLIC!",
    "Email addresses are never saved and are rejected from translation files.",
    "This feature is meant to be a community collaboration tool for game modding only.",
    "You will need a Github account to proceed. Continue?",
)


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.text = README.read_text(encoding="utf-8")

    def test_the_share_warning_is_there_word_for_word(self):
        for sentence in WARNING:
            with self.subTest(sentence=sentence[:40]):
                self.assertIn("> " + sentence, self.text)
        self.assertIn("Please DO NOT put ANY PRIVATE DETAILS YOU DO NOT WANT TO MAKE PUBLIC!", self.text)
        self.assertEqual(vs.MISSING_KEY.count("@"), 0)
        self.assertEqual(tf.EMAIL_MESSAGE, WARNING[1])

    def test_the_easy_way_and_the_credit(self):
        for words in ("Add file → Upload files", "pull request automatically", "any text editor", "Make a translation",
                      "@translator", "Never put an email address in it", "accept-translation", "<language code>.tsv"):
            self.assertIn(words, self.text)

    def test_virustotal_is_disclosed(self):
        self.assertRegex(self.text, r"sent to VirusTotal")
        self.assertIn("VirusTotal's\npartners", self.text)
        self.assertIn("never to put\nprivate details", self.text)

    def test_no_email_address_in_the_guide(self):
        self.assertFalse(tf.contains_email(self.text))
        self.assertNotIn("@example", self.text)

    def test_the_folder_holds_only_the_guide_and_language_files(self):
        for path in (ROOT / "translations").iterdir():
            if path.name != "README.md":
                self.assertEqual(vt.pre_check("translations/" + path.name, path.read_bytes()), "", path.name)
                self.assertTrue(vt.check_file("translations/" + path.name, path.read_bytes())[0], path.name)


# ------------------------------------------------------------------------------------------ the workflow
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_triggers(self):
        self.assertRegex(self.text, r"(?m)^  pull_request_target:\n    types: \[opened, synchronize, reopened, labeled\]"
                                    r"\n    paths: \[\"translations/\*\*\"\]")
        self.assertRegex(self.text, r"(?m)^  push:\n    branches: \[main\]\n    paths: \[\"translations/\*\*\"\]")
        self.assertNotRegex(self.text, r"(?m)^  pull_request:")

    def test_minimal_permissions(self):
        top = re.search(r"(?m)^permissions:\n((?:  .*\n)+)", self.text).group(1)
        self.assertEqual(top.split(), ["contents:", "read", "pull-requests:", "write", "issues:", "write"])
        # only the owner-label accept job may write, and it checks the owner
        writes = re.findall(r"contents: write", self.text)
        self.assertEqual(len(writes), 1)
        accept = self.text[self.text.index("  accept:"):]
        self.assertIn("contents: write", accept)
        self.assertIn("github.event.sender.login == github.repository_owner", accept)
        self.assertIn("--match-head-commit \"$HEAD_SHA\"", accept)

    def test_never_checks_out_or_runs_the_pull_request(self):
        self.assertNotIn("ref:", self.text)
        self.assertNotRegex(self.text, r"head\.ref|head_ref|refs/pull|merge_commit_sha")
        self.assertEqual(self.text.count("actions/checkout@v4"), 2)
        self.assertEqual(self.text.count("persist-credentials: false"), 2)
        self.assertNotRegex(self.text, r"\b(pip install|npm|make)\b")
        for line in re.findall(r"(?m)^\s+run: (.*)$", self.text):
            if line.startswith("python"):
                self.assertTrue(line.startswith("python -I scripts/"), line)

    def test_no_pr_text_in_a_shell(self):
        # Expressions in run: blocks are pasted into the script before the shell sees it; only
        # env: may carry them. Find every ${{ }} and check it is not inside a run block.
        in_run = False
        run_indent = 0
        for line in self.text.splitlines():
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if in_run and stripped and indent <= run_indent:
                in_run = False
            if re.match(r"-?\s*run:", stripped):
                in_run, run_indent = True, indent
                self.assertNotIn("${{", line)
                continue
            if in_run:
                self.assertNotIn("${{", line, line)
        for field in ("title", "body", "head.ref", "head.label", "user.login", "label.description"):
            self.assertNotIn("pull_request." + field, self.text.replace("pull_request.head.sha", ""))

    def test_scan_runs_first_and_validate_needs_it(self):
        jobs = re.findall(r"(?m)^  ([a-z]+):\n", self.text.split("\njobs:\n", 1)[1])
        self.assertEqual(jobs[:2], ["scan", "validate"])
        validate = self.text[self.text.index("  validate:"):self.text.index("  refuse:")]
        self.assertIn("needs: scan", validate)
        self.assertIn("SCANNED: ${{ needs.scan.outputs.hashes }}", validate)
        for job in ("  refuse:", "  accept:"):
            block = self.text[self.text.index(job):]
            self.assertIn("needs: [scan, validate]", block.split("\n  ", 2)[1] + block)
        refuse = self.text[self.text.index("  refuse:"):self.text.index("  accept:")]
        self.assertIn("--remove-label accept-translation", refuse)

    def test_secret_handling(self):
        self.assertEqual(self.text.count("secrets.VT_API_KEY"), 1)
        scan_step = self.text[self.text.index("- name: Scan every file with VirusTotal"):]
        scan_step = scan_step[:scan_step.index("\n      - ")]
        self.assertIn("VT_API_KEY: ${{ secrets.VT_API_KEY }}", scan_step)
        self.assertNotRegex(self.text, r"echo .*VT_API_KEY|VT_API_KEY.*>>")
        self.assertNotRegex(self.text, r"user\.email|@users\.noreply|@[a-z0-9-]+\.(com|org|net)")

    def test_yaml_structure(self):
        if yaml is None:
            self.skipTest("PyYAML is not installed; the text checks above cover the workflow")
        doc = yaml.safe_load(self.text)
        triggers = doc.get("on", doc.get(True))
        self.assertEqual(set(triggers), {"pull_request_target", "push", "workflow_dispatch"})
        self.assertEqual(doc["permissions"], {"contents": "read", "pull-requests": "write", "issues": "write"})
        jobs = doc["jobs"]
        self.assertEqual(jobs["validate"]["needs"], "scan")
        self.assertNotIn("permissions", jobs["scan"])
        self.assertNotIn("permissions", jobs["validate"])
        for name, job in jobs.items():
            for step in job["steps"]:
                if "uses" in step and step["uses"].startswith("actions/checkout"):
                    self.assertNotIn("ref", step.get("with", {}), name)
                if "run" in step:
                    self.assertNotIn("${{", step["run"], name)
        scan_env = [s.get("env", {}) for s in jobs["scan"]["steps"]]
        self.assertIn({"VT_API_KEY": "${{ secrets.VT_API_KEY }}"}, scan_env)


if __name__ == "__main__":
    unittest.main()
