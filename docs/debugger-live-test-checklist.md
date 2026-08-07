# B153 default-off debugger live-test checklist

This package is a developer-only validation build. It is not a release and must
not replace the published B152 installation. Normal B152 builds remain stock
with respect to debugger input.

## Save safety

The debugger test executable uses the normal game's data locations. Before
testing, make a separate backup of every VF2 save/player folder you care about,
or use a disposable player. Do not press the editor Save command until the
add/delete/drag checks have behaved correctly in the disposable save.

Stop testing immediately if loading a save, moving the mouse, or pressing F5
causes a crash. Preserve `vf2_additive_debug.txt`, `ldwLog.txt`, and the exact
last action.

For a crash handoff, do not restart or retry the scenario until the evidence is
copied. Record the disposable save identity, exact EXE path/size/SHA-256, last
action and timestamp, selected patch settings, dump/log hashes, exception
address, module base/RVA, registers, and stack frames using
`docs/crash-capture-readiness.md`. Static validation alone is never a runtime
pass.

## Files

- `Virtual Families 2 - Additive Mobile Furniture Pack.exe`: untouched B152
  all-patches control executable.
- `Virtual Families 2 - B153 Debugger Test.exe`: opt-in developer executable.
- `Launch_B152_Control.bat`: launches the untouched control from this folder.
- `Launch_B153_Debugger_Test.bat`: launches the developer build from this
  folder so its direct log is written beside the executable.
- `TEST-RESULTS-TEMPLATE.txt`: record every result before sending it back.

## Test order

1. Launch the B152 control. Load the disposable save, move/click around the
   house, then exit normally. Record whether the control passed.
2. Launch the B153 debugger test. Load the same disposable save. Wait at least
   two minutes, move/click around the house, and confirm ordinary play still
   works before pressing any debugger key.
3. Press F5 once. Confirm the game stays open and
   `vf2_additive_debug.txt` contains `VF2 debugger input enabled by F5.`
4. Press Up and Down. Confirm the native debugger overlay changes pages without
   affecting normal house input.
5. Press F6. Confirm the Waypoint Editor appears. Press W five times: the view
   should visit each of the five native waypoint positions once and then wrap.
   Click near a waypoint marker, drag it once, release it, then press F4 and
   confirm normal play resumes. Do not press S during this first pass.
6. Press F7. Confirm the Light Source Editor appears and the night-light view is
   enabled. Press F4 without editing and confirm the previous lighting state is
   restored.
7. Re-enter with F7. Press L exactly once and verify exactly one light is added.
   Press D exactly once and verify exactly one selected/nearby light is removed.
   This specifically validates the single character-event route.
8. Select a light and drag it with the mouse. Press + once to advance its native
   type and - once to return to the previous type. Confirm one visible change
   per key press. Native light types cycle through values 3 through 11.
9. Only on the disposable save, press S once. Exit normally, relaunch the
   debugger test, and confirm the saved light layout persists. S is also the
   Waypoint Editor save command; do not use it there unless you intentionally
   want to persist the dragged waypoint in the disposable save.
10. Press F4, then test ordinary keyboard/mouse input again. Confirm unhandled
    input falls through to the stock handlers.
11. Exit and attach the completed results template plus both debugger logs.

## Pass boundary

The developer path is not ready to enable in a release until save loading,
F5/F6/F7/F4, overlay paging, waypoint selection, light add/delete/drag/type/save,
lighting restoration, stock input fallthrough, and fault-disable behavior all
pass in game. A successful compile, link, or automated test is not a substitute.
