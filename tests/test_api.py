import io
import sqlite3
from collections import Counter

import pytest

from app import PROFILE_CATALOG, QUESTION_CATALOG, create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3"),
                       "UPLOAD_FOLDER": str(tmp_path / "uploads"), "SECRET_KEY": "test-secret",
                       "ADMIN_PASSWORD": "correct-horse", "SEED_DEMO": True})


@pytest.fixture()
def client(app):
    return app.test_client()


def start_session(client):
    participant = client.get("/api/participants").get_json()["participants"][0]
    response = client.post("/api/sessions", json={"participantId": participant["id"],
                           "email": "ami@example.fr", "phone": "+33 6 12 34 56 78"})
    assert response.status_code == 201
    return participant, response.get_json()["sessionId"]


def login_admin(client):
    response = client.post("/admin/login", data={"password": "correct-horse"})
    assert response.status_code == 302
    token = client.get("/api/admin/csrf").get_json()["csrfToken"]
    return {"X-CSRF-Token": token}


def compare_two_instances(app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        return db.execute(
            """SELECT qi.id, qi.target_participant_id, qi.target_participant_2_id, q.id
               FROM question_instances qi
               JOIN questions q ON q.id = qi.question_id
               WHERE qi.is_active = 1 AND q.is_active = 1 AND q.type = 'compare_two'
               ORDER BY qi.id"""
        ).fetchall()


def assert_cycle_sample(rows, expected_participant_ids):
    expected_participant_ids = set(expected_participant_ids)
    grouped = {}
    for row in rows:
        grouped.setdefault(row[3], []).append(row)
    assert grouped
    for question_rows in grouped.values():
        assert len(question_rows) == len(expected_participant_ids)
        pairs = [{row[1], row[2]} for row in question_rows]
        assert all(len(pair) == 2 for pair in pairs)
        assert len({frozenset(pair) for pair in pairs}) == len(question_rows)
        degrees = Counter(participant_id for row in question_rows for participant_id in row[1:3])
        assert degrees == Counter({participant_id: 2 for participant_id in expected_participant_ids})


def valid_answer(question, participant_ids):
    question_type = question["type"]
    if question_type in {"free_text", "single_person_answer"}:
        return "Une réponse avec du panache."
    if question_type == "slider":
        return question["scaleMin"]
    if question_type in {"compare_two", "compare_three"}:
        return {"selectedParticipantId": question["targetParticipantIds"][0], "comment": "Choix assumé."}
    if question_type == "ranking":
        return {"orderedParticipantIds": participant_ids}
    if question_type == "binary_split":
        return {"categoryA": participant_ids[:2], "categoryB": participant_ids[2:]}
    raise AssertionError(f"Type non testé: {question_type}")


def answer_all_questions(client, session_id):
    payload = client.get(f"/api/sessions/{session_id}/questions").get_json()
    participant_ids = [person["id"] for person in payload["participants"]]
    for question in payload["questions"]:
        if str(question["instanceId"]) in payload["answersByInstance"]:
            continue
        response = client.post(f"/api/sessions/{session_id}/answers", json={
            "questionInstanceId": question["instanceId"],
            "answer": valid_answer(question, participant_ids),
        })
        assert response.status_code == 200, (question["type"], response.get_json())


def test_participant_flow_does_not_expose_answers(client):
    participant, session_id = start_session(client)
    payload = client.get(f"/api/sessions/{session_id}/questions").get_json()
    assert payload["questions"]
    assert all(participant["id"] not in q["targetParticipantIds"] for q in payload["questions"])
    question = next(q for q in payload["questions"] if q["type"] == "free_text")
    saved = client.post(f"/api/sessions/{session_id}/answers",
                        json={"questionInstanceId": question["instanceId"], "answer": "Il va surprendre."})
    assert saved.status_code == 200
    again = client.get(f"/api/sessions/{session_id}/questions").get_json()
    assert again["answersByInstance"][str(question["instanceId"])] == "Il va surprendre."
    assert all("answer" not in q for q in again["questions"])
    assert client.get("/api/admin/answers").status_code == 401
    assert client.post(f"/api/sessions/{session_id}/complete").status_code == 409
    answer_all_questions(client, session_id)
    assert client.post(f"/api/sessions/{session_id}/complete").get_json()["completed"] is True
    assert client.post(f"/api/sessions/{session_id}/answers",
                       json={"questionInstanceId": question["instanceId"], "answer": "Tard"}).status_code == 200
    login_admin(client)
    assert client.get("/api/admin/answers").get_json()["answers"][0]["answer"] == "Tard"


def test_participant_resumes_the_only_existing_session(client):
    participant = client.get("/api/participants").get_json()["participants"][0]
    started = client.post("/api/sessions", json={
        "participantId": participant["id"], "email": "ami@example.fr", "phone": "",
    })
    session_id = started.get_json()["sessionId"]
    resumed = client.post("/api/sessions", json={
        "participantId": participant["id"], "email": "ami@example.fr", "phone": "",
        "resumeToken": started.get_json()["resumeToken"],
    })
    assert resumed.status_code == 200
    assert resumed.get_json()["sessionId"] == session_id
    assert resumed.get_json()["resumed"] is True
    refused = client.post("/api/sessions", json={
        "participantId": participant["id"], "email": "ami@example.fr", "phone": "",
        "resumeToken": "mauvais-jeton",
    })
    assert refused.status_code == 409


def test_bundled_logo_is_used_on_a_clean_database(client):
    assert client.get("/health").get_json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200
    assert b'/logo.png' in page.data
    assert client.get('/logo.png').status_code == 200


def test_ten_profiles_and_both_images_are_preloaded(client):
    participants = client.get("/api/participants").get_json()["participants"]
    assert [participant["displayName"] for participant in participants] == sorted(
        profile[0] for profile in PROFILE_CATALOG
    )
    assert len(participants) == 10
    for participant in participants:
        assert participant["choicePhotoUrl"].startswith("/profile-images/")
        assert participant["profilePhotoUrl"].startswith("/profile-images/")
        assert participant["choicePhotoUrl"] != participant["profilePhotoUrl"]
        assert client.get(participant["choicePhotoUrl"]).mimetype == "image/png"
        assert client.get(participant["profilePhotoUrl"]).mimetype == "image/png"


def test_legacy_placeholder_profiles_are_deleted_during_seed(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    uploads = tmp_path / "uploads"
    legacy_app = create_app({
        "TESTING": True, "DATABASE": str(database), "UPLOAD_FOLDER": str(uploads),
        "SECRET_KEY": "test-secret", "ADMIN_PASSWORD": "correct-horse", "SEED_DEMO": False,
    })
    with sqlite3.connect(database) as db:
        for name, slug in (("Hugo", "hugo"), ("Léo", "l-o"), ("Max", "max"), ("Nico", "nico")):
            db.execute(
                """INSERT INTO participants(display_name, slug, is_active, created_at, updated_at)
                   VALUES (?, ?, 1, 'now', 'now')""",
                (name, slug),
            )
        db.commit()

    migrated_app = create_app({
        "TESTING": True, "DATABASE": str(database), "UPLOAD_FOLDER": str(uploads),
        "SECRET_KEY": "test-secret", "ADMIN_PASSWORD": "correct-horse", "SEED_DEMO": True,
    })
    participants = migrated_app.test_client().get("/api/participants").get_json()["participants"]
    assert {participant["displayName"] for participant in participants} == {
        profile[0] for profile in PROFILE_CATALOG
    }
    with sqlite3.connect(database) as db:
        assert db.execute(
            "SELECT count(*) FROM participants WHERE display_name IN ('Hugo', 'Léo', 'Max', 'Nico')"
        ).fetchone()[0] == 0


def test_admin_uploads_two_participant_photos_and_logo(client):
    csrf = login_admin(client)
    image = b"\x89PNG\r\n\x1a\n" + b"test-image"
    first = client.post("/api/admin/uploads", data={"image": (io.BytesIO(image), "portrait.png")}, headers=csrf)
    second = client.post("/api/admin/uploads", data={"image": (io.BytesIO(image), "profil.png")}, headers=csrf)
    assert first.status_code == second.status_code == 201
    created = client.post("/api/admin/participants", json={
        "displayName": "Deux Photos",
        "choicePhotoUrl": first.get_json()["url"],
        "profilePhotoUrl": second.get_json()["url"],
    }, headers=csrf)
    assert created.status_code == 201
    assert created.get_json()["choicePhotoUrl"] == first.get_json()["url"]
    assert created.get_json()["profilePhotoUrl"] == second.get_json()["url"]
    settings = client.patch("/api/admin/settings", json={"logoUrl": first.get_json()["url"]}, headers=csrf)
    assert settings.status_code == 200
    assert client.get("/api/admin/settings").get_json()["logoUrl"] == first.get_json()["url"]
    invalid = client.post("/api/admin/uploads", data={"image": (io.BytesIO(b"not-an-image"), "fake.png")}, headers=csrf)
    assert invalid.status_code == 400


def test_final_feedback_is_visible_to_admin(client):
    participant, session_id = start_session(client)
    saved = client.post(f"/api/sessions/{session_id}/feedback", json={"message": "Ajoute plus de café."})
    assert saved.status_code == 200
    csrf = login_admin(client)
    feedback = client.get("/api/admin/feedback", headers=csrf).get_json()["feedback"]
    assert feedback[0]["participant"] == participant["displayName"]
    assert feedback[0]["message"] == "Ajoute plus de café."


@pytest.mark.parametrize(("email", "phone"), [("pas-un-mail", "+33612345678"), ("ok@example.fr", "12")])
def test_session_rejects_invalid_contact(client, email, phone):
    participant = client.get("/api/participants").get_json()["participants"][0]
    response = client.post("/api/sessions", json={"participantId": participant["id"], "email": email, "phone": phone})
    assert response.status_code == 400


def test_admin_crud_generation_and_export(client):
    csrf = login_admin(client)
    created = client.post("/api/admin/participants", json={"displayName": "Cédric", "secretCode": "cedz"}, headers=csrf)
    assert created.status_code == 201
    participant_id = created.get_json()["id"]
    question = client.post("/api/admin/questions", json={"title": "Mental", "body": "Mental de {person} ?",
                           "type": "slider", "targetMode": "one_person", "scaleMin": 1, "scaleMax": 10}, headers=csrf)
    assert question.status_code == 201
    assert client.post("/api/admin/questions/generate-instances", headers=csrf).get_json()["generated"] > 0
    assert client.delete(f"/api/admin/participants/{participant_id}", headers=csrf).get_json()["deactivated"] is True
    assert client.get("/api/admin/export?format=json").mimetype == "application/json"
    assert client.get("/api/admin/export?format=csv").mimetype == "text/csv"


def test_structured_comparison_is_validated(client):
    _, session_id = start_session(client)
    questions = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"]
    comparison = next(q for q in questions if q["type"] == "compare_two")
    response = client.post(f"/api/sessions/{session_id}/answers", json={"questionInstanceId": comparison["instanceId"],
                           "answer": {"selectedParticipantId": 999999, "comment": "triche"}})
    assert response.status_code == 400


def test_phone_is_optional(client):
    participant = client.get("/api/participants").get_json()["participants"][0]
    response = client.post("/api/sessions", json={
        "participantId": participant["id"],
        "email": "ami-sans-telephone@example.fr",
        "phone": "",
    })
    assert response.status_code == 201


def test_admin_mutations_require_csrf(client):
    login_admin(client)
    response = client.post("/api/admin/participants", json={"displayName": "Intrus"})
    assert response.status_code == 403


def test_all_seed_question_types_accept_valid_answers(client):
    _, session_id = start_session(client)
    payload = client.get(f"/api/sessions/{session_id}/questions").get_json()
    participant_ids = [person["id"] for person in payload["participants"]]
    answers = {}
    for question in payload["questions"]:
        question_type = question["type"]
        if question_type in answers:
            continue
        value = valid_answer(question, participant_ids)
        response = client.post(f"/api/sessions/{session_id}/answers", json={
            "questionInstanceId": question["instanceId"],
            "answer": value,
        })
        assert response.status_code == 200, (question_type, response.get_json())
        answers[question_type] = value
    assert answers.keys() >= {"free_text", "slider", "compare_two", "compare_three", "ranking", "binary_split"}


def test_regenerating_instances_preserves_active_session_answers(client):
    _, session_id = start_session(client)
    before = client.get(f"/api/sessions/{session_id}/questions").get_json()
    question = before["questions"][0]
    saved = client.post(f"/api/sessions/{session_id}/answers", json={
        "questionInstanceId": question["instanceId"],
        "answer": valid_answer(question, [person["id"] for person in before["participants"]]),
    })
    assert saved.status_code == 200
    csrf = login_admin(client)
    assert client.post("/api/admin/questions/generate-instances", headers=csrf).status_code == 200
    after = client.get(f"/api/sessions/{session_id}/questions").get_json()
    assert [item["instanceId"] for item in after["questions"]] == [item["instanceId"] for item in before["questions"]]
    assert str(question["instanceId"]) in after["answersByInstance"]


def test_compare_two_generation_is_a_stable_cycle(client, app):
    participant_ids = [person["id"] for person in client.get("/api/participants").get_json()["participants"]]
    before = compare_two_instances(app)
    assert_cycle_sample(before, participant_ids)

    csrf = login_admin(client)
    regenerated = client.post("/api/admin/questions/generate-instances", headers=csrf)
    assert regenerated.status_code == 200
    after = compare_two_instances(app)
    assert after == before


def test_compare_two_generation_resamples_after_population_change(client, app):
    csrf = login_admin(client)
    created = client.post(
        "/api/admin/participants",
        json={"displayName": "Nouvelle recrue"},
        headers=csrf,
    )
    assert created.status_code == 201
    assert client.post("/api/admin/questions/generate-instances", headers=csrf).status_code == 200

    participant_ids = [person["id"] for person in client.get("/api/participants").get_json()["participants"]]
    assert_cycle_sample(compare_two_instances(app), participant_ids)


def test_compare_two_generation_with_two_people_keeps_one_unique_pair(client, app):
    csrf = login_admin(client)
    participant_ids = [person["id"] for person in client.get("/api/participants").get_json()["participants"]]
    for participant_id in participant_ids[2:]:
        response = client.delete(f"/api/admin/participants/{participant_id}", headers=csrf)
        assert response.status_code == 200
    assert client.post("/api/admin/questions/generate-instances", headers=csrf).status_code == 200

    rows = compare_two_instances(app)
    assert len(rows) == sum(question[2] == "compare_two" for question in QUESTION_CATALOG)
    assert all({row[1], row[2]} == set(participant_ids[:2]) for row in rows)


def test_catalog_is_preloaded_once_and_contains_every_markdown_question(client, app):
    csrf = login_admin(client)
    first = client.get("/api/admin/questions", headers=csrf).get_json()["questions"]
    active = [question for question in first if question["isActive"]]
    assert len(active) == len(QUESTION_CATALOG)
    assert {question["category"] for question in active} == {
        "Classements", "Sur quelqu'un", "Duels", "Comparaisons à trois",
        "Réponses ouvertes", "Deux groupes", "Curseurs",
    }

    create_app({
        "TESTING": True,
        "DATABASE": app.config["DATABASE"],
        "UPLOAD_FOLDER": app.config["UPLOAD_FOLDER"],
        "SECRET_KEY": "test-secret",
        "ADMIN_PASSWORD": "correct-horse",
        "SEED_DEMO": True,
    })
    second = client.get("/api/admin/questions", headers=csrf).get_json()["questions"]
    assert len(second) == len(first)


def test_session_gets_at_most_two_stable_comparisons_per_category(client):
    _, session_id = start_session(client)
    first = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"]
    second = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"]
    first_ids = [question["instanceId"] for question in first if question["type"] == "compare_two"]
    second_ids = [question["instanceId"] for question in second if question["type"] == "compare_two"]
    assert len(first_ids) == 2
    assert second_ids == first_ids


def test_session_limits_every_category_and_keeps_same_question_targets_distinct(client):
    _, session_id = start_session(client)
    first = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"]
    second = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"]
    grouped = {}
    by_category = {}
    for question in first:
        grouped.setdefault(question["questionId"], []).append(question)
        by_category.setdefault(question["category"], []).append(question)
    assert all(len(questions) <= 2 for questions in by_category.values())
    assert all(len(variants) <= 2 for variants in grouped.values())
    for variants in grouped.values():
        target_sets = [tuple(question["targetParticipantIds"]) for question in variants]
        assert len(target_sets) == len(set(target_sets))
    assert [question["instanceId"] for question in second] == [
        question["instanceId"] for question in first
    ]


def test_session_cannot_answer_an_unassigned_comparison(client, app):
    csrf = login_admin(client)
    assert client.post(
        "/api/admin/participants",
        json={"displayName": "Cinquième"},
        headers=csrf,
    ).status_code == 201
    assert client.post("/api/admin/questions/generate-instances", headers=csrf).status_code == 200
    author, session_id = start_session(client)
    assigned = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"]
    assigned_ids = {
        question["instanceId"] for question in assigned if question["type"] == "compare_two"
    }
    unassigned = next(
        row for row in compare_two_instances(app)
        if row[0] not in assigned_ids and author["id"] not in {row[1], row[2]}
    )
    response = client.post(f"/api/sessions/{session_id}/answers", json={
        "questionInstanceId": unassigned[0],
        "answer": {"selectedParticipantId": unassigned[1], "comment": ""},
    })
    assert response.status_code == 403


def test_saved_answer_keeps_its_author(client, app):
    author, session_id = start_session(client)
    question = client.get(f"/api/sessions/{session_id}/questions").get_json()["questions"][0]
    response = client.post(f"/api/sessions/{session_id}/answers", json={
        "questionInstanceId": question["instanceId"],
        "answer": valid_answer(
            question,
            [person["id"] for person in client.get("/api/participants").get_json()["participants"]],
        ),
    })
    assert response.status_code == 200
    with sqlite3.connect(app.config["DATABASE"]) as db:
        row = db.execute(
            "SELECT author_participant_id FROM answers WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    assert row[0] == author["id"]


def test_production_refuses_default_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("T24_ENV", "production")
    monkeypatch.delenv("T24_SECRET_KEY", raising=False)
    monkeypatch.delenv("T24_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="doivent être définis"):
        create_app({"DATABASE": str(tmp_path / "production.sqlite3"), "SEED_DEMO": False})
