"""The parallel matrix build splits over any number of parts, and parts never share a scratch file.

work/build_matrix_parallel.ps1 runs one work/build_matrix.ps1 per worktree at the same time. Two things
must hold for that to scale past three parts:

* work/build_b119.bat (the link step every variant runs) writes its link response file inside the
  checkout, not at one fixed %TEMP% path every part shares. B205's part m1 failed once with link exit 255
  when two parts wrote that one file at the same moment.
* work/matrix_parts.ps1 deals the variants out evenly over N parts and gives each part the seed folders of
  its own variants, copying a missing one completely or not at all and never replacing one that is there.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_BAT = ROOT / "work" / "build_b119.bat"
PARTS_PS1 = ROOT / "work" / "matrix_parts.ps1"
PARALLEL_PS1 = ROOT / "work" / "build_matrix_parallel.ps1"
MATRIX = ROOT / "data" / "vf2" / "build-matrix-toggles.json"
OBJ = r"work\patched_mobile_furniture_pack_objs\vf2_mobile_renovations.obj"

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
ON_WINDOWS = sys.platform == "win32"


def _ps(script: str, cwd: Path = ROOT):
    """Run PowerShell with matrix_parts.ps1 loaded; returns (exit code, stdout, stderr)."""
    command = f". '{PARTS_PS1}'; $ErrorActionPreference = 'Stop'; {script}"
    result = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                            cwd=str(cwd), capture_output=True, text=True, timeout=300)
    return result.returncode, result.stdout, result.stderr


def _rsp_block() -> str:
    """The lines of build_b119.bat that build the link response file, from LINK_RSP to the count check."""
    lines = BUILD_BAT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('set "LINK_RSP='))
    end = next(i for i, line in enumerate(lines) if '"%MOBILE_RENOVATION_COUNT%"=="1"' in line)
    return "\n".join(lines[start:end + 1])


class TheLinkResponseFileIsPerCheckout(unittest.TestCase):
    def test_the_response_file_is_inside_the_checkout(self):
        set_line = next(line for line in BUILD_BAT.read_text(encoding="utf-8").splitlines()
                        if line.startswith('set "LINK_RSP='))
        self.assertEqual(set_line, r'set "LINK_RSP=work\patched_mobile_furniture_pack_objs\vf2_link_b119_no_out.rsp"')
        self.assertNotIn("%TEMP%", set_line.upper())
        self.assertNotIn("%TMP%", set_line.upper())

    def test_no_build_script_names_a_fixed_temp_file(self):
        for script in (BUILD_BAT, ROOT / "work" / "build_matrix.ps1", PARALLEL_PS1, PARTS_PS1):
            for line in script.read_text(encoding="utf-8").splitlines():
                if line.lstrip().lower().startswith(("rem", "#")):
                    continue
                self.assertNotRegex(line, r"(?i)%TE?MP%\\", f"{script.name}: {line}")

    @unittest.skipUnless(ON_WINDOWS, "runs cmd.exe")
    def test_two_checkouts_build_their_response_files_at_once(self):
        """Two parts at once each write their own complete response file and nothing in %TEMP%."""
        link_rsp = (ROOT / "work" / "vf2_link_b27_arcade_behavior_restore.rsp").read_text(encoding="ascii")
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            temp = base / "temp"
            temp.mkdir()
            checkouts = []
            for name in ("m1", "m2"):
                checkout = base / name
                (checkout / "work" / "patched_mobile_furniture_pack_objs").mkdir(parents=True)
                (checkout / "work" / "vf2_link_b27_arcade_behavior_restore.rsp").write_text(link_rsp, encoding="ascii")
                (checkout / "rsp.bat").write_text(
                    "@echo off\r\nsetlocal\r\n" + _rsp_block().replace("\n", "\r\n") + "\r\nexit /b 0\r\n",
                    encoding="ascii")
                checkouts.append(checkout)
            env = dict(os.environ, TEMP=str(temp), TMP=str(temp))
            env["PATH"] = r"C:\Windows\system32;C:\Windows;C:\Windows\System32\Wbem"
            results = {}

            def run(checkout):
                for _ in range(3):
                    done = subprocess.run(["cmd.exe", "/d", "/c", str(checkout / "rsp.bat")], cwd=str(checkout), env=env,
                                          capture_output=True, text=True)
                    if done.returncode != 0:
                        results[checkout.name] = done
                        return
                results[checkout.name] = done

            threads = [threading.Thread(target=run, args=(c,)) for c in checkouts]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            for checkout in checkouts:
                done = results[checkout.name]
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                rsp = checkout / "work" / "patched_mobile_furniture_pack_objs" / "vf2_link_b119_no_out.rsp"
                lines = rsp.read_text(encoding="ascii").splitlines()
                self.assertFalse([l for l in lines if l.startswith("/OUT:")])
                self.assertEqual([l for l in lines if OBJ.lower() in l.lower()], [f'"{OBJ}"'])
                expected = [l for l in link_rsp.splitlines()
                            if not l.startswith("/OUT:") and OBJ.lower() not in l.lower()] + [f'"{OBJ}"']
                self.assertEqual(lines, expected)
            self.assertEqual(list(temp.iterdir()), [])


@unittest.skipUnless(POWERSHELL, "needs PowerShell")
class TheSplitScalesToNParts(unittest.TestCase):
    def test_every_part_count_deals_every_variant_once_and_evenly(self):
        code, out, err = _ps(
            f"$m = Get-Content -LiteralPath '{MATRIX}' -Raw | ConvertFrom-Json; $v = @($m.variants); "
            "$all = @{}; foreach ($n in 1..$v.Count) { $s = Split-MatrixVariants -Variants $v -Parts $n; "
            "$all[[string]$n] = @($s | ForEach-Object { , @($_ | ForEach-Object { $_.name }) }) }; "
            "$all | ConvertTo-Json -Depth 5 -Compress")
        self.assertEqual(code, 0, err)
        names = [v["name"] for v in json.loads(MATRIX.read_text(encoding="utf-8"))["variants"]]
        self.assertEqual(len(names), 32)
        splits = json.loads(out)
        for n in range(1, len(names) + 1):
            parts = splits[str(n)]
            parts = [p if isinstance(p, list) else [p] for p in parts]
            with self.subTest(parts=n):
                self.assertEqual(len(parts), n)
                self.assertEqual(sorted(sum(parts, [])), sorted(names))
                sizes = [len(p) for p in parts]
                self.assertLessEqual(max(sizes) - min(sizes), 1)
                for k, part in enumerate(parts):
                    self.assertEqual(part, names[k::n])
        self.assertEqual([len(p) for p in splits["8"]], [4] * 8)

    def test_more_parts_than_variants_is_refused(self):
        code, out, err = _ps(
            f"$v = @((Get-Content -LiteralPath '{MATRIX}' -Raw | ConvertFrom-Json).variants); "
            "Split-MatrixVariants -Variants $v -Parts ($v.Count + 1)")
        self.assertNotEqual(code, 0)
        self.assertIn("would build nothing", out + err)

    def test_the_parallel_script_uses_the_shared_split(self):
        text = PARALLEL_PS1.read_text(encoding="utf-8")
        self.assertIn('. (Join-Path $PSScriptRoot "matrix_parts.ps1")', text)
        self.assertIn("Split-MatrixVariants -Variants $variants -Parts $parts", text)
        self.assertIn("$mine = @($split[$k])", text)
        self.assertIn("Sync-PartSeeds", text)


@unittest.skipUnless(POWERSHELL and ON_WINDOWS, "needs PowerShell and robocopy")
class EachPartGetsItsOwnSeeds(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.source = self.base / "release"
        for name in ("a", "b", "c"):
            seed = self.source / "outputs" / f"VF2-OLD-matrix-{name}"
            (seed / "Images").mkdir(parents=True)
            (seed / "Images" / "x.png").write_bytes(name.encode() * 100)
            (seed / "game.dll").write_bytes(b"dll" + name.encode())
        self.release = self.base / "release.json"
        self.release.write_text(json.dumps({
            "output_prefix": "VF2-NEW-matrix",
            "seeds": {n: f"outputs/VF2-OLD-matrix-{n}" for n in ("a", "b", "c")},
        }), encoding="utf-8")
        self.parts = [self.base / "m1", self.base / "m2"]
        for part in self.parts:
            part.mkdir()

    def _sync(self, extra=""):
        script = (
            f"$r = Get-Content -LiteralPath '{self.release}' -Raw | ConvertFrom-Json; "
            "$v = @('a','b','c','d' | ForEach-Object { [pscustomobject]@{ name = $_ } }); "
            "$s = Split-MatrixVariants -Variants $v -Parts 2; $wts = @("
            + ",".join(f"'{p}'" for p in self.parts) + "); "
            "for ($k = 0; $k -lt 2; $k++) { $seeds = @(Get-PartSeeds -Release $r -Variants $s[$k]); "
            f"Sync-PartSeeds -Worktree $wts[$k] -Seeds $seeds {extra} }}")
        return _ps(script)

    def _tree(self, folder):
        return sorted((p.relative_to(folder).as_posix(), p.read_bytes()) for p in folder.rglob("*") if p.is_file())

    def test_each_part_gets_exactly_its_own_variants_seeds(self):
        code, out, err = self._sync(f"-SeedsFrom '{self.source}'")
        self.assertEqual(code, 0, err)
        # a and c (variants 0 and 2) are m1's; b is m2's; d has no seed.
        expected = {"m1": ["VF2-OLD-matrix-a", "VF2-OLD-matrix-c"], "m2": ["VF2-OLD-matrix-b"]}
        for part in self.parts:
            have = sorted(p.name for p in (part / "outputs").iterdir())
            self.assertEqual(have, expected[part.name])
            for name in have:
                self.assertEqual(self._tree(part / "outputs" / name), self._tree(self.source / "outputs" / name))
        self.assertEqual(out.count("copied from"), 3)
        # Run again: nothing is copied, nothing changes.
        code, out, err = self._sync(f"-SeedsFrom '{self.source}'")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count("copied from"), 0)
        self.assertEqual(out.count("present in"), 3)

    def test_a_missing_seed_without_a_source_stops_before_building(self):
        code, out, err = self._sync()
        self.assertNotEqual(code, 0)
        self.assertIn("Pass -SeedsFrom", out + err)

    def test_a_seed_that_differs_from_its_source_is_never_replaced(self):
        mine = self.parts[0] / "outputs" / "VF2-OLD-matrix-a"
        (mine / "Images").mkdir(parents=True)
        (mine / "Images" / "x.png").write_bytes(b"different")
        code, out, err = self._sync(f"-SeedsFrom '{self.source}'")
        self.assertNotEqual(code, 0)
        self.assertIn("Move it aside", out + err)
        self.assertEqual((mine / "Images" / "x.png").read_bytes(), b"different")
        self.assertFalse((mine / "game.dll").exists())

    def test_check_only_copies_nothing(self):
        code, out, err = self._sync(f"-SeedsFrom '{self.source}' -CheckOnly")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count("would copy"), 3)
        for part in self.parts:
            self.assertFalse((part / "outputs").exists())

    def test_no_partial_copy_is_left_looking_like_a_seed(self):
        code, out, err = self._sync(f"-SeedsFrom '{self.source}'")
        self.assertEqual(code, 0, err)
        for part in self.parts:
            self.assertFalse([p for p in (part / "outputs").iterdir() if ".partial-" in p.name])


if __name__ == "__main__":
    unittest.main()
