# Explorer Grouping Prototype

This is a text-only prototype for the left Explorer dock hierarchy. It uses the
current catalog served at `http://127.0.0.1:8765/catalog.json` on 2026-05-06.

The goal is to test whether grouping makes semantic claims that are true. A tree
must distinguish ownership, compatibility, runtime usage, archive containment,
and semantic layout.

## Catalog Frame

```text
LBA2 Evidence Workbench
[Search assets, ids, source, usage...]

[Kind] [Archive] [Status] [Usage]

22659 assets
573 models  2082 animations  720 sprites  222 scenes  19062 resources
28128 reverse usage refs across 2361 used assets

Sort: Evidence relevance
View: Semantic | Archive
```

## Semantic View

```text
Models (573)
  BODY.HQR:2  Twinsen with tunic model                         DECODED_ONLY
    Geometry
      188 vertices  281 polygons  19 bones  5 spheres  15 lines
    Compatible animations (32)
      ANIM.HQR:2   Back up                                     compatible
      ANIM.HQR:30  Generic animation 53                        compatible
      ANIM.HQR:35  Generic animation 58                        compatible
      ANIM.HQR:46  Generic animation 63, Generic animation 78  compatible
      ANIM.HQR:48  Generic animation 65                        compatible
      ANIM.HQR:49  Lightning                                   compatible
      ANIM.HQR:56  Burning                                     compatible
      ANIM.HQR:57  Generic animation 69                        compatible
      ... 24 more
    Scene usages
      none known for BODY.HQR:2

  BODY.HQR:29  Piece of flying saucer model                     DECODED_ONLY
    Scene usages (455)
      SCENE.HQR:2 object 2   body       matched scene GenBody to File3D body generic id
      ... 454 more

Sprites (720)
  ANIM3DS range: COQU                                           33 frames
    Source frames: ANIM3DS.HQR:0-32
    ANIM3DS.HQR:0   COQU sprite frame 0                         frame 0
    ANIM3DS.HQR:1   COQU sprite frame 1                         frame 1
    ANIM3DS.HQR:2   COQU sprite frame 2                         frame 2
    ANIM3DS.HQR:3   COQU sprite frame 3                         frame 3
    ANIM3DS.HQR:4   COQU sprite frame 4                         frame 4
    ... 28 more

Animations (2082)
  ANIM.HQR:2  Back up                                           DECODED_ONLY
    Compatible bodies
      BODY.HQR:1
      BODY.HQR:2
      BODY.HQR:3
      BODY.HQR:4
      BODY.HQR:5
      BODY.HQR:6
      BODY.HQR:7
      BODY.HQR:8
      ... more compatible body ids
    Scene/script references
      shown as reverse links, not as children owned by this animation

Scenes (222)
  SCENE.HQR:2  Scene 1
    Object 2
      body: BODY.HQR:29  Piece of flying saucer model
      rule: matched scene GenBody to File3D body generic id

Resources (19062)
  Background brick graphics (17903)
  Audio samples (606)
  Background grid maps (148)
  Text order tables (84)
  Text payload banks (84)
  Indexed screens 640x480 (39)
  Screen palettes (39)
  Smacker videos (33)
  Background GRM fragments (30)
  Background block tables (18)
```

## Archive View

```text
Archives (15)
  BODY.HQR
    BODY.HQR:2  Twinsen with tunic model
      Links
        Compatible animations (32)
        Scene usages: none known
    BODY.HQR:29  Piece of flying saucer model
      Links
        Scene usages (455)

  ANIM.HQR
    ANIM.HQR:2  Back up
      Links
        Compatible bodies
        Scene/script references

  ANIM3DS.HQR
    Range COQU (0-32)
      ANIM3DS.HQR:0
      ANIM3DS.HQR:1
      ANIM3DS.HQR:2
      ...
```

## UX Verdict

The tree should not be one universal hierarchy.

Recommended canonical behavior:

- Default to `Semantic` view.
- Keep `Archive` as an alternate grouping, because archive identity is still
  important evidence.
- Models may expand to `Compatible animations` and `Scene usages`, but those
  groups must be labeled as links, not ownership.
- Sprites should be grouped by range/frame because frame adjacency is part of
  the falsification task.
- Animations should remain first-class assets with reverse links to compatible
  bodies.
- Scenes should be object/usage first.
- Resources should be grouped by semantic layout because the raw list is too
  large and archive identity is usually less useful than payload kind.

## Open Design Risk

`BODY.HQR:2` currently has no known reverse scene usage in the catalog, while
other models have hundreds. The UI must handle empty relationship groups without
making the selected asset look broken. For empty groups, use a single compact
line such as `No known scene usages`, not a blank expandable section.
