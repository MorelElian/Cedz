# Peloton Social Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mobile-first Peloton directory with public participant cards, curated revelations, rankings, reactions, comments, profile walls, and admin moderation.

**Architecture:** Keep social data in SQLite beside the existing participant/revelation data. Flask exposes authenticated JSON APIs for Peloton reads and writes, with ownership checks at every mutation boundary. The participant account consumes a focused `peloton.js` module; admin receives a dedicated Peloton panel and script for curation/moderation.

**Tech Stack:** Flask 3, SQLite, vanilla JavaScript/CSS, pytest.

**Spec:** `docs/superpowers/specs/2026-10-28-peloton-social-design.md`

## Global Constraints

- Keep Garmin, OAuth, connected-device data, and health data out of scope.
- Keep exactly four participant tabs: Accueil, Dossiers, Peloton, Profil.
- `Dossiers` combines Révélations and Mes réponses through a secondary selector.
- Reactions are public and nominative: `J'avoue`, `N'importe quoi`, or a participant-defined short label.
- One participant has at most one reaction per target and may update or remove it.
- Ranking votes accept reactions only; featured revelations accept reactions and comments.
- Profile wall posts are public to authenticated participants immediately.
- The administrator chooses and orders at most five sent revelations for each participant.
- Escape all user-provided text when rendering and enforce CSRF on mutations.

---

### Task 1: Persist social data and participant taglines

**Files:**
- Modify: `app.py` (`init_db`, migration block, `participant_payload`)
- Test: `tests/test_api.py`

**Interfaces:**
- Produces `participants.profile_tagline TEXT`.
- Produces `profile_wall_posts`, `social_comments`, `social_reactions`, and `peloton_featured_revelations` tables.
- Produces profile payload key `profileTagline`.

- [ ] **Step 1: Write failing migration and payload tests**

```python
def test_participant_payload_exposes_profile_tagline(client, app):
    participant = client.get('/api/participants').get_json()['participants'][0]
    with sqlite3.connect(app.config['DATABASE']) as db:
        db.execute("UPDATE participants SET profile_tagline=? WHERE id=?", ('Le vélo est une religion.', participant['id']))
        db.commit()
    refreshed = client.get('/api/participants').get_json()['participants'][0]
    assert refreshed['profileTagline'] == 'Le vélo est une religion.'
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_participant_payload_exposes_profile_tagline -q`

Expected: FAIL because the column/payload key does not exist.

- [ ] **Step 3: Add additive schema migrations**

Create tables with foreign keys and indexes:

```sql
CREATE TABLE IF NOT EXISTS profile_wall_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_participant_id INTEGER NOT NULL REFERENCES participants(id),
  author_participant_id INTEGER NOT NULL REFERENCES participants(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  revelation_id INTEGER NOT NULL REFERENCES revelations(id),
  author_participant_id INTEGER NOT NULL REFERENCES participants(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS social_reactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_type TEXT NOT NULL CHECK(target_type IN ('revelation','ranking_answer')),
  target_id INTEGER NOT NULL,
  author_participant_id INTEGER NOT NULL REFERENCES participants(id),
  kind TEXT NOT NULL CHECK(kind IN ('agree','disagree','custom')),
  custom_label TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(target_type,target_id,author_participant_id)
);
CREATE TABLE IF NOT EXISTS peloton_featured_revelations (
  profile_participant_id INTEGER NOT NULL REFERENCES participants(id),
  revelation_id INTEGER NOT NULL REFERENCES revelations(id),
  position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 5),
  created_at TEXT NOT NULL,
  PRIMARY KEY(profile_participant_id, position),
  UNIQUE(profile_participant_id, revelation_id)
);
```

Add `profile_tagline` with `ALTER TABLE participants ADD COLUMN` only when absent. Add indexes for wall profile/date, comments revelation/date and reactions target.

- [ ] **Step 4: Extend `participant_payload`**

Expose `profileTagline` from `profile_tagline`, defaulting to `None`; do not expose private account fields on public Peloton payloads.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_api.py
git commit -m "feat: add peloton social data model"
```

### Task 2: Participant profile tagline API

**Files:**
- Modify: `app.py` (`register_account_api`)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes `participants.profile_tagline` from Task 1.
- Produces `PATCH /api/account/profile` accepting `{ "profileTagline": string }`.

- [ ] **Step 1: Write failing ownership and validation tests**

```python
def test_participant_can_update_short_profile_tagline(client):
    participant = client.get('/api/participants').get_json()['participants'][0]
    authenticate_as(client, participant['id'])
    csrf = client.get('/api/account/dashboard').get_json()['csrfToken']
    response = client.patch('/api/account/profile', json={'profileTagline': 'Toujours en danseuse.'}, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200
    assert response.get_json()['profileTagline'] == 'Toujours en danseuse.'
    assert client.patch('/api/account/profile', json={'profileTagline': 'x' * 121}, headers={'X-CSRF-Token': csrf}).status_code == 400
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_participant_can_update_short_profile_tagline -q`

- [ ] **Step 3: Implement `PATCH /api/account/profile`**

Require participant login and CSRF. Strip the text, accept empty text as `NULL`, reject text longer than 120 characters, update only `g.current_participant['id']`, then return `participant_payload(..., private=True)`.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_participant_can_update_short_profile_tagline -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_api.py
git commit -m "feat: let participants set peloton taglines"
```

### Task 3: Peloton read model and rankings detail

**Files:**
- Modify: `app.py` (Peloton query helpers and account APIs)
- Test: `tests/test_revelations.py`

**Interfaces:**
- Produces `GET /api/peloton` with participant summaries.
- Produces `GET /api/peloton/<participant_id>` with `{participant, rankings, featuredRevelations, wallPosts, mostCommented}`.
- `rankings` contains named ranking-vote details only for sent/public ranking answers.

- [ ] **Step 1: Write failing public-read tests**

```python
def test_peloton_profile_shows_rankings_and_only_curated_revelations(client):
    csrf = admin_login(client)
    people = client.get('/api/admin/participants', headers=csrf).get_json()['participants']
    profile_id = people[0]['id']
    # Seed or send two revelations, curate exactly one through the admin API in Task 6.
    participant_login(client, people[1]['displayName'])
    profile = client.get(f'/api/peloton/{profile_id}').get_json()
    assert profile['participant']['id'] == profile_id
    assert set(profile['rankings']) == {'global', 'swim', 'bike', 'run'}
    assert len(profile['featuredRevelations']) <= 5
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_revelations.py::test_peloton_profile_shows_rankings_and_only_curated_revelations -q`

- [ ] **Step 3: Add query helpers**

Implement helpers that:

1. return active participants with public payload and reaction/comment counts;
2. reuse existing ranking aggregation for global/swim/bike/run summaries;
3. retrieve named ranking answers targeting the profile, constrained to public/sent source data;
4. retrieve only `peloton_featured_revelations` joined to sent revelations, in `position` order;
5. retrieve wall posts with author payload and interaction counts;
6. retrieve up to three highest-commented featured revelations or wall posts for `mostCommented`.

- [ ] **Step 4: Add authenticated read endpoints**

Protect both endpoints with `@participant_required`. Return no raw emails, passwords, tokens, unpublished revelations, or unsent answers.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_revelations.py::test_peloton_profile_shows_rankings_and_only_curated_revelations -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_revelations.py
git commit -m "feat: expose public peloton profiles"
```

### Task 4: Reactions, revelation comments, and profile walls

**Files:**
- Modify: `app.py` (social mutation endpoints and validation helpers)
- Test: `tests/test_revelations.py`

**Interfaces:**
- Produces `PUT /api/peloton/reactions` with `{targetType,targetId,kind,customLabel?}`.
- Produces `DELETE /api/peloton/reactions/<target_type>/<target_id>`.
- Produces `POST /api/peloton/revelations/<revelation_id>/comments` and `DELETE /api/peloton/comments/<comment_id>`.
- Produces `POST /api/peloton/<participant_id>/wall-posts` and `DELETE /api/peloton/wall-posts/<post_id>`.

- [ ] **Step 1: Write failing interaction tests**

```python
def test_peloton_reaction_is_named_unique_and_updatable(client):
    # Authenticate a participant and target a sent revelation.
    first = client.put('/api/peloton/reactions', json={'targetType':'revelation','targetId':1,'kind':'agree'}, headers=participant_csrf)
    second = client.put('/api/peloton/reactions', json={'targetType':'revelation','targetId':1,'kind':'custom','customLabel':'Bien envoyé'}, headers=participant_csrf)
    assert first.status_code == 200 and second.status_code == 200
    profile = client.get('/api/peloton/1').get_json()
    mine = [item for item in profile['featuredRevelations'][0]['reactions'] if item['author']['id'] == participant_id]
    assert mine == [{'kind':'custom', 'customLabel':'Bien envoyé', 'author': {'id': participant_id, 'displayName': name}}]

def test_peloton_rejects_comments_on_non_featured_or_non_sent_revelations(client):
    assert client.post('/api/peloton/revelations/999/comments', json={'body':'Non.'}, headers=participant_csrf).status_code == 404
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_revelations.py -k peloton -q`

- [ ] **Step 3: Implement strict validation and authorization**

Validate `kind` against `agree`, `disagree`, `custom`; require a 1–40 character `customLabel` only for `custom`; reject it for fixed kinds. Allow `ranking_answer` targets only when the target is a ranking answer and the requester is a participant. Allow revelation comments only for currently featured sent revelations. Limit wall posts/comments to 1–800 characters. On deletion, require author ownership; later admin moderation is added in Task 6.

- [ ] **Step 4: Return normalized social payloads**

Every returned reaction includes public author id/display name, kind and optional label. Every comment/wall post includes id, body, timestamps and author. Sort newest first for walls/comments; update reactions in place through the unique constraint.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_revelations.py -k peloton -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_revelations.py
git commit -m "feat: add peloton social interactions"
```

### Task 5: Participant UI — four tabs, Dossiers, Profile tagline, Peloton

**Files:**
- Modify: `templates/participant_dashboard.html`
- Modify: `static/js/account.js`
- Create: `static/js/peloton.js`
- Modify: `static/css/app.css`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes Task 2 profile API and Task 3–4 Peloton APIs.
- Produces four accessible account tabs and a responsive Peloton experience.

- [ ] **Step 1: Write failing account-page structure tests**

```python
def test_account_page_has_four_tabs_and_peloton_mount(client):
    participant = client.get('/api/participants').get_json()['participants'][0]
    authenticate_as(client, participant['id'])
    page = client.get('/compte').get_data(as_text=True)
    assert 'data-account-tab="peloton"' in page
    assert page.count('data-account-tab=') == 4
    assert 'data-peloton-app' in page
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_account_page_has_four_tabs_and_peloton_mount -q`

- [ ] **Step 3: Restructure participant navigation**

Keep `Accueil`, replace separate Révélations/Mes réponses tabs with `Dossiers`, add `Peloton`, retain `Profil`. In Dossiers render a two-button accessible selector for `Révélations` and `Mes réponses`; retain replies received under Profile. Add tagline editor under Profile with saved/error states.

- [ ] **Step 4: Implement `peloton.js`**

Load summaries, default to the signed-in participant, and load the selected profile. Render:

```text
desktop: [vertical portrait rail] [public fiche]
mobile:  [horizontal sticky portrait rail]
         [public fiche]
```

Render rank cards first, then `<details>` named votes, curated revelation cards with reactions/comments, profile-wall composer/feed, and a three-card `Les plus commentés` block. Escape all dynamic values using the existing escaping convention.

- [ ] **Step 5: Implement interaction states**

Use delegated submit/click handlers for reactions, comment creation/deletion, wall creation/deletion and profile selection. Disable only the active control during requests, update the selected profile from API responses, and show inline errors rather than browser alerts.

- [ ] **Step 6: Add responsive styles**

Create `.peloton-layout`, `.peloton-rail`, `.peloton-fiche`, `.rank-detail`, `.reaction-row`, `.comment-thread`, and `.wall-post` styles. At mobile width make the rail horizontal with `overflow-x:auto`, keep portrait targets at least 44px, and never horizontally scroll the fiche body.

- [ ] **Step 7: Run focused tests and syntax checks**

Run:

```bash
.venv/bin/python -m pytest tests/test_api.py::test_account_page_has_four_tabs_and_peloton_mount -q
node --check static/js/account.js
node --check static/js/peloton.js
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add templates/participant_dashboard.html static/js/account.js static/js/peloton.js static/css/app.css tests/test_api.py
git commit -m "feat: add mobile-first peloton participant UI"
```

### Task 6: Admin curation and moderation

**Files:**
- Modify: `app.py` (`register_admin_api`)
- Modify: `templates/admin.html`
- Create: `static/js/admin_peloton.js`
- Modify: `static/css/app.css`
- Test: `tests/test_revelations.py`

**Interfaces:**
- Produces `GET /api/admin/peloton/<participant_id>` and `PUT /api/admin/peloton/<participant_id>/featured-revelations`.
- Produces admin delete endpoints for wall posts, comments and reactions.
- Consumes featured-revelation data from Task 1.

- [ ] **Step 1: Write failing curation/moderation tests**

```python
def test_admin_can_choose_ordered_featured_revelations_and_moderate_social_content(client):
    csrf = admin_login(client)
    response = client.put('/api/admin/peloton/1/featured-revelations', json={'revelationIds':[9, 7, 5]}, headers=csrf)
    assert response.status_code == 200
    assert response.get_json()['featuredRevelationIds'] == [9, 7, 5]
    assert client.delete('/api/admin/peloton/wall-posts/1', headers=csrf).status_code == 200
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_revelations.py::test_admin_can_choose_ordered_featured_revelations_and_moderate_social_content -q`

- [ ] **Step 3: Implement curation endpoint transactionally**

Accept 0–5 unique revelation ids. Verify every revelation is `sent` and its recipient is `participant_id`. Delete the profile’s existing feature rows then insert the submitted list at positions 1–5 in one transaction. Return ids in order.

- [ ] **Step 4: Implement moderation deletes**

Provide admin-only deletion for any wall post, comment or reaction. Return `{deleted: true}` or a 404. Do not delete the associated sent revelation or ranking answer.

- [ ] **Step 5: Build the admin Peloton panel**

Add a Peloton admin tab with a profile selector, sent-revelation checkboxes/order controls limited to five, a save action, and separate compact lists for wall/comments/reactions with moderation delete buttons. Use the existing CSRF/API conventions and show the current selection first.

- [ ] **Step 6: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_revelations.py::test_admin_can_choose_ordered_featured_revelations_and_moderate_social_content -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/admin.html static/js/admin_peloton.js static/css/app.css tests/test_revelations.py
git commit -m "feat: curate and moderate peloton profiles"
```

### Task 7: End-to-end regression and mobile smoke check

**Files:**
- Modify: `tests/test_api.py` and `tests/test_revelations.py` only if coverage gaps are found.

**Interfaces:**
- Consumes all prior task APIs and UI mounts.
- Produces final regression evidence.

- [ ] **Step 1: Add authorization regression cases**

Cover unauthenticated Peloton read/mutations returning 401, participant attempts to delete another author’s content returning 403, invalid custom labels returning 400, and inactive participants excluded from the portrait rail.

- [ ] **Step 2: Run full Python suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS with no regressions.

- [ ] **Step 3: Run JavaScript syntax checks**

Run:

```bash
node --check static/js/account.js
node --check static/js/peloton.js
node --check static/js/admin_peloton.js
```

Expected: all commands exit 0.

- [ ] **Step 4: Perform responsive browser smoke check**

Use the project Playwright workflow to sign in, open Peloton, select two profiles, submit a wall post, submit/change a reaction, open a ranking detail, then repeat at a 390px viewport. Capture one desktop and one mobile screenshot in `output/playwright/` only if needed for review.

- [ ] **Step 5: Commit final verification fixes if any**

```bash
git add app.py templates static tests
git commit -m "test: verify peloton social flows"
```
