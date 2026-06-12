# Authoring the career corpus

This folder is the **only** source of truth the server can return. If a fact isn't here, no
client can make the AI say it. Keep it **public-safe**: no secrets, no application tracking,
no private contact details beyond your stated `contact_policy`.

## Layout

```
corpus/
├── profile.yaml          # one file: identity, links, bio, summary templates
├── roles/<id>.yaml       # one file per role/job
├── projects/<id>.yaml    # one file per project
└── skills.yaml           # one file: skills grouped by category
```

## The evidence → bullet model

Each role/project has two lists:

- **`evidence`** — granular, factual statements you can fully stand behind. This is the
  "base list of everything I did." Add approved `metrics` (label/value) only when you've
  vetted the number.
- **`bullets`** — resume-ready phrasings *derived from* evidence. Every bullet lists the
  `source_ids` (evidence ids) it came from.

`assemble_resume` selects and orders these for a query; it never writes new sentences with
new facts. The summary line comes from `profile.summary_templates` with `{headline}`,
`{top_tags}`, and `{name}` filled from corpus values.

## Multiple roles at one company (title progression)

A role is one `(company, title, date-range)` record. To express a progression — e.g. you
joined as Frontend Developer, became Fullstack Developer, then Lead — create **one role file
per title** and give them all the same **`company_id`**:

```yaml
# roles/timeplay-frontend.yaml
id: timeplay-frontend
company_id: timeplay        # <-- shared key
org: TimePlay
title: Frontend Developer
start: "2021-03"
end: "2022-06"
...
```

Each title keeps its own `evidence`/`bullets` (what you did *as* that title). Grouping is a
**render-time** decision:

- `list_roles` returns them flat (each title separately).
- `list_experience` and `assemble_resume` group them under one company header, newest title
  first.
- **Left and came back later?** Use the same `company_id` for both stints. A date gap of
  more than a month automatically splits them into **two separate tenures** (two company
  blocks), so it reads correctly without any extra fields. A continuous promotion stays one
  block.

Roles sharing a `company_id` must use the **same `org`** display name (integrity-checked).

## "About" facets — voice & fact content

Four optional top-level files describe the person rather than a job. The `get_about` tool
returns all four together. Unlike evidence/bullets, these are **not** quantified claims that
cite a source — they are approved by *authorship* (your own words and plain facts) and are
returned **verbatim**. Each item carries a free-text `note`/`body`: that depth is what lets a
host answer with substance instead of a bare list, since the honesty rule forbids it from
inventing backstory. Missing file = that facet is simply empty.

```yaml
# corpus/languages.yaml
- name: Persian (Farsi)
  proficiency: native        # native | fluent | professional | conversational | basic
  note: "My mother tongue — I grew up speaking it at home."

# corpus/interests.yaml
- name: Beach volleyball
  note: "My way to switch the analytical brain off — all flow and reading the other side."

# corpus/education.yaml
- id: march                  # unique id (integrity-checked)
  institution: <school>
  degree: Master of Architecture
  field: Architecture        # optional
  location: <city>           # optional
  start: "2015-09"           # optional, "YYYY-MM"
  end: "2018-06"             # optional
  note: "<thesis focus, honor, etc.>"   # optional

# corpus/principles.yaml
- id: clarity-from-mess      # unique id (integrity-checked)
  title: Hold the mess until one line appears
  body: >-
    Trained as an architect, I sit with a messy, multi-dimensional problem until a single
    clear line resolves it, rather than forcing structure too early.
```

## Integrity rules (enforced by tests / CI)

- Every id (`role`, `project`, `evidence`, `bullet`, `education`, `principle`) is **unique**.
- Every `bullet.source_ids` and `skill.evidence_ids` **resolves** to a real evidence id.
- Every `project.role_id` (if set) **resolves** to a real role.

Run `uv run pytest tests/test_corpus_integrity.py` after editing; CI runs it on every push.

## Conventions

- IDs are short kebab/slug strings (`timeplay`, `tp-e1`, `tp-b3`).
- Dates are `"YYYY-MM"` strings (quote them). Use `end: null` for a current role.
- `tags` drive search and resume tailoring — use a consistent vocabulary
  (e.g. `0-to-1`, `product`, `frontend`, `backend`, `realtime`, `design`, `ai`).
- Content is **public-safe and sanitized**: every claim traces to vetted evidence;
  individuals, internal codenames, and private partner details are generalized.
