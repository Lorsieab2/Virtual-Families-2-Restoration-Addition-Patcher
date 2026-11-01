"""Which of the image table's pictures the game asks for: src/vf2_game_pictures.json "usage", recomputed from the
B200 desktop objects (scripts/build_vf2_image_table.py: the call graph from WinMain, the ids every call passes, the
tables and data files the computed ids come from), and a few claims pinned one by one.

Skips without work/desktop_obj_files (the game's code) and work/vanilla_runtime_payload (its Assets data files, which
CAnimManager::LoadAssets reads)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
DATA = ROOT / "src" / "vf2_game_pictures.json"
HAVE = (OBJ_DIR / "theGraphicsManager.obj").is_file() and (GAME_DIR / "Assets" / "animpts.dat").is_file()
pytestmark = pytest.mark.skipif(not HAVE, reason="no B200 desktop objects or no original game folder")


@pytest.fixture(scope="module")
def builder():
    pytest.importorskip("capstone")
    pytest.importorskip("unicorn")
    import build_vf2_image_table as b
    return b


@pytest.fixture(scope="module")
def table(builder):
    return builder.image_table(OBJ_DIR)


@pytest.fixture(scope="module")
def usage(builder, table):
    return builder.image_usage(OBJ_DIR, table, GAME_DIR)[0]


@pytest.fixture(scope="module")
def graph(builder):
    from vf2_people_emu import CoffObject
    objs = {p.stem: CoffObject(p) for p in sorted(OBJ_DIR.glob("*.obj"))}
    funcs, edges, roots = builder.call_graph(objs)
    return objs, funcs, edges, roots, builder.reachable(builder.unused_globals(edges), roots)


@pytest.fixture(scope="module")
def sites(builder, graph):
    objs, funcs, *_ = graph
    return {(fn, addr): vals for fn, addr, _callee, vals in builder.call_sites(objs, funcs)}


def _file(table, i):
    return next(e["file"] for e in table if e["id"] == i)


def test_the_data_file_is_recomputed(usage):
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert data["usage"] == {k: list(v) for k, v in usage.items()}
    assert len(usage) == 630                                    # every table id but 0, "No Graphic"
    assert sum(1 for used, _w in usage.values() if not used) == 22


def test_dead_code_is_not_reached(graph):
    *_, live = graph
    assert "_WinMain@16" in live
    for name in ("??0theVariableMeter@@QAE@XZ", "??0theSlicedVariableMeter@@QAE@XZ", "??0theHummingbirdClass@@IAE@XZ",
                 "??0CDayNightCycleTestDlg@@QAE@XZ", "?Init@theProgressDlg@@IAEXPBDH@Z", "??0theDealerSay@@IAE@XZ",
                 "?Draw@CLightSourceEditor@@UAEXXZ", "?LoadAssets@CWaypointEditor@@QAEXXZ",
                 "?LoadAssets@CLightSourceEditor@@QAEXXZ"):
        assert name not in live, name
    # constructed while the game loads (theGame::GameUpdate), so counted as reached, though only a debug key shows it
    assert "?DrawSceneEditAnimation@theAlignVillagerScene@@AAEXXZ" in live
    assert "?DrawPet@CPetManager@@QAEXH@Z" in live and "?Draw@CStory@@QAEXXZ" in live


def test_the_editors_globals_reach_nothing_virtual(builder, graph):
    _objs, _funcs, edges, roots, live = graph
    plain = builder.reachable(edges, roots)                    # without the never-used-global refinement
    assert "?Draw@CLightSourceEditor@@UAEXXZ" in plain and "?Draw@CLightSourceEditor@@UAEXXZ" not in live
    assert "??0CLightSourceEditor@@QAE@XZ#object never used" in live    # its constructor still runs
    assert "?Draw@CWaypointEditor@@UAEXXZ" not in live


def test_pinned_unused(usage, table):
    assert _file(table, 363) == "LoadColor.png"
    assert usage["363"] == [False, "Only theVariableMeter::theVariableMeter asks for it, and no code reached from "
                                   "WinMain calls it."]
    assert _file(table, 597) == "hummingbirdstrip.png"
    assert usage["597"][0] is False and "theHummingbirdClass::theHummingbirdClass" in usage["597"][1]
    for i in (77, 358, 367, 368, 369, 618, 619, 620, 621, 624, 633, 636):
        assert usage[str(i)][0] is False and usage[str(i)][1].startswith("No code asks"), i
    assert _file(table, 77) == "Furniture/LaundryBasketStd.png"


def test_the_furniture_table(builder, usage, table, graph):
    objs, *_ = graph
    data, _rel = builder._symbol_bytes(objs["FurnitureManager"], "?itemInfo@@3PAUsFurnitureInfo@@A")
    assert len(data) == 252 * 0x6C
    ids = builder._resolve(builder._FURNITURE, objs, OBJ_DIR, GAME_DIR, {}, {}, {e["id"] for e in table}, "")[0]
    furniture = {e["id"] for e in table if e["file"].startswith("Furniture/")}
    assert furniture - ids == {77}                               # the laundry basket has no furniture entry
    assert 7 in ids                                              # the pet bowls item draws from pet_grid.png
    assert all(usage[str(i)][0] for i in furniture - {77})
    assert "the furniture table" in usage["85"][1] and "CFurnitureManager::Draw" in usage["85"][1]


def test_computed_ids(sites):
    assert sites[("?LoadAssets@CWind@@QAEXXZ", 0x1E)] == {0x24E, 0x24F, 0x250}                  # a counted loop
    assert sites[("?AddBubble@CBubbles@@QAEXUldwPoint@@HMM@Z", 0x58)] == {0x1D9, 0x1DA}          # setne + add
    assert sites[("?DrawAchievement@CAchievement@@QAEXHHH_NM@Z", 0x11B)] == {0x271, 0x272}
    assert sites[("?GetImageGridForCanvas@theGraphicsManager@@QAEPAVldwImageGrid@@H@Z", 0x19)] == {0x15F}
    assert sites[("?Init@theMessageBoxDlg@@IAEXPBDW4EImage@@0H@Z", 0x1A9)] == {"p:1"}             # its argument


def test_pinned_used(usage):
    assert usage["10"] == [True, "Asked for by CScrollingStoreScene::DrawVisibleStoreItem, from its gIAPItem table."]
    assert "CAnimManager::GetScaledLinkToNextPt" in usage["21"][1]     # bigheads: an id animpts.dat holds
    assert usage["610"] == [True, "Asked for by CLifeEvent::Show, through ShowMessageBox."]       # wedding.jpg
    assert usage["590"] == [True, "Asked for by CWind::LoadAssets."]
    assert "CStory::Draw, from the pictures given to CStory::AddImage" in "".join(v[1] for v in usage.values())
    assert usage["600"] == [True, "Asked for by CNight::SetupLightSource."]
    assert "CInventoryManager::DrawItem" in usage["333"][1]                # a service icon from its local table


# ---------------------------------------------------------------------- mutations: the checks catch a broken analysis
def test_mutation_an_unresolved_call_stops_the_build(builder, table, monkeypatch):
    rules = dict(builder.SITE_RULES)
    del rules[("?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z", 0xA7)]
    monkeypatch.setattr(builder, "SITE_RULES", rules)
    with pytest.raises(SystemExit, match="not resolved"):
        builder.image_usage(OBJ_DIR, table, GAME_DIR)


def test_mutation_a_wrong_table_changes_the_answer(builder, table, usage, monkeypatch):
    rules = dict(builder.SITE_RULES)
    key = ("?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z", 0xA7)
    rules[key] = rules[key][:3] + (16,) + rules[key][4:]          # a wrong stride
    monkeypatch.setattr(builder, "SITE_RULES", rules)
    assert builder.image_usage(OBJ_DIR, table, GAME_DIR)[0] != usage


def test_mutation_reaching_dead_code_changes_the_answer(builder, table, usage, monkeypatch):
    monkeypatch.setattr(builder, "ROOTS", builder.ROOTS + ("??0theVariableMeter@@QAE@XZ",))
    assert builder.image_usage(OBJ_DIR, table, GAME_DIR)[0]["363"][0] is True
    monkeypatch.setattr(builder, "ROOTS", ("_WinMain@16",))
    monkeypatch.setattr(builder, "unused_globals", lambda edges: edges)
    changed = builder.image_usage(OBJ_DIR, table, GAME_DIR)[0]
    assert "CLightSourceEditor::Draw" in changed["364"][1] and "CLightSourceEditor::Draw" not in usage["364"][1]


def test_mutation_branches_not_followed(builder, graph, monkeypatch):
    objs, funcs, *_ = graph
    monkeypatch.setattr(builder, "cond", lambda m, flags: None)   # every branch both ways: the loop never ends
    oname, s, a, e = funcs["?LoadAssets@CWind@@QAEXXZ"][0]
    vals = builder._Walk(objs[oname], s, a, e).run()[(0x1E, "?GetImage@theGraphicsManager@@QAEPAVldwImage@@W4EImage@@@Z")]
    assert None in vals                                             # widened: unknown, so the build would stop
