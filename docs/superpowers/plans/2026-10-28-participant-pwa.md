# Participant PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a participant-only app navigation, installable PWA, and Web Push notifications for revelations and bonus questions.

**Architecture:** Keep the Flask-rendered participant page as the application shell and switch content panes client-side with URL hashes. Serve a root-scoped service worker that caches only immutable public assets. Store per-device push subscriptions in SQLite and invoke Web Push as a best-effort side effect after stateful email/revelation actions commit.

**Tech Stack:** Flask, SQLite, vanilla JavaScript/CSS, Web App Manifest, Service Worker, Web Push/VAPID, pytest.

**Spec:** `docs/superpowers/specs/2026-10-28-participant-pwa-design.md`

## Global Constraints

- Participant content, API JSON, session data and admin pages must never be service-worker cached.
- Notifications require an explicit participant click after first login.
- VAPID private material is provided only through Railway environment variables.
- Push failure must not prevent email delivery or committed revelation/question state.
- Admin remains a standard web UI.

---

### Task 1: Participant tab shell and catch-up flow

**Files:**
- Modify: `templates/participant_dashboard.html`, `static/js/account.js`, `static/css/app.css`, `app.py`
- Test: `tests/test_revelations.py`

**Interfaces:** Dashboard returns `answeredDailyQuestion` and `unansweredPreviousDailyCount` with the existing `dailyQuestion` and `previousDailyQuestions` values.

- [ ] Write a failing dashboard test for the catch-up fields and for prior answers moving to Mes réponses.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_revelations.py -k daily` and confirm failure.
- [ ] Add server aggregation, four hash-addressable panes, Home order, bottom navigation, Profile-only unanswered previous questions, and Mes réponses bonus-answer rendering.
- [ ] Re-run the targeted test, then commit `feat: add participant app navigation`.

### Task 2: Installable participant-only PWA

**Files:**
- Create: `static/manifest.webmanifest`, `static/sw.js`, `static/offline.html`, PNG PWA icons
- Modify: `templates/base.html`, `templates/participant_dashboard.html`, `app.py`, `static/js/account.js`, `tests/test_api.py`

**Interfaces:** `GET /manifest.webmanifest` and `GET /sw.js` provide root-scoped PWA resources. The worker precaches only named public assets and uses the offline page only for navigation failures.

- [ ] Write failing route/template tests for manifest linkage, worker scope and cache policy.
- [ ] Run targeted pytest and confirm failure.
- [ ] Implement manifest, icons, root worker route, participant-only registration and static-only caching.
- [ ] Verify API/participant/admin requests stay network-only, then commit `feat: add participant pwa shell`.

### Task 3: Push subscription boundary

**Files:**
- Modify: `requirements.txt`, `app.py`, `tests/test_revelations.py`, `README.md`

**Interfaces:** `POST /api/account/push-subscriptions` accepts one validated Push API subscription for the logged-in participant. `DELETE /api/account/push-subscriptions` removes the current endpoint. `send_push_notification(participant_id, payload)` sends best-effort notifications and removes expired endpoints.

- [ ] Write failing authorization, validation and expiration-cleanup tests.
- [ ] Run targeted pytest and confirm failure.
- [ ] Add subscription table, VAPID configuration, authenticated CRUD and best-effort sender.
- [ ] Document `T24_VAPID_PUBLIC_KEY`, `T24_VAPID_PRIVATE_KEY`, and `T24_VAPID_SUBJECT` for Railway.
- [ ] Re-run targeted tests, then commit `feat: store participant push subscriptions`.

### Task 4: Permission and delivery events

**Files:**
- Modify: `static/js/account.js`, `static/sw.js`, `app.py`, `tests/test_revelations.py`

**Interfaces:** Push payloads use `title`, `body`, `url`. Revelation sends title `Une révélation t’attend.` with its detail URL. Daily-batch sends use `daily_question_subject()` with the account URL.

- [ ] Write failing tests for both event payloads and push errors that preserve email/revelation success.
- [ ] Run targeted pytest and confirm failure.
- [ ] Add the first-login explainer, click-to-subscribe flow, worker push/click handlers, and backend post-commit sends.
- [ ] Re-run targeted tests, then commit `feat: notify participants of revelations and questions`.

### Task 5: Release verification

**Files:**
- Modify: `README.md`, `tests/test_api.py`, `tests/test_revelations.py`

- [ ] Run `.venv/bin/python -m pytest -q` and `git diff --check`.
- [ ] Manually verify installation, tab reload, notification subscription and offline navigation over HTTPS.
- [ ] Document Railway deployment and browser-permission testing.
- [ ] Commit `docs: document participant pwa deployment`.
