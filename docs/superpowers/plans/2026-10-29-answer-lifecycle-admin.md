# Answer Lifecycle and Admin Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every answer a dated revelation source and expose all sent and remaining revelations per participant to admins.

**Architecture:** `imported_answers` stays canonical. Bonus writes use the same timestamped ledger before generating candidates. Inventory endpoints query the existing revelations table by recipient and status; a desktop admin screen lazily loads every card for the selected participant.

**Tech Stack:** Flask, SQLite, vanilla JavaScript, CSS, pytest.

**Spec:** `docs/superpowers/specs/2026-10-29-answer-lifecycle-admin-design.md`

## Global Constraints

- Preserve sent revelations and make answer writes atomic.
- Use `source_created_at` as the canonical answer timestamp.
- Remaining means only `candidate` and `in_review`.
- Use `apply_patch` for repository edits.
- Start each backend behavior change with a failing pytest.

---

### Task 1: Timestamped bonus answer ledger

**Files:**
- Modify: `app.py: init_db`, `app.py: answer_daily_question`
- Test: `tests/test_revelations.py`

**Interfaces:**
- Produces an `imported_answers` row keyed `daily:<daily_question_id>` with `source_created_at == answered_at`.
- Produces candidate revelations in the same transaction.

- [ ] **Step 1: Write the failing test**

```python
def test_daily_answer_is_timestamped_and_generates_revelation_candidates(client, app):
    # Answer an active bonus question, then assert its linked imported row
    # has source_created_at == daily_questions.answered_at and candidates exist.
```

- [ ] **Step 2: Verify red**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k daily_answer_is_timestamped`

Expected: failure because the imported row has no source timestamp.

- [ ] **Step 3: Implement the minimal write and repair migration**

```python
db.execute(
    "INSERT INTO imported_answers(..., source_created_at, imported_at, updated_at) VALUES (..., ?, ?, ?)",
    (..., now, now, now),
)
db.execute(
    "UPDATE imported_answers SET source_created_at=COALESCE((SELECT answered_at FROM daily_questions WHERE imported_answer_id=imported_answers.id), imported_at) WHERE source_key LIKE 'daily:%' AND source_created_at IS NULL"
)
```

- [ ] **Step 4: Verify green and commit**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k daily_answer_is_timestamped`

```bash
git add app.py tests/test_revelations.py
git commit -m "Timestamp daily answer imports"
```

### Task 2: Participant revelation inventory API

**Files:**
- Modify: `app.py: register_admin_api`, `app.py: revelation payload helpers`
- Test: `tests/test_revelations.py`

**Interfaces:**
- Produces `GET /api/admin/revelation-inventory` with participant counters.
- Produces `GET /api/admin/revelation-inventory/<participant_id>` with complete `sent` and `remaining` lists.

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_admin_revelation_inventory_separates_sent_and_remaining(client):
    # Seed sent, in_review and candidate rows for one recipient.
    # Assert sent is newest-first and remaining contains the two unsent statuses.
```

- [ ] **Step 2: Verify red**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k revelation_inventory`

Expected: 404 because the inventory routes do not exist.

- [ ] **Step 3: Add serializer and routes**

```python
def revelation_inventory_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = revelation_payload(row, admin=True)
    payload["answerSummary"] = revelation_answer_summary(row)
    return payload

@app.get("/api/admin/revelation-inventory/<int:participant_id>")
@admin_required
def admin_revelation_inventory_person(participant_id: int):
    # Query sent and candidate/in_review using the documented order.
```

- [ ] **Step 4: Verify green and commit**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k revelation_inventory`

```bash
git add app.py tests/test_revelations.py
git commit -m "Expose participant revelation inventory"
```

### Task 3: Reliable import feedback and refresh

**Files:**
- Modify: `static/js/admin_revelations.js`
- Modify: `static/js/admin.js`
- Test: `tests/test_revelations.py`

**Interfaces:**
- Consumes `{imported, updated, generated}` from `POST /api/admin/import-answers`.
- Emits `cedz:answers-imported` after a successful import.

- [ ] **Step 1: Write the import result test**

```python
def test_import_answers_reports_created_updated_and_generated(client, app):
    # Import the supplied JSON twice and assert the first and second result counters.
```

- [ ] **Step 2: Verify current contract**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k import_answers_reports`

Expected: failure until the stable result assertions exist.

- [ ] **Step 3: Refresh every dependent admin view**

```javascript
status.textContent = `${result.imported} importées · ${result.updated} mises à jour · ${result.generated} candidats créés.`;
await loadAll();
window.dispatchEvent(new Event('cedz:answers-imported'));
```

- [ ] **Step 4: Verify and commit**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k import_answers_reports && node --check static/js/admin.js && node --check static/js/admin_revelations.js`

```bash
git add app.py static/js/admin.js static/js/admin_revelations.js tests/test_revelations.py
git commit -m "Refresh admin after answer imports"
```

### Task 4: Desktop revelation inventory UI

**Files:**
- Modify: `templates/admin.html`
- Create: `static/js/admin_inventory.js`
- Modify: `static/css/app.css`

**Interfaces:**
- Consumes both inventory routes.
- Reloads when `cedz:answers-imported` is received.

- [ ] **Step 1: Add the tab and containers**

```html
<button type="button" aria-selected="false" data-tab="inventory">Suivi révélations</button>
<section class="admin-panel" data-panel="inventory" hidden data-revelation-inventory>
  <nav data-inventory-people aria-label="Participants"></nav>
  <div data-inventory-detail></div>
</section>
```

- [ ] **Step 2: Implement lazy selection**

```javascript
async function loadParticipant(participantId) {
  selectedId = participantId;
  renderPeople();
  renderDetail(await api(`/api/admin/revelation-inventory/${participantId}`));
}
```

- [ ] **Step 3: Render every card and responsive layout**

```css
.inventory-layout { display:grid; grid-template-columns:240px minmax(0,1fr); }
.inventory-columns { display:grid; grid-template-columns:1fr 1fr; }
@media (max-width:800px) { .inventory-layout,.inventory-columns { grid-template-columns:1fr; } }
```

- [ ] **Step 4: Verify and commit**

Run: `node --check static/js/admin_inventory.js && env PYTHONPATH=. .venv/bin/pytest -q`

```bash
git add templates/admin.html static/js/admin_inventory.js static/css/app.css
git commit -m "Add admin revelation inventory"
```

### Task 5: Peloton response rendering hardening

**Files:**
- Modify: `app.py: peloton payload`
- Modify: `static/js/peloton.js`
- Modify: `static/css/app.css`
- Test: `tests/test_revelations.py`

**Interfaces:**
- Uses server fallback content and typed answer summaries.
- Never renders raw JSON or a silent blank card.

- [ ] **Step 1: Write the failing fallback-content test**

```python
def test_peloton_featured_revelation_has_non_empty_fallback_content(client, app):
    # Select a sent revelation with final_content NULL and assert finalContent is populated.
```

- [ ] **Step 2: Verify red, implement and verify green**

Run: `env PYTHONPATH=. .venv/bin/pytest -q tests/test_revelations.py -k peloton_featured_revelation_has_non_empty`

```javascript
const answer = item.finalContent || 'Réponse indisponible.';
```

Run: `env PYTHONPATH=. .venv/bin/pytest -q && node --check static/js/peloton.js`

- [ ] **Step 3: Commit**

```bash
git add app.py static/js/peloton.js static/css/app.css tests/test_revelations.py
git commit -m "Harden Peloton revelation rendering"
```
