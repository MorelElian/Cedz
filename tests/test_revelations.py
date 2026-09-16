import base64
import io
import json
import sqlite3

import pytest

from app import DEFAULT_INTRO_PHRASES, MailDeliveryError, choose_intro, create_app, deliver_email


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "revelations.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SECRET_KEY": "test-secret",
        "ADMIN_PASSWORD": "correct-horse",
        "SEED_DEMO": True,
        "AUTO_IMPORT_ANSWERS": True,
    })


@pytest.fixture()
def client(app):
    return app.test_client()


def admin_login(client):
    assert client.post("/admin/login", data={"password": "correct-horse"}).status_code == 302
    token = client.get("/api/admin/csrf").get_json()["csrfToken"]
    return {"X-CSRF-Token": token}


def set_password(client, csrf, participant_id, password="mot-de-passe"):
    response = client.patch(
        f"/api/admin/participants/{participant_id}/password",
        json={"password": password}, headers=csrf,
    )
    assert response.status_code == 200


def participant_login(client, name, password="mot-de-passe"):
    response = client.post("/login", json={"name": name, "password": password})
    assert response.status_code == 200, response.get_json()
    return {"X-CSRF-Token": response.get_json()["csrfToken"]}


def test_gmail_transport_uses_starttls_without_exposing_credentials(app, monkeypatch):
    calls = []
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def ehlo(self):
            calls.append(("ehlo",))

        def starttls(self, *, context):
            calls.append(("starttls", bool(context)))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            sent_messages.append(message)
            calls.append(("send", message["To"], message["Subject"], message.get_content_type()))

    monkeypatch.setattr("app.smtplib.SMTP", FakeSMTP)
    app.config.update(
        MAIL_MODE="gmail", SMTP_USERNAME="sender@gmail.com", SMTP_PASSWORD="application-secret",
        MAIL_FROM="Cedz <sender@gmail.com>", SMTP_HOST="smtp.gmail.com", SMTP_PORT=587,
    )
    with app.app_context():
        assert deliver_email(
            "sender@gmail.com", "Test Cedz",
            "<p style='color:#17213a'>Ça marche.</p><img src='https://cedz.example/logo.png' alt='Cedz'>"
            "<img src='https://cedz.example/profile-images/BarbsSmall.png' alt='Barbs'>",
        ) == "gmail"
    assert calls[0][:3] == ("connect", "smtp.gmail.com", 587)
    assert ("starttls", True) in calls
    assert calls[-1] == ("send", "sender@gmail.com", "Test Cedz", "multipart/alternative")
    html_part = sent_messages[0].get_body(preferencelist=("html",))
    assert "style='color:#17213a'" in html_part.get_content()
    assert "src='https://cedz.example/logo.png'" in html_part.get_content()
    assert "src='https://cedz.example/profile-images/BarbsSmall.png'" in html_part.get_content()
    images = [part for part in sent_messages[0].walk() if part.get_content_maintype() == "image"]
    assert images == []

    app.config["SMTP_PASSWORD"] = ""
    with app.app_context(), pytest.raises(MailDeliveryError, match="incomplète"):
        deliver_email("sender@gmail.com", "Test Cedz", "<p>Non.</p>")


def test_gmail_api_refreshes_token_and_sends_mime_message(app, monkeypatch):
    requests = []
    responses = [
        {"access_token": "temporary-access-token", "expires_in": 3600},
        {"id": "gmail-message-id", "threadId": "gmail-thread-id"},
    ]

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(json.dumps(responses[len(requests) - 1]).encode())

    monkeypatch.setattr("app.urlopen", fake_urlopen)
    app.config.update(
        MAIL_MODE="gmail_api",
        MAIL_FROM="Cedz Are Shooting <cedzt24@gmail.com>",
        GMAIL_CLIENT_ID="oauth-client-id",
        GMAIL_CLIENT_SECRET="oauth-client-secret",
        GMAIL_REFRESH_TOKEN="oauth-refresh-token",
    )
    with app.app_context():
        assert deliver_email(
            "participant@example.fr", "Une révélation", "<p style='color:#17213a'>Salut.</p>"
        ) == "gmail_api"

    token_request, send_request = requests[0][0], requests[1][0]
    assert token_request.full_url == "https://oauth2.googleapis.com/token"
    assert b"grant_type=refresh_token" in token_request.data
    assert b"oauth-refresh-token" in token_request.data
    assert send_request.full_url.endswith("/gmail/v1/users/me/messages/send")
    assert send_request.get_header("Authorization") == "Bearer temporary-access-token"
    raw = json.loads(send_request.data)["raw"]
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode(errors="replace")
    assert "participant@example.fr" in decoded
    assert "Salut." in decoded

    app.config["GMAIL_REFRESH_TOKEN"] = ""
    with app.app_context(), pytest.raises(MailDeliveryError, match="OAuth Gmail incomplète"):
        deliver_email("participant@example.fr", "Test", "<p>Non.</p>")


def test_intro_phrase_catalog_migrates_existing_database_once(tmp_path):
    database = tmp_path / "catalog.sqlite3"
    config = {
        "TESTING": True,
        "DATABASE": str(database),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SECRET_KEY": "test-secret",
        "ADMIN_PASSWORD": "correct-horse",
        "SEED_DEMO": True,
    }
    create_app(config)
    with sqlite3.connect(database) as db:
        db.execute("DELETE FROM site_settings WHERE key='intro_phrase_catalog_version'")
        db.execute(
            """UPDATE intro_phrases SET text=?, tone='pique', is_active=1
               WHERE id=(SELECT MIN(id) FROM intro_phrases)""",
            ("Pas la pêche aujourd'hui ?",),
        )
        db.execute(
            """INSERT INTO intro_phrases(text,tone,is_active,created_at,updated_at)
               VALUES (?,'positif',1,'now','now')""",
            ("Phrase ajoutée dans l'admin",),
        )
        db.commit()

    create_app(config)
    create_app(config)
    with sqlite3.connect(database) as db:
        active = db.execute(
            "SELECT text,tone FROM intro_phrases WHERE is_active=1 ORDER BY id"
        ).fetchall()
        version = db.execute(
            "SELECT value FROM site_settings WHERE key='intro_phrase_catalog_version'"
        ).fetchone()[0]
    assert version == "2"
    assert set(DEFAULT_INTRO_PHRASES).issubset(set(active))
    assert ("Phrase ajoutée dans l'admin", "positif") in active
    assert sum(text == "Tu chiales Aujourd'hui ?" for text, _ in active) == 1
    assert all(text != "Pas la pêche aujourd'hui ?" for text, _ in active)


def test_import_is_idempotent_and_does_not_reuse_external_primary_keys(client, app):
    csrf = admin_login(client)
    before = client.get("/api/admin/raw-answers").get_json()["answers"]
    exported = json.loads((app.root_path + "/answers/t24-reponses(1).json" and
                           open(app.root_path + "/answers/t24-reponses(1).json", encoding="utf-8").read()))
    first = client.post("/api/admin/import-answers", json={"answers": exported}, headers=csrf)
    second = client.post("/api/admin/import-answers", json={"answers": exported}, headers=csrf)
    assert first.status_code == second.status_code == 200
    after = client.get("/api/admin/raw-answers").get_json()["answers"]
    assert len(after) == len(before) == len(exported)
    assert second.get_json()["imported"] == 0
    assert {row["id"] for row in after} != {row["externalId"] for row in after}
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_import_rebuilds_sessions_progress_and_fresh_database_emails(client, app):
    csrf = admin_login(client)
    people = client.get("/api/admin/participants").get_json()["participants"]
    assert sum(bool(person["email"]) for person in people) == 9
    assert next(person for person in people if person["displayName"] == "Rov")["email"] is None
    with sqlite3.connect(app.config["DATABASE"]) as db:
        statuses = dict(db.execute(
            """SELECT p.display_name,s.status FROM participants p
               LEFT JOIN answer_sessions s ON s.participant_id=p.id"""
        ).fetchall())
    assert {name for name, status in statuses.items() if status == "completed"} == {
        "Barbs", "Div", "JL", "Moms", "Nav", "Peusch", "Pilche",
    }
    assert {name for name, status in statuses.items() if status == "started"} == {"Diego", "Lahaye"}
    assert statuses["Rov"] is None
    diego = next(person for person in people if person["displayName"] == "Diego")
    set_password(client, csrf, diego["id"])
    participant_login(client, "Diego")
    dashboard = client.get("/api/account/dashboard").get_json()
    assert dashboard["questionnaire"]["completed"] is False
    assert dashboard["questionnaire"]["answeredCount"] == 18
    assert dashboard["questionnaire"]["remainingCount"] == 12
    assert dashboard["questionnaire"]["totalCount"] == 30
    questions = client.get(f"/api/sessions/{dashboard['questionnaire']['sessionId']}/questions").get_json()
    assert len(questions["answersByInstance"]) == 18
    assert len(questions["questions"]) == 12
    assert questions["remainingCount"] == 12
    assert questions["totalCount"] == 30


def test_admin_overview_aggregates_imported_answers_without_duplicates(client):
    admin_login(client)
    answers = client.get("/api/admin/answers").get_json()["answers"]
    assert len(answers) == 252
    assert len({(item["sessionId"], item["id"]) for item in answers}) == 252
    assert len({item["sessionId"] for item in answers if item["sessionCompleted"]}) == 7
    stats = client.get("/api/admin/stats").get_json()
    assert stats["completed"] == 7
    assert stats["answerCount"] == 252
    progress = {item["participant"]: item for item in stats["progress"]}
    assert progress["Diego"] == {"participantId": progress["Diego"]["participantId"],
                                  "participant": "Diego", "answered": 18, "total": 30,
                                  "percent": 60, "status": "started"}
    assert progress["Lahaye"]["answered"] == 12
    assert progress["Lahaye"]["percent"] == 40


def test_import_validation_is_atomic(client):
    csrf = admin_login(client)
    before = len(client.get("/api/admin/raw-answers").get_json()["answers"])
    response = client.post("/api/admin/import-answers", json={"answers": [
        {"id": 999999, "author": "Personne inconnue", "answer": "x", "question": "Test"}
    ]}, headers=csrf)
    assert response.status_code == 400
    assert len(client.get("/api/admin/raw-answers").get_json()["answers"]) == before


def test_login_hashes_password_and_isolates_questionnaires(client, app):
    csrf = admin_login(client)
    people = client.get("/api/admin/participants").get_json()["participants"]
    first = next(person for person in people if person["displayName"] == "Rov")
    second = next(person for person in people if person["id"] != first["id"])
    participants = [first, second]
    for person in participants:
        set_password(client, csrf, person["id"])
    participant_login(client, participants[0]["displayName"])
    created = client.post("/api/sessions", json={
        "participantId": participants[0]["id"], "email": "first@example.fr", "phone": "",
    })
    assert created.status_code == 201
    session_id = created.get_json()["sessionId"]
    participant_login(client, participants[1]["displayName"])
    assert client.get(f"/api/sessions/{session_id}/questions").status_code == 403
    participant_login(client, participants[0]["displayName"])
    with sqlite3.connect(app.config["DATABASE"]) as db:
        stored = db.execute("SELECT password_hash FROM participants WHERE id=?", (participants[0]["id"],)).fetchone()[0]
        assert stored != "mot-de-passe" and stored
        db.execute("UPDATE answer_sessions SET status='completed' WHERE id=?", (session_id,))
        db.commit()
    assert client.get(f"/api/sessions/{session_id}/questions").status_code == 403
    assert client.get(f"/questionnaire/{session_id}").status_code == 403


def test_login_rejects_external_next_redirect(client):
    csrf = admin_login(client)
    rov = next(person for person in client.get("/api/admin/participants").get_json()["participants"]
               if person["displayName"] == "Rov")
    set_password(client, csrf, rov["id"])
    response = client.post("/login?next=https://evil.example", json={"name": "Rov", "password": "mot-de-passe"})
    assert response.status_code == 200
    assert response.get_json()["redirectUrl"] in {"/compte", "/mon-compte"}


def test_participant_can_change_password_and_old_password_stops_working(client):
    csrf = admin_login(client)
    participant = client.get("/api/admin/participants").get_json()["participants"][0]
    set_password(client, csrf, participant["id"], "ancien-pass")
    assert client.post("/admin/logout", data={"csrf_token": csrf["X-CSRF-Token"]}).status_code == 302

    account_csrf = participant_login(client, participant["displayName"], "ancien-pass")
    assert client.patch(
        "/api/account/password",
        json={"currentPassword": "incorrect", "newPassword": "nouveau-pass"},
        headers=account_csrf,
    ).status_code == 403
    changed = client.patch(
        "/api/account/password",
        json={"currentPassword": "ancien-pass", "newPassword": "nouveau-pass"},
        headers=account_csrf,
    )
    assert changed.status_code == 200
    assert client.post("/logout", headers=account_csrf).status_code == 302
    assert client.post(
        "/login", json={"name": participant["displayName"], "password": "ancien-pass"}
    ).status_code == 401
    assert client.post(
        "/login", json={"name": participant["displayName"], "password": "nouveau-pass"}
    ).status_code == 200


def test_intro_phrase_is_random_among_least_used_choices(app, monkeypatch):
    seen = []

    class PickLast:
        def choice(self, values):
            seen.extend(values)
            return values[-1]

    monkeypatch.setattr("app.secrets.SystemRandom", PickLast)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        participant_id = db.execute("SELECT MIN(id) FROM participants WHERE is_active=1").fetchone()[0]
        expected_id = db.execute(
            "SELECT MAX(id) FROM intro_phrases WHERE is_active=1 AND tone='pique'"
        ).fetchone()[0]
    with app.app_context():
        chosen = choose_intro({"recipient_participant_id": participant_id, "tone": "pique"})
    assert len(seen) > 1
    assert chosen["id"] == expected_id


def test_review_rerolls_automatic_intro_but_preserves_admin_edit(client, monkeypatch):
    csrf = admin_login(client)
    first = client.get("/api/admin/revelations/review").get_json()["revelations"]
    edited = first[0]
    assert client.patch(
        f"/api/admin/revelations/{edited['id']}",
        json={"intro": "Texte choisi manuellement", "finalContent": edited["finalContent"]},
        headers=csrf,
    ).status_code == 200
    monkeypatch.setattr("app.choose_intro", lambda _: {"id": None, "text": "Nouveau tirage automatique"})
    reloaded = client.get("/api/admin/revelations/review").get_json()["revelations"]
    by_id = {card["id"]: card for card in reloaded}
    assert by_id[edited["id"]]["intro"] == "Texte choisi manuellement"
    assert all(
        card["intro"] == "Nouveau tirage automatique"
        for card in reloaded if card["id"] != edited["id"]
    )


def test_review_has_one_card_per_participant_and_refreshes_explicitly(client):
    csrf = admin_login(client)
    payload = client.get("/api/admin/revelations/review").get_json()
    assert payload["expectedCount"] == 10
    assert len(payload["revelations"]) == 10
    assert len({row["recipientId"] for row in payload["revelations"]}) == 10
    current = payload["revelations"][0]
    refreshed = client.post(
        f"/api/admin/revelations/{current['id']}/refresh",
        json={"action": "later"}, headers=csrf,
    )
    assert refreshed.status_code == 200
    assert refreshed.get_json()["revelation"]["id"] != current["id"]


def test_send_calls_configured_delivery_then_is_idempotent_and_private(client, app, monkeypatch):
    deliveries = []

    def fake_delivery(recipient, subject, html_body):
        deliveries.append((recipient, subject, html_body))
        return "gmail"

    app.config["MAIL_MODE"] = "gmail"
    app.config["PUBLIC_BASE_URL"] = "https://cedz.example"
    monkeypatch.setattr("app.deliver_email", fake_delivery)
    csrf = admin_login(client)
    people = client.get("/api/admin/participants").get_json()["participants"]
    cards = client.get("/api/admin/revelations/review").get_json()["revelations"]
    card = next(item for item in cards if item["content"]["recipient"] != "Rov")
    recipient = next(person for person in people if person["id"] == card["recipientId"])
    author = next(person for person in people if person["id"] == card["authorId"])
    set_password(client, csrf, recipient["id"])
    set_password(client, csrf, author["id"])
    assert client.patch(
        f"/api/admin/participants/{recipient['id']}",
        json={"email": "recipient@example.fr"}, headers=csrf,
    ).status_code == 200
    assert client.patch(
        f"/api/admin/participants/{author['id']}",
        json={"email": "author@example.fr"}, headers=csrf,
    ).status_code == 200
    assert client.patch(
        f"/api/admin/revelations/{card['id']}",
        json={"intro": "<b>Bonjour</b>", "finalContent": "<script>alert(1)</script>"}, headers=csrf,
    ).status_code == 200
    sent = client.post(f"/api/admin/revelations/{card['id']}/send", headers=csrf)
    assert sent.status_code == 200
    assert sent.get_json()["deliveryMode"] == "gmail"
    assert len(deliveries) == 1 and deliveries[0][0] == "recipient@example.fr"
    snapshot = sent.get_json()["htmlSnapshot"]
    assert "<script>" not in snapshot
    assert "&lt;script&gt;" not in snapshot
    assert "<main class='mail' style=" in snapshot
    assert "<section class='actions' style=" in snapshot
    assert "Question du moment" in snapshot
    assert "line-height:1.65" in snapshot
    assert "https://cedz.example/logo.png" in snapshot
    assert "https://cedz.example/profile-images/" in snapshot
    assert f"https://cedz.example/revelations/{card['id']}" in snapshot
    marker = {"ranking": "class='rank'", "binary_split": "class='groups'", "slider": "class='number'",
              "compare_two": "class='verdict'", "compare_three": "class='verdict'"}.get(card["type"], "<blockquote ")
    assert marker in snapshot
    assert "/logo.png" in sent.get_json()["htmlSnapshot"]
    assert f"/revelations/{card['id']}" in sent.get_json()["htmlSnapshot"]
    again = client.post(f"/api/admin/revelations/{card['id']}/send", headers=csrf)
    assert again.status_code == 200 and again.get_json()["alreadySent"] is True
    assert len(deliveries) == 1
    account_csrf = participant_login(client, recipient["displayName"])
    dashboard = client.get("/api/account/dashboard").get_json()
    assert [item["id"] for item in dashboard["revelations"]] == [card["id"]]
    assert client.post(
        f"/api/account/revelations/{card['id']}/reply",
        json={"message": "Sans jeton."},
    ).status_code == 403
    reply = client.post(
        f"/api/account/revelations/{card['id']}/reply",
        json={"message": "Je prends note."}, headers=account_csrf,
    )
    assert reply.status_code == 201
    assert reply.get_json()["notificationSent"] is True
    assert len(deliveries) == 2
    notification = deliveries[-1]
    assert notification[0] == "author@example.fr"
    assert notification[1] == f"Cedz — {recipient['displayName']} t’a répondu"
    assert card["question"] in notification[2]
    assert "Je prends note." in notification[2]
    assert "Ta question" in notification[2]
    assert "Ta réponse" in notification[2]
    assert "Sa réponse" in notification[2]
    assert client.post(
        f"/api/account/revelations/{card['id']}/reply",
        json={"message": "Deuxième réponse."}, headers=account_csrf,
    ).status_code == 409
    participant_login(client, author["displayName"])
    received_reply = client.get("/api/account/dashboard").get_json()["repliesReceived"][0]
    assert received_reply["message"] == "Je prends note."
    assert received_reply["original_question"] == card["question"]
    assert received_reply["original_message"] == "<script>alert(1)</script>"
    assert client.get(f"/api/account/revelations/{card['id']}").status_code == 404
    admin_csrf = admin_login(client)
    replies = client.get("/api/admin/revelation-replies", headers=admin_csrf).get_json()["replies"]
    assert replies[0]["message"] == "Je prends note."
    assert replies[0]["originalQuestion"] == card["question"]
    assert replies[0]["originalMessage"] == "<script>alert(1)</script>"


def test_failed_gmail_delivery_keeps_revelation_in_review(client, app, monkeypatch):
    csrf = admin_login(client)
    card = next(item for item in client.get("/api/admin/revelations/review").get_json()["revelations"]
                if item["recipientEmail"])
    app.config["MAIL_MODE"] = "gmail"

    def reject_delivery(*_):
        raise MailDeliveryError("refus simulé")

    monkeypatch.setattr("app.deliver_email", reject_delivery)
    response = client.post(f"/api/admin/revelations/{card['id']}/send", headers=csrf)
    assert response.status_code == 502
    remaining_ids = {item["id"] for item in client.get("/api/admin/revelations/review").get_json()["revelations"]}
    assert card["id"] in remaining_ids


def test_bulk_send_continues_after_one_failure_and_skips_missing_email(client, app, monkeypatch):
    csrf = admin_login(client)
    cards = client.get("/api/admin/revelations/review").get_json()["revelations"]
    ready = [card for card in cards if card["recipientEmail"]]
    missing = [card for card in cards if not card["recipientEmail"]]
    failed_email = ready[0]["recipientEmail"]
    attempts = []

    def fake_delivery(recipient, subject, html_body):
        attempts.append(recipient)
        if recipient == failed_email:
            raise MailDeliveryError("refus simulé")
        return "gmail_api"

    app.config["MAIL_MODE"] = "gmail_api"
    monkeypatch.setattr("app.deliver_email", fake_delivery)
    assert client.post("/api/admin/revelations/send-active").status_code == 403
    response = client.post("/api/admin/revelations/send-active", headers=csrf)
    assert response.status_code == 200
    result = response.get_json()
    assert result["sentCount"] == len(ready) - 1
    assert result["failedCount"] == 1
    assert result["failed"][0]["recipientName"] == ready[0]["recipientName"]
    assert result["failed"][0]["recipientEmail"] == failed_email
    assert result["skippedCount"] == len(missing)
    assert [item["recipientEmail"] for item in result["skipped"]] == [
        card["recipientEmail"] for card in missing
    ]
    assert all(item["recipientEmail"] for item in result["sent"])
    assert len(attempts) == len(ready)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        failed_status = db.execute(
            "SELECT status FROM revelations WHERE id=?", (ready[0]["id"],)
        ).fetchone()[0]
        sent_count = db.execute(
            "SELECT COUNT(*) FROM revelations WHERE status='sent'"
        ).fetchone()[0]
    assert failed_status == "in_review"
    assert sent_count == len(ready) - 1


def test_rov_without_email_blocks_send_and_multi_person_answers_fan_out(client, app):
    csrf = admin_login(client)
    cards = client.get("/api/admin/revelations/review").get_json()["revelations"]
    rov = next(item for item in cards if item["content"]["recipient"] == "Rov")
    assert client.post(f"/api/admin/revelations/{rov['id']}/send", headers=csrf).status_code == 409
    with sqlite3.connect(app.config["DATABASE"]) as db:
        rows = db.execute(
            """SELECT ia.question_type, ia.id, count(r.id)
               FROM imported_answers ia JOIN revelations r ON r.imported_answer_id=ia.id
               WHERE ia.question_type IN ('compare_two','compare_three')
               GROUP BY ia.id"""
        ).fetchall()
    assert rows
    assert all(count == (2 if kind == "compare_two" else 3) for kind, _, count in rows)


def test_intro_phrase_crud_requires_admin_csrf(client):
    csrf = admin_login(client)
    created = client.post("/api/admin/intro-phrases", json={"text": "Ça roule ?", "tone": "positif"}, headers=csrf)
    assert created.status_code == 201
    phrase_id = created.get_json()["id"]
    assert client.patch(
        f"/api/admin/intro-phrases/{phrase_id}",
        json={"text": "Ça nage ?", "tone": "pique"}, headers=csrf,
    ).status_code == 200
    assert client.delete(f"/api/admin/intro-phrases/{phrase_id}", headers=csrf).status_code == 200
