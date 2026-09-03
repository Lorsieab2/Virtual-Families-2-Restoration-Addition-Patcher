# New furniture art

Sprite sheets for furniture this patcher adds that the base game does not
have. Each is a two-frame sheet in the same layout as its stock counterpart:
frame 1 is the north-west orientation, frame 2 the north-east one.

| file | size | modelled on |
| --- | --- | --- |
| `ExerciseBikeStd.png` | 202x97 | `TreadmillStd.png` (210x120) |
| `HomeGymSystemStd.png` | 259x129 | `YogaGearStd.png` (248x105) |
| `PingPongTableStd.png` | 336x121 | `PoolTableStd.png` (314x142) | not registered -- the Ping-Pong Table was dropped; the art is kept in case it is wanted again |

Digests are recorded in `SHA256SUMS.json` and checked by the build, so a
corrupted or replaced sprite fails rather than shipping quietly.
