# SOP — Standard Operating Procedures

Gold-standard procedure graphs used as ground truth for surgical compliance analysis. Each procedure is defined as a directed graph of steps (nodes) with sequential/conditional edges, derived from published medical literature and WHO guidelines.

## Structure

```
SOP/data/
├── 9789241598590_eng_Checklist.pdf    # WHO Surgical Safety Checklist
├── abcess_data/
│   ├── incision_drainage_abscess.json # Procedure graph
│   ├── supabase_seed_abscess.sql      # DB seed script
│   └── *.pdf                          # Source literature
├── appendectomy_data/
│   ├── laparoscopic_appendectomy.json
│   └── *.pdf
├── c-section_data/
│   ├── cesarean_section.json
│   └── *.pdf
└── lap_chole_data/
    ├── laparoscopic_cholecystectomy.json
    └── *.pdf
```

## Procedures Available

| Procedure | Nodes | Source Documents |
|---|---|---|
| Incision & Drainage of Abscess | 16 (13 mandatory) | WHO Checklist, BMC Medical Education, 2025 Technique Handout |
| Laparoscopic Cholecystectomy | 20+ | WHO Checklist, WJGS, Surgical Endoscopy |
| Cesarean Section | 15+ | Cochrane Review |
| Laparoscopic Appendectomy | 15+ | Surgical Endoscopy |

## Graph Format

Each JSON file contains:

- **`procedure`** — ID, name, version, source documents
- **`nodes`** — each step with: `id`, `name`, `phase`, `mandatory`, `safety_critical`, `actors`, `required_tools`, `preconditions`
- **`edges`** — directed edges (`from` → `to`) typed as `sequential` or `conditional`

These graphs are loaded by the ScitePipeline comparator to detect missing, out-of-order, and skipped safety-critical steps.

