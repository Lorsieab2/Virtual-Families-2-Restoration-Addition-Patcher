# Mobile VF2 Debug Editor Check

Checked on 2026-07-01 from the local mobile archive:

- `work/Virtual+Families+2_1.7.16_APKPure.xapk`
- re-extracted for inspection to `work/vf2_mobile_reextract/`
- native libraries inspected under `work/vf2_mobile_reextract/apk/lib/*/libVirtualFamilies2.so`

## Result

The mobile VF2 native libraries contain real built-in debugger/editor support for:

- `CDebugger`
- `IEditor`
- `CWaypointEditor`
- `CLightSourceEditor`

The mobile libraries did not show evidence of implemented behavior/content-map editor classes:

- no `BehaviorEditor`
- no `CBehaviorEditor`
- no `ContentMapEditor`
- no `CContentMapEditor`

This matches the desktop object-file evidence: `WaypointEditor` and `LightSourceEditor` are real editor implementations, while `BehaviorEditor.obj`, `ContentMapEditor.obj`, and `Editor.obj` in the desktop object set do not expose usable editor class/object methods.

## Evidence

All four mobile ABIs contained editor symbols for waypoint and light-source editing:

- `arm64-v8a`
- `armeabi-v7a`
- `x86`
- `x86_64`

Representative `x86` strings/symbol names:

```text
_ZN18CLightSourceEditor10LoadAssetsEv
_ZN18CLightSourceEditor11HandleKeyUpEi
_ZN18CLightSourceEditor13HandleKeyDownEi
_ZN18CLightSourceEditor13HandleMouseUpE8ldwPoint
_ZN18CLightSourceEditor15HandleMouseDownE8ldwPoint
_ZN18CLightSourceEditor15HandleMouseMoveE8ldwPoint
_ZN18CLightSourceEditor18HandleKeyCharacterEc
_ZN18CLightSourceEditor4DrawEv
_ZN18CLightSourceEditor5ResetEv
_ZN18CLightSourceEditor8ActivateEb
_ZTV18CLightSourceEditor
_ZN15CWaypointEditor10LoadAssetsEv
_ZN15CWaypointEditor11HandleKeyUpEi
_ZN15CWaypointEditor13DrawWaypointsEv
_ZN15CWaypointEditor13HandleKeyDownEi
_ZN15CWaypointEditor13HandleMouseUpE8ldwPoint
_ZN15CWaypointEditor15HandleMouseDownE8ldwPoint
_ZN15CWaypointEditor15HandleMouseMoveE8ldwPoint
_ZN15CWaypointEditor18HandleKeyCharacterEc
_ZN15CWaypointEditor4DrawEv
_ZN15CWaypointEditor5ResetEv
_ZTV15CWaypointEditor
```

User-facing/debug strings present:

```text
Light Source Editor Enabled (F4 to exit)
Waypoint Editor Enabled
```

Direct byte/string searches returned no hits for:

```text
BehaviorEditor
CBehaviorEditor
ContentMapEditor
CContentMapEditor
```

## Interpretation

The mobile game and desktop objects contain the same useful debug surface, but
the interfaces are separate:

- theMainScene implements IDebugger through its secondary base at this+8.
- CWaypointEditor and CLightSourceEditor implement IEditor.
- The editor globals are therefore not valid arguments to
  CDebugger::Register(IDebugger *). The former B62 research helper's casts from
  those editor addresses to IDebugger * were type-invalid.

The original corrected default-off research design registered only the real
theMainScene debugger provider. The B156 helper also registers the preserved
offset-zero `CVillagerManager` `IDebugger` provider, whose native `Debug()` page
reports the focused villager's position, feet position, current behavior,
current action, next action, and animation frame. F6 selects the native
Waypoint Editor, F7 selects the native Light Source Editor, and F4 deactivates
the selected editor through a separate IEditor * route. The dormant developer
build now also routes key-character and
mouse down/move/up calls through guarded hooks only after F5 activation.
Disabled, unhandled, or fault-disabled sessions fall through to the original
main-scene handlers. The normal build does not install any of these hooks.
This source and link proof does not replace live save-load and input testing
after the B58-B62 failures.

Native disassembly pins `HandleKeyDown(int)` and
`HandleKeyCharacter(char)` to `ret 4`, while all point handlers use `ret 8`.
The regression suite now asserts each inserted payload, cleanup width, REL32
helper relocation target, and a 24-byte stock fallthrough window for every
hook.

The native vtable relocation order is Reset, Draw, KeyCharacter, KeyDown,
KeyUp, MouseDown, MouseUp, MouseMove, Activate. The generated `IEditor`
declaration now matches those nine slots exactly, and the regression test reads
the relocations from `LightSourceEditor.obj` rather than trusting the handwritten
declaration.

The main-scene constructor writes its IDebugger vptr at object offset `+8`, and
that vtable's only slot targets `theMainScene::Debug`. `CDebugger::Register` and
`Draw` independently prove the provider array, count, selected index, and draw
anchor offsets used by the helper. A separate default-off test proves the stock
main-scene object remains SHA-256
`BA93F6430B45AAB75EFAE17C982BD9AC52DF078AE6E798D7D4F92E5DEBF733FB`.

Native disassembly also proves that `CLightSourceEditor::HandleKeyDown(int)`
is only a return-false stub. Add, delete, save, and type cycling live in
`HandleKeyCharacter(char)`. The helper therefore sends printable commands only
through the dedicated character hook; forwarding them from key-down as well
could execute a command twice. The corrected helper and scene link into a
1,737,216-byte x86 Windows GUI diagnostic with SHA-256
`1D8C51B67CB02BC3310CA5C25DC00E51D792A720B6BE684328488B5B12B04520`.

The save-safe test order, stop conditions, exact controls, and pass boundary are
in the [debugger live-test checklist](debugger-live-test-checklist.md). The
developer executable must be tested only with a disposable save/player.

The desktop Light Source Editor already contains the requested core operations:

- L: add a light source at the cursor.
- D: delete the selected/nearby light source.
- S: save changes through CNight::Save.
- +: advance the selected light-source type, wrapping from 11 to 3.
- -: move to the previous selected light-source type, wrapping from 3 to 11.
- mouse drag: move a selected light source.

The desktop Waypoint Editor uses W to select the next of five native waypoint
positions and scroll it into view, S to save through CWaypoint::Save, and mouse
down/move/up to select a nearby waypoint and drag it. Its key-down handler is a
return-false stub, so W/w and S/s are character events rather than raw key-down
commands.

CLightSourceEditor::Activate(true) temporarily forces the night-light state
needed to see the editor; Activate(false) restores the prior value. This
lifecycle must always run when switching or leaving editors.

Behavior editing and content-map editing may have existed in another internal/dev build, but they are not present as named editor implementations in this mobile release. The restored `CVillagerManager::Debug()` page is a viewer, not a behavior editor. If we want editing features, the safer route is to build new editor functionality around existing systems like `CBehavior`, `CVillagerPlans`, `CContentMap`, and `CContentMapUtil`, rather than trying to register missing editor singletons.
