# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Two Claude Code custom skills for supply chain (SCM) domain: knowledge curation and PRD production. All content is Markdown, YAML, and shell/Python/JS scripts. Test suite: `python -m pytest tests/ -v`.

Versioning follows CalVer (`YYYY.MM.PATCH`), e.g. `v2026.03.0`.

## Architecture: Two Skills, Producer-Consumer

**Skill 1 — `scm-knowledge-curator`** (knowledge producer): Journalist-style interviews → structured knowledge cards in `knowledge-base/`.

**Skill 2 — `scm-prd-workflow`** (knowledge consumer): PRD production pipeline with three modes:
- **Autonomous** (Stage A-D): 10-chapter PRD, 5-9 rounds, optional prototype generation (Stage D)
- **Interactive** (Phase 1-4+): 10-chapter PRD, 18-33 rounds, step-by-step confirmation
- **Lite** (Stage L1-L3): 7-chapter PRD, 2-5 rounds, for simple changes

Optional prototype integration (Stage D / post-review) produces `prototype-design.md` + `prototype/bundle.html` via `web-artifacts-builder` skill for UI-heavy requirements.

## Key File Roles

- `SKILL.md` — skill definition (system prompt). Changes directly affect behavior.
- `references/` — operational guides loaded on-demand per phase (interview framework, phase instructions, diagram patterns, prototype planning, etc.)
- `templates/` — output templates filled when generating artifacts (PRD templates, prototype brief/design templates)
- `scripts/` — automation:
  - `diagram_core.py` — shared layout engine, validation, color constants (imported by yaml2drawio + yaml2svg)
  - `yaml2drawio.py` / `yaml2svg.py` — YAML DSL → draw.io XML / SVG+PNG
  - `md2docx.mjs` (JS, recommended) / `md2docx.py` (Python, fallback) — Word generation
  - `check-prd-consistency.py` — ID/terminology validation (supports custom `chapter_id_map` in front matter)
  - `check-skill-consistency.py` — skill file cross-reference + gate ID integration checks
  - `export-diagrams.py` — batch diagram export (supports `allow_remote_render` config flag)
  - `package.json` — Node.js dependency management (`npm install` in scripts/ for docx library)
- `tests/` — pytest test suite (41 tests) covering diagram generation, PRD consistency, knowledge consistency

## Runtime Outputs (gitignored)

- `knowledge-base/` — domain cards, `_index.md`, `glossary.yaml`
- `requirements/REQ-{date}-{name}/` — `intake.md`, `clarification.md`, `PRD-*.md`, `PRD-*.docx`, `review-report.md`, `knowledge-discoveries.md`, `prototype-design.md` (optional), `diagrams/`, `prototype/bundle.html` (optional)

## Core Design Principles

1. **No fabrication** — never invent business details; ask to confirm
2. **Challenge first** — question unreasonable requirements
3. **Evidence-driven** — cite sources; label web-sourced practices
4. **Authorized writes only** — AI suggestions marked `[建议]`, approved before entering PRD
5. **Incremental capture** — new knowledge → `knowledge-discoveries.md` → importable to knowledge base
6. **Cross-requirement consistency** — scan existing PRDs for conflicts when starting new requirements

## Conventions

- Knowledge cards: `domain-{abbrev}.md` naming (English, lowercase, hyphen-separated)
- Quality annotations: `[待确认]`, `[推测]`, `[过时?]`, `[矛盾]`
- Diagrams: Mermaid for state/sequence/simple flows; YAML DSL → draw.io for swimlanes and complex flows (>12 nodes)
- Primary language: **Chinese (Simplified)**; file names and code identifiers in English
