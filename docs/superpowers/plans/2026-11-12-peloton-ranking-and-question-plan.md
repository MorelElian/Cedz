# Peloton Ranking and Question Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add revealed-only Peloton ranks, comments per ranking participant, a three-person free-answer type, and bounded Peloton lists.

**Architecture:** Extend the JSON payload of ranking answers compatibly, derive public ranks from sent revelations, and add one question type through existing validation/generation paths. The Peloton API gains page-based older revelations while the UI appends them after the initial five.

**Tech Stack:** Flask, SQLite JSON payloads, vanilla JavaScript, CSS, pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-peloton-ranking-and-question-design.md`

## Global Constraints

- Count only `sent` ranking revelations for public averages and ranks.
- Preserve old answers that lack ranking comments.
- Keep existing question answers and URLs compatible.
- Use TDD: observe each added test fail before its implementation.

---

### Task 1: Ranking answer comments and revelations

**Files:** `app.py`, `static/js/questionnaire.js`, `tests/test_api.py`, `tests/test_revelations.py`

- [ ] Add failing tests for persisted per-person comments and recipient-only rendered comments.
- [ ] Validate and persist `participant_comments` with each ranking answer.
- [ ] Render one textarea per ranking item and include its value in the saved answer JSON.
- [ ] Extend ranking revelation content/summary formatting with the recipient comment.
- [ ] Run focused tests and commit.

### Task 2: Revealed-only Peloton rank order

**Files:** `app.py`, `static/js/peloton.js`, `tests/test_revelations.py`

- [ ] Add failing tests where sent positions produce rank `#1` and mean `3.6` independently of unsent rows.
- [ ] Derive discipline/global ranking tables from sent revelations and expose `rank`, `averagePosition`, and `revealedCount`.
- [ ] Render rank prominently and the mean as secondary copy.
- [ ] Run focused tests and commit.

### Task 3: Three-person free answer type

**Files:** `app.py`, `templates/admin.html`, `templates/participant_dashboard.html`, `static/js/questionnaire.js`, `static/js/account.js`, `tests/test_api.py`, `tests/test_revelations.py`

- [ ] Add failing tests for creation, three targets, validation, answer persistence, and three candidate revelations.
- [ ] Add `three_person_free_text` to type validation, target selection, answer validation, candidate generation, admin question creation, and suggestions.
- [ ] Add questionnaire and suggestion labels/examples/placeholders.
- [ ] Run focused tests and commit.

### Task 4: Peloton interaction top five and chronological loading

**Files:** `app.py`, `static/js/peloton.js`, `static/css/app.css`, `tests/test_revelations.py`

- [ ] Add failing tests for interaction ranking by reactions plus comments and paged older revelations.
- [ ] Expose at most five interactive cards and a paged sent-revelation endpoint/result.
- [ ] Add “Charger plus de réponses” with append-only chronological rendering.
- [ ] Run focused tests and commit.

### Task 5: Full verification

**Files:** all modified files

- [ ] Run `node --check` on modified scripts.
- [ ] Run `env PYTHONPATH=. .venv/bin/pytest -q` and `git diff --check`.
- [ ] Review the requirement checklist against the spec and commit the integrated work.
