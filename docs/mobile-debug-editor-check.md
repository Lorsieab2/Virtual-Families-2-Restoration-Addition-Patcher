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

The mobile game appears to have the same usable debug-editor surface we can safely enable in the desktop rebuild: the `CDebugger` selector plus waypoint and light-source editors.

Behavior editing and content-map editing may have existed in another internal/dev build, but they are not present as named editor implementations in this mobile release. If we want those features, the safer route is to build new editor functionality around existing systems like `CBehavior`, `CVillagerPlans`, `CContentMap`, and `CContentMapUtil`, rather than trying to register missing editor singletons.
