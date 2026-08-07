# Note templates

Starting points for campaign wiki pages. A GM installs the ones they want, then
picks one from **Templates** in the campaign wiki to create a pre-structured
page instead of a blank one.

Each template is a directory named after its `id`, holding a manifest and the
markdown page it creates. Templates are filed under a folder per game system:

```
templates/
├── dnd-5e/
│   └── 5e-spell/
│       ├── 5e-spell.yml   # required — the manifest
│       ├── 5e-spell.md    # required — the page body, with frontmatter
│       └── README.md      # optional
└── draw-steel/
    └── ds-encounter/
        ├── ds-encounter.yml
        └── ds-encounter.md
```

The grouping folders are for humans browsing the repo — Grimoire groups the
template browser by the manifest's `category` and `system`, not by directory. A
template in a system folder still needs its `system:` key set.

See [`../docs/note-templates.md`](../docs/note-templates.md) for the authoring
reference.

## Available templates

| Template | System | Category | Description |
| --- | --- | --- | --- |
| [NPC](dnd-5e/5e-npc/) | D&D 5e | Characters | Statblock, motivation, and plot hooks |
| [Magic Item](dnd-5e/5e-magic-item/) | D&D 5e | Items | Rarity, attunement, properties, charges |
| [Spell](dnd-5e/5e-spell/) | D&D 5e | Spells | Level, school, casting time, range, effect |
| [Encounter](draw-steel/ds-encounter/) | Draw Steel | Encounters | Victories, terrain, enemy roster, objectives |
| [Montage Test](draw-steel/ds-montage-test/) | Draw Steel | Encounters | Objective, challenges, outcomes |
| [Negotiation](draw-steel/ds-negotiation/) | Draw Steel | Encounters | Interest, patience, motivations, pitfalls |
