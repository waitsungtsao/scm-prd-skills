# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains two Claude Code custom skills for supply chain (SCM) domain knowledge management and PRD (Product Requirements Document) production. It is a **documentation-only** project — no build, lint, or test commands. All content is Markdown, YAML, and one shell script.

Versioning follows CalVer (`YYYY.MM.PATCH`), e.g. `v2026.03.0`.

## Architecture: Two Skills, Producer-Consumer

**Skill 1 — `scm-knowledge-curator`** (knowledge producer): Conducts structured "journalist-style" interviews to capture business knowledge into `knowledge-base/` as domain cards, glossary, and an index.

**Skill 2 — `scm-prd-workflow`** (knowledge consumer): 4-phase PRD pipeline (Intake → Clarify → Write → Review) that reads from the knowledge base and outputs complete requirement packages under `requirements/REQ-{date}-{name}/`.

The skills share context within a single conversation but are intentionally separate so knowledge curation and PRD production can evolve independently. Phase state is passed via standardized Markdown files with YAML front matter.

## Key File Roles

- `SKILL.md` in each skill directory is the **skill definition** — the system prompt Claude uses when the skill is triggered. Changes here directly affect skill behavior.
- `references/` files are **operational guides** read by the skill at runtime (interview framework, phase instructions, diagram patterns).
- `templates/` files are **output templates** the skill fills in when generating artifacts.
- `scm-prd-workflow/scripts/init_workspace.sh` bootstraps workspace directories and config.

## Runtime Outputs (gitignored)

- `knowledge-base/` — knowledge cards, `_index.md`, `glossary.yaml`
- `requirements/` — per-requirement folders with `intake.md`, `clarification.md`, `PRD-*.md`, `review-report.md`, `diagrams/*.mermaid`
- `.scm-prd-config.yaml` — optional project-level config

## Core Design Principles (enforced across both skills)

1. **No fabrication** — never invent business details; always ask the user to confirm
2. **Challenge first** — question unreasonable requirements rather than complying
3. **Evidence-driven** — cite sources for recommendations; label web-sourced practices
4. **Authorized writes only** — AI suggestions must be marked `[建议]` and approved before entering PRD text
5. **Incremental capture** — new business knowledge discovered during PRD work should be flagged for addition to the knowledge base

## Conventions

- Knowledge card files use `domain-{abbrev}.md` naming (lowercase, hyphen-separated, no Chinese filenames)
- Quality annotations: `[待确认]` (unconfirmed), `[推测]` (inferred), `[过时?]` (possibly outdated), `[矛盾]` (contradictory)
- All flowcharts use Mermaid syntax, saved as standalone `.mermaid` files; max ~20 nodes per diagram
- PRD documents require dual-format output (Markdown + Word) unless the user opts out
- The primary language for all skill content and outputs is **Chinese (Simplified)**; file names and code identifiers use English
