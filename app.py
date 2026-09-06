from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from itertools import combinations
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)


QUESTION_TYPES = {
    "free_text",
    "single_person_answer",
    "compare_two",
    "compare_three",
    "ranking",
    "binary_split",
    "slider",
}
TARGET_MODES = {"none", "one_person", "two_people", "three_people", "all_people"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 .()\-]{6,24}$")

PROFILE_CATALOG = [
    ("Barbs", "barbsBig.png", "BarbsSmall.png"),
    ("Diego", "DiegoBig.png", "DiegoSmall.png"),
    ("Div", "DivBig.png", "DivSmall.png"),
    ("JL", "JlBig.png", "JlSmall.png"),
    ("Lahaye", "LahayeBig.png", "LahayeSmall.png"),
    ("Moms", "MomsBig.png", "MomsSmall.png"),
    ("Nav", "NavBig.png", "navSmall.png"),
    ("Peusch", "PeuschBig.png", "PeuschSmall.png"),
    ("Pilche", "PilcheBig.png", "PilcheSmall.png"),
    ("Rov", "RovBig.png", "RovSmall.png"),
]

QUESTION_CATALOG = [
    ("Classement des disciplines", "Classe les participants pour les différentes disciplines du T24.", "ranking", "Classements", "all_people", None, None),

    ("Sport de prédilection", "Sur quel sport devrait se concentrer {person} ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Petit mot", "Un petit mot à adresser à {person}.", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Carrière rugbystique", "Que penses-tu de la carrière rugbystique de {person} ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Match idéal", "La meuf qui conviendrait le mieux à {person} avec son niveau actuel ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Prêt demain", "Si le T24 était demain, est-ce que {person} serait prêt ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Défaut T24", "Le plus gros défaut de {person} pour le T24, selon toi ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Salle du temps", "Si {person} entre dans la salle du temps, ça sera pour…", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Phrase de motivation", "Si tu devais motiver {person} avec une phrase, tu lui dirais quoi ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Qualité salvatrice", "Quelle qualité de {person} peut vraiment le sauver quand les jambes vont commencer à négocier leur départ ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Discipline surprise", "Quelle discipline va permettre à {person} de faire taire deux ou trois mauvaises langues ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Excuse professionnelle", "Quelle excuse de qualité professionnelle {person} prépare déjà en cas de contre-performance ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Athlète inquiétant", "Quel détail ferait passer {person} de « bon pote courageux » à « athlète inquiétant » ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Message de ravito", "Quelle phrase devrait être écrite sur le ravito de {person} pour le relancer ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Film du T24", "Quel film correspondrait le mieux au T24 de {person} ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Meilleure version", "Quelle est la meilleure version possible de {person} le jour du T24 ?", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Danger de la prépa", "Le plus gros danger dans la préparation de {person}, c'est…", "free_text", "Sur quelqu'un", "one_person", None, None),
    ("Phrase après victoire", "Si {person} réussit son T24, qu'est-ce qu'il nous dira ?", "free_text", "Sur quelqu'un", "one_person", None, None),

    ("Comparaison de niveau", "Entre {person1} et {person2}, qui a le plus gros potentiel sportif ?", "compare_two", "Duels", "two_people", None, None),
    ("Duel d'aura", "Entre {person1} et {person2}, qui a le plus de chances de finir le T24 avec une vraie aura ?", "compare_two", "Duels", "two_people", None, None),
    ("Décollage risqué", "Entre {person1} et {person2}, qui est le plus susceptible de partir comme un avion et de finir avec les ailes qui touchent la piste ?", "compare_two", "Duels", "two_people", None, None),
    ("Personne n'y croyait", "Entre {person1} et {person2}, qui a le plus gros potentiel de « personne n'y croyait, et pourtant » ?", "compare_two", "Duels", "two_people", None, None),
    ("Dernier relais", "Entre {person1} et {person2}, à qui confierais-tu le dernier relais si ta dignité dépendait du résultat ?", "compare_two", "Duels", "two_people", None, None),
    ("Performance inattendue", "Entre {person1} et {person2}, qui peut sortir une performance inattendue juste pour embêter les pronostics ?", "compare_two", "Duels", "two_people", None, None),

    ("Menace non homologuée", "Entre {person1}, {person2} et {person3}, qui gagne le titre de « menace sérieuse mais pas encore homologuée » ?", "compare_three", "Comparaisons à trois", "three_people", None, None),
    ("Moins avantagé", "Entre {person1}, {person2} et {person3}, qui est le moins avantagé par le format ?", "compare_three", "Comparaisons à trois", "three_people", None, None),
    ("Capitaine, joker, ambiance", "Entre {person1}, {person2} et {person3}, qui mets-tu capitaine, qui mets-tu joker et qui mets-tu responsable de l'ambiance ?", "free_text", "Comparaisons à trois", "three_people", None, None),
    ("Plot twist", "Entre {person1}, {person2} et {person3}, qui a le plus de chances de créer le plot twist du T24 ?", "compare_three", "Comparaisons à trois", "three_people", None, None),
    ("Lettre de démission", "Entre {person1}, {person2} et {person3}, qui va le mieux gérer le moment où le corps envoie sa lettre de démission ?", "compare_three", "Comparaisons à trois", "three_people", None, None),
    ("Peur sur 24 heures", "Entre {person1}, {person2} et {person3}, qui fait le plus peur sur 24 heures : le talent, le mental ou l'absence de lucidité ?", "compare_three", "Comparaisons à trois", "three_people", None, None),
    ("Équipier de minuit", "Entre {person1}, {person2} et {person3}, qui veux-tu dans ton équipe à minuit quand tout le monde commence à parler moins fort ?", "compare_three", "Comparaisons à trois", "three_people", None, None),
    ("Capital respect", "Entre {person1}, {person2} et {person3}, qui repartira avec le plus gros capital respect ?", "compare_three", "Comparaisons à trois", "three_people", None, None),

    ("La vilaine tempête", "Un jour, tu as fait du sport avec {person} et tu lui as mis une vilaine tempête : raconte.", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Performance de renom", "Quand tu penses à une performance sportive de renom de {person}, tu penses à quoi ?", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Le déclic", "Décris le moment exact où {person} va passer de « tranquille » à « finalement, c'est un vrai truc ce T24 ».", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Légende de la performance", "Écris la légende Instagram que {person} postera s'il fait une grosse performance.", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Légende de l'explosion", "Écris la légende Instagram que {person} postera s'il explose mais veut quand même sauver son image.", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Ralenti épique", "Quelle scène du T24 de {person} mériterait d'être rejouée au ralenti avec une musique épique ?", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Documentaire Netflix", "Si le T24 était un documentaire Netflix du point de vue de {person}, quel serait le titre ?", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Discours de coach", "Invente le discours de coach qui ferait repartir {person} quand il commence à voir flou.", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Meilleure surprise", "Quelle serait la meilleure surprise que {person} pourrait offrir à tout le monde pendant le T24 ?", "free_text", "Réponses ouvertes", "one_person", None, None),
    ("Scénario de remontada", "Raconte le scénario le plus drôle mais réaliste de la remontada de {person}.", "free_text", "Réponses ouvertes", "one_person", None, None),

    ("Physique ou chance", "Répartis les participants : physique d'un côté, chance de l'autre.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Se révéler ou craquer", "Répartis ceux qui peuvent se révéler et ceux qui peuvent craquer.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Mental ou force", "Répartis les gros mentaux et les grosses forces physiques.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Silence ou larmes", "Ceux qui vont souffrir en silence contre ceux qui vont chialer.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Après minuit", "Ceux qui performent mieux de nuit contre ceux qui négocient avec leur âme après minuit.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Gestion du chaos", "Ceux qui vont gérer contre ceux qui ne vont pas gérer.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Moteurs ou diesels", "Ceux qui vont motiver les autres contre ceux qu'il faudra motiver comme un vieux diesel.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Sourire final", "Ceux qui vont finir avec le sourire contre ceux qui souriront uniquement pour les photos.", "binary_split", "Deux groupes", "all_people", None, None),
    ("Zug ou Bellagio", "Il va se la mettre à Zug contre il va chiller à Bellagio.", "binary_split", "Deux groupes", "all_people", None, None),

    ("Chrono à viser", "Le jour du T24, combien de minutes doit viser {person} ?", "slider", "Curseurs", "one_person", 0, 1440),
    ("Premiers regrets", "À partir de quelle minute {person} commence à regretter d'être venu ?", "slider", "Curseurs", "one_person", 0, 1440),
    ("Probabilité de performance", "Sur 100, quelle est la probabilité que {person} sorte une vraie performance et oblige tout le monde à respecter ?", "slider", "Curseurs", "one_person", 0, 100),
    ("Menace sérieuse", "De 1 à 10, à quel point {person} est une menace sérieuse si son ego et son cardio signent enfin un pacte ?", "slider", "Curseurs", "one_person", 1, 10),
    ("Je suis bien là", "Combien de minutes avant que {person} dise « en vrai, je suis bien là » alors que son visage dit l'inverse ?", "slider", "Curseurs", "one_person", 0, 1440),
    ("Préparation physique", "Sur 100, à combien {person} est prêt physiquement aujourd'hui, sans compter la confiance injustifiée ?", "slider", "Curseurs", "one_person", 0, 100),
    ("Pas à mon prime", "Combien de fois {person} va dire « je ne suis pas à mon prime » pendant le T24 ?", "slider", "Curseurs", "one_person", 0, 50),
    ("Respect gagné", "Sur 100, quelle est la probabilité que {person} gagne du respect même sans gagner le T24 ?", "slider", "Curseurs", "one_person", 0, 100),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("T24_DATABASE", str(Path(app.instance_path) / "t24.sqlite3")),
        SECRET_KEY=os.environ.get("T24_SECRET_KEY", "local-dev-change-me"),
        ADMIN_PASSWORD=os.environ.get("T24_ADMIN_PASSWORD", "t24-admin"),
        UPLOAD_FOLDER=os.environ.get("T24_UPLOAD_FOLDER", str(Path(app.instance_path) / "uploads")),
        SEED_DEMO=True,
        MAX_CONTENT_LENGTH=6_000_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("T24_SECURE_COOKIE", "0") == "1",
    )
    if config:
        app.config.update(config)
    if os.environ.get("T24_ENV") == "production":
        if app.config["SECRET_KEY"] == "local-dev-change-me" or app.config["ADMIN_PASSWORD"] == "t24-admin":
            raise RuntimeError("T24_SECRET_KEY et T24_ADMIN_PASSWORD doivent être définis en production.")

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.before_request(protect_admin_mutations)
    app.context_processor(inject_site_settings)
    register_routes(app)
    with app.app_context():
        init_db()
        if app.config["SEED_DEMO"]:
            seed_demo_data()
    return app


# Flask's application context is available even when there is no request.
def _db() -> sqlite3.Connection:
    from flask import current_app

    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    _db().executescript(
        """
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            email TEXT,
            phone TEXT,
            avatar_url TEXT,
            profile_photo_url TEXT,
            secret_code TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT,
            target_mode TEXT NOT NULL DEFAULT 'none',
            scale_min REAL,
            scale_max REAL,
            allow_self_target INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS question_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            target_participant_id INTEGER REFERENCES participants(id),
            target_participant_2_id INTEGER REFERENCES participants(id),
            target_participant_3_id INTEGER REFERENCES participants(id),
            rendered_body TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS answer_sessions (
            id TEXT PRIMARY KEY,
            participant_id INTEGER NOT NULL REFERENCES participants(id),
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            resume_token_hash TEXT,
            status TEXT NOT NULL DEFAULT 'started',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            feedback TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES answer_sessions(id),
            author_participant_id INTEGER NOT NULL REFERENCES participants(id),
            question_instance_id INTEGER NOT NULL REFERENCES question_instances(id),
            target_participant_id INTEGER REFERENCES participants(id),
            answer_text TEXT,
            answer_number REAL,
            answer_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(session_id, question_instance_id)
        );
        CREATE INDEX IF NOT EXISTS idx_instances_question ON question_instances(question_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_answers_session ON answers(session_id);
        CREATE INDEX IF NOT EXISTS idx_answers_target ON answers(target_participant_id);
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    participant_columns = {row["name"] for row in _db().execute("PRAGMA table_info(participants)")}
    if "profile_photo_url" not in participant_columns:
        _db().execute("ALTER TABLE participants ADD COLUMN profile_photo_url TEXT")
    session_columns = {row["name"] for row in _db().execute("PRAGMA table_info(answer_sessions)")}
    if "feedback" not in session_columns:
        _db().execute("ALTER TABLE answer_sessions ADD COLUMN feedback TEXT")
    if "resume_token_hash" not in session_columns:
        _db().execute("ALTER TABLE answer_sessions ADD COLUMN resume_token_hash TEXT")
    _db().commit()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "participant"


def unique_slug(name: str, participant_id: int | None = None) -> str:
    base = slugify(name)
    slug, index = base, 2
    while _db().execute(
        "SELECT 1 FROM participants WHERE slug = ? AND (? IS NULL OR id != ?)",
        (slug, participant_id, participant_id),
    ).fetchone():
        slug, index = f"{base}-{index}", index + 1
    return slug


def seed_demo_data() -> None:
    db = _db()
    now = utcnow()
    changed = False

    profile_version = db.execute(
        "SELECT value FROM site_settings WHERE key = 'profile_catalog_version'"
    ).fetchone()
    if not profile_version or profile_version["value"] != "3":
        legacy_rows = db.execute(
            """SELECT id FROM participants
               WHERE slug IN ('hugo', 'leo', 'l-o', 'max', 'nico')
                  OR display_name IN ('Hugo', 'Léo', 'Max', 'Nico')"""
        ).fetchall()
        legacy_ids = [row["id"] for row in legacy_rows]
        if legacy_ids:
            placeholders = ",".join("?" for _ in legacy_ids)
            db.execute(
                f"""DELETE FROM answers
                    WHERE author_participant_id IN ({placeholders})
                       OR target_participant_id IN ({placeholders})
                       OR session_id IN (
                           SELECT id FROM answer_sessions
                           WHERE participant_id IN ({placeholders})
                       )
                       OR question_instance_id IN (
                           SELECT id FROM question_instances
                           WHERE target_participant_id IN ({placeholders})
                              OR target_participant_2_id IN ({placeholders})
                              OR target_participant_3_id IN ({placeholders})
                       )""",
                legacy_ids * 6,
            )
            db.execute(
                f"DELETE FROM answer_sessions WHERE participant_id IN ({placeholders})",
                legacy_ids,
            )
            db.execute(
                f"""DELETE FROM question_instances
                    WHERE target_participant_id IN ({placeholders})
                       OR target_participant_2_id IN ({placeholders})
                       OR target_participant_3_id IN ({placeholders})""",
                legacy_ids * 3,
            )
            db.execute(
                f"DELETE FROM participants WHERE id IN ({placeholders})",
                legacy_ids,
            )
        for name, large_image, small_image in PROFILE_CATALOG:
            slug = slugify(name)
            large_url = f"/profile-images/{large_image}"
            small_url = f"/profile-images/{small_image}"
            existing = db.execute(
                "SELECT id FROM participants WHERE slug = ? ORDER BY id LIMIT 1",
                (slug,),
            ).fetchone()
            if existing:
                db.execute(
                    """UPDATE participants
                       SET display_name = ?, avatar_url = ?, profile_photo_url = ?,
                           is_active = 1, updated_at = ?
                       WHERE id = ?""",
                    (name, large_url, small_url, now, existing["id"]),
                )
                continue
            db.execute(
                """INSERT INTO participants(
                       display_name, slug, avatar_url, profile_photo_url,
                       is_active, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (name, slug, large_url, small_url, now, now),
            )
        db.execute(
            """INSERT INTO site_settings(key, value, updated_at)
               VALUES ('profile_catalog_version', '3', ?)
               ON CONFLICT(key) DO UPDATE
               SET value = excluded.value, updated_at = excluded.updated_at""",
            (now,),
        )
        changed = True

    catalog_version = db.execute(
        "SELECT value FROM site_settings WHERE key = 'question_catalog_version'"
    ).fetchone()
    if not catalog_version or catalog_version["value"] != "1":
        # Preserve old answers while retiring the six placeholders from the MVP.
        db.execute("UPDATE questions SET is_active = 0, updated_at = ? WHERE category = 'Démo'", (now,))
        next_order = db.execute("SELECT COALESCE(MAX(display_order), 0) FROM questions").fetchone()[0]
        for offset, values in enumerate(QUESTION_CATALOG, 1):
            title, body, question_type, category, target_mode, scale_min, scale_max = values
            if db.execute(
                "SELECT 1 FROM questions WHERE body = ? AND type = ? LIMIT 1",
                (body, question_type),
            ).fetchone():
                continue
            db.execute(
                """INSERT INTO questions(title, body, type, target_mode, scale_min, scale_max,
                   category, allow_self_target, is_active, display_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?)""",
                (
                    title,
                    body,
                    question_type,
                    target_mode,
                    scale_min,
                    scale_max,
                    category,
                    next_order + offset,
                    now,
                    now,
                ),
            )
        db.execute(
            """INSERT INTO site_settings(key, value, updated_at) VALUES ('question_catalog_version', '1', ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (now,),
        )
        changed = True
    db.commit()
    if changed:
        generate_instances()


def render_question(body: str, people: list[sqlite3.Row]) -> str:
    values: dict[str, str] = {}
    if people:
        values["person"] = values["person1"] = people[0]["display_name"]
    if len(people) > 1:
        values["person2"] = people[1]["display_name"]
    if len(people) > 2:
        values["person3"] = people[2]["display_name"]
    try:
        return body.format(**values)
    except (KeyError, ValueError):
        return body


def _valid_active_compare_two_groups(
    db: sqlite3.Connection,
    question_id: int,
    participants: list[sqlite3.Row],
) -> list[tuple[sqlite3.Row, sqlite3.Row]] | None:
    """Return the current sample when it is still a cycle over the active people."""
    rows = db.execute(
        """SELECT target_participant_id, target_participant_2_id, target_participant_3_id
           FROM question_instances
           WHERE question_id = ? AND is_active = 1
           ORDER BY id""",
        (question_id,),
    ).fetchall()
    people_by_id = {person["id"]: person for person in participants}
    participant_ids = set(people_by_id)
    expected_count = len(participants) if len(participants) >= 3 else int(len(participants) == 2)
    if len(rows) != expected_count:
        return None

    pairs: list[tuple[sqlite3.Row, sqlite3.Row]] = []
    seen_pairs: set[frozenset[int]] = set()
    neighbours = {participant_id: set() for participant_id in participant_ids}
    for row in rows:
        first_id, second_id = row["target_participant_id"], row["target_participant_2_id"]
        if (
            first_id not in participant_ids
            or second_id not in participant_ids
            or first_id == second_id
            or row["target_participant_3_id"] is not None
        ):
            return None
        pair_key = frozenset((first_id, second_id))
        if pair_key in seen_pairs:
            return None
        seen_pairs.add(pair_key)
        neighbours[first_id].add(second_id)
        neighbours[second_id].add(first_id)
        pairs.append((people_by_id[first_id], people_by_id[second_id]))

    if len(participants) == 2:
        return pairs if all(len(values) == 1 for values in neighbours.values()) else None
    if len(participants) < 2:
        return pairs
    if any(len(values) != 2 for values in neighbours.values()):
        return None

    visited: set[int] = set()
    pending = [next(iter(participant_ids))]
    while pending:
        participant_id = pending.pop()
        if participant_id in visited:
            continue
        visited.add(participant_id)
        pending.extend(neighbours[participant_id] - visited)
    return pairs if visited == participant_ids else None


def _compare_two_groups(
    db: sqlite3.Connection,
    question_id: int,
    participants: list[sqlite3.Row],
) -> list[tuple[sqlite3.Row, sqlite3.Row]]:
    current_groups = _valid_active_compare_two_groups(db, question_id, participants)
    if current_groups is not None:
        return current_groups
    if len(participants) < 2:
        return []

    shuffled = list(participants)
    secrets.SystemRandom().shuffle(shuffled)
    if len(shuffled) == 2:
        return [(shuffled[0], shuffled[1])]
    return [(shuffled[index], shuffled[(index + 1) % len(shuffled)]) for index in range(len(shuffled))]


def generate_instances() -> int:
    db = _db()
    participants = db.execute("SELECT id, display_name FROM participants WHERE is_active = 1 ORDER BY id").fetchall()
    questions = db.execute("SELECT * FROM questions WHERE is_active = 1 ORDER BY display_order, id").fetchall()
    active_instance_ids: list[int] = []
    count = 0
    now = utcnow()
    for question in questions:
        size = {"none": 0, "one_person": 1, "two_people": 2, "three_people": 3, "all_people": 0}[question["target_mode"]]
        if question["type"] == "compare_two":
            groups = _compare_two_groups(db, question["id"], participants)
        else:
            groups = [()] if size == 0 else combinations(participants, size)
        for group_tuple in groups:
            group = list(group_tuple)
            ids = [person["id"] for person in group] + [None, None, None]
            rendered_body = render_question(question["body"], group)
            existing = db.execute(
                """SELECT id FROM question_instances
                   WHERE question_id = ? AND target_participant_id IS ?
                     AND target_participant_2_id IS ? AND target_participant_3_id IS ?
                   ORDER BY id LIMIT 1""",
                (question["id"], ids[0], ids[1], ids[2]),
            ).fetchone()
            if existing:
                instance_id = existing["id"]
                db.execute(
                    "UPDATE question_instances SET rendered_body = ?, is_active = 1 WHERE id = ?",
                    (rendered_body, instance_id),
                )
            else:
                cursor = db.execute(
                    """INSERT INTO question_instances(question_id, target_participant_id,
                       target_participant_2_id, target_participant_3_id, rendered_body, is_active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (question["id"], ids[0], ids[1], ids[2], rendered_body, now),
                )
                instance_id = cursor.lastrowid
            active_instance_ids.append(instance_id)
            count += 1
    if active_instance_ids:
        placeholders = ",".join("?" for _ in active_instance_ids)
        db.execute(
            f"UPDATE question_instances SET is_active = 0 WHERE id NOT IN ({placeholders})",
            active_instance_ids,
        )
    else:
        db.execute("UPDATE question_instances SET is_active = 0")
    db.commit()
    return count


def json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort_json(400, "Corps JSON invalide.")
    return data


def abort_json(status: int, message: str) -> None:
    response = jsonify({"error": message})
    response.status_code = status
    abort(response)


def inject_site_settings() -> dict[str, Any]:
    row = _db().execute("SELECT value FROM site_settings WHERE key = 'logo_url'").fetchone()
    bundled_logo = "/logo.png" if Path(__file__).with_name("logo.png").is_file() else None
    return {"site_logo_url": row["value"] if row and row["value"] else bundled_logo}


def resume_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def validate_asset_url(value: Any) -> str | None:
    url = str(value or "").strip()
    if not url:
        return None
    if len(url) > 1000 or not (
        url.startswith("/uploads/")
        or url.startswith("/profile-images/")
        or url.startswith("https://")
        or url.startswith("http://")
    ):
        abort_json(400, "URL d’image invalide.")
    return url


def image_extension(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                abort_json(401, "Authentification admin requise.")
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)
    return session["csrf_token"]


def protect_admin_mutations() -> None:
    is_admin_mutation = (
        request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and (request.path.startswith("/api/admin/") or request.path == "/admin/logout")
    )
    if not is_admin_mutation:
        return
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        abort_json(403, "Jeton CSRF invalide.")


def participant_payload(row: sqlite3.Row, private: bool = False) -> dict[str, Any]:
    choice_photo = row["avatar_url"]
    profile_photo = row["profile_photo_url"] or choice_photo
    result = {
        "id": row["id"],
        "displayName": row["display_name"],
        "slug": row["slug"],
        "avatarUrl": choice_photo,
        "choicePhotoUrl": choice_photo,
        "profilePhotoUrl": profile_photo,
        "isActive": bool(row["is_active"]),
        "requiresSecretCode": bool(row["secret_code"]),
    }
    if private:
        result.update(email=row["email"], phone=row["phone"], secretCode=row["secret_code"])
    return result


def question_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "title": row["title"], "body": row["body"], "type": row["type"],
        "category": row["category"], "targetMode": row["target_mode"], "scaleMin": row["scale_min"],
        "scaleMax": row["scale_max"], "allowSelfTarget": bool(row["allow_self_target"]),
        "isActive": bool(row["is_active"]), "displayOrder": row["display_order"],
    }


def validate_contact(email: Any, phone: Any) -> tuple[str, str]:
    email = str(email or "").strip().lower()
    phone = str(phone or "").strip()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        abort_json(400, "Adresse email invalide.")
    if phone and not PHONE_RE.fullmatch(phone):
        abort_json(400, "Numéro de téléphone invalide.")
    return email, phone


def get_answer_session(session_id: str) -> sqlite3.Row:
    row = _db().execute("SELECT * FROM answer_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        abort_json(404, "Session introuvable.")
    canonical = _db().execute(
        """SELECT s.id FROM answer_sessions s
           LEFT JOIN answers a ON a.session_id = s.id
           WHERE s.participant_id = ?
           GROUP BY s.id ORDER BY COUNT(a.id) DESC, s.created_at, s.id LIMIT 1""",
        (row["participant_id"],),
    ).fetchone()
    if canonical and canonical["id"] != session_id:
        abort_json(410, "Cette ancienne session a été remplacée par la participation principale.")
    return row


def session_question_rows(session_id: str, participant_id: int) -> list[sqlite3.Row]:
    rows = _db().execute(
        """SELECT qi.*, q.type, q.category, q.scale_min, q.scale_max, q.allow_self_target, q.display_order
           FROM question_instances qi JOIN questions q ON q.id = qi.question_id
           WHERE qi.is_active = 1 AND q.is_active = 1
             AND (q.allow_self_target = 1 OR ? NOT IN (
                 COALESCE(qi.target_participant_id, -1), COALESCE(qi.target_participant_2_id, -1),
                 COALESCE(qi.target_participant_3_id, -1)))
           ORDER BY q.display_order, qi.id""",
        (participant_id,),
    ).fetchall()
    selected: list[sqlite3.Row] = []
    variants: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        category = row["category"] or f"question:{row['question_id']}"
        variants.setdefault(category, []).append(row)
    for category, candidates in variants.items():
        candidates.sort(
            key=lambda row: hashlib.sha256(
                f"{session_id}:{category}:{row['question_id']}:{row['id']}".encode()
            ).digest()
        )
        selected.extend(candidates[:2])
    return sorted(selected, key=lambda row: (row["display_order"], row["id"]))


def register_routes(app: Flask) -> None:
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/favicon.ico")
    def favicon():
        return app.send_static_file("favicon.svg")

    @app.get("/logo.png")
    def project_logo():
        return send_from_directory(Path(__file__).parent, "logo.png", max_age=86400)

    @app.get("/profile-images/<path:filename>")
    def profile_image(filename: str):
        return send_from_directory(Path(__file__).with_name("images"), filename, max_age=86400)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/questionnaire/<session_id>")
    def questionnaire(session_id: str):
        answer_session = get_answer_session(session_id)
        participant = _db().execute("SELECT * FROM participants WHERE id = ?", (answer_session["participant_id"],)).fetchone()
        return render_template("questionnaire.html", session_id=session_id, current_participant=participant_payload(participant))

    @app.get("/merci")
    def merci():
        return render_template("merci.html", session_id=None)

    @app.get("/merci/<session_id>")
    def merci_session(session_id: str):
        get_answer_session(session_id)
        return render_template("merci.html", session_id=session_id)

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, max_age=86400)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        error = None
        if request.method == "POST":
            password = request.form.get("password", "")
            if secrets.compare_digest(password, str(app.config["ADMIN_PASSWORD"])):
                session.clear()
                session["is_admin"] = True
                csrf_token()
                return redirect(url_for("admin"))
            error = "Mot de passe incorrect."
        return render_template("admin_login.html", error=error)

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    @app.get("/admin")
    @admin_required
    def admin():
        return render_template("admin.html", csrf_token=csrf_token())

    @app.get("/api/participants")
    def public_participants():
        rows = _db().execute("SELECT * FROM participants WHERE is_active = 1 ORDER BY display_name").fetchall()
        return jsonify({"participants": [participant_payload(row) for row in rows]})

    @app.post("/api/sessions")
    def create_answer_session():
        data = json_body()
        try:
            participant_id = int(data.get("participantId"))
        except (TypeError, ValueError):
            abort_json(400, "Participant invalide.")
        participant = _db().execute("SELECT * FROM participants WHERE id = ? AND is_active = 1", (participant_id,)).fetchone()
        if not participant:
            abort_json(404, "Participant introuvable.")
        if participant["secret_code"] and not secrets.compare_digest(str(data.get("secretCode", "")), participant["secret_code"]):
            abort_json(403, "Code participant incorrect.")
        secret_verified = bool(participant["secret_code"])
        email, phone = validate_contact(data.get("email"), data.get("phone"))
        db = _db()
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            """SELECT s.* FROM answer_sessions s LEFT JOIN answers a ON a.session_id = s.id
               WHERE s.participant_id = ? GROUP BY s.id
               ORDER BY COUNT(a.id) DESC, s.created_at, s.id LIMIT 1""",
            (participant_id,),
        ).fetchone()
        if existing:
            supplied_token = str(data.get("resumeToken", ""))
            token_verified = bool(
                supplied_token and existing["resume_token_hash"]
                and secrets.compare_digest(resume_token_hash(supplied_token), existing["resume_token_hash"])
            )
            if not (token_verified or secret_verified) or existing["email"] != email:
                db.rollback()
                abort_json(409, "Ce profil a déjà une participation. Utilise ce navigateur ou ton code secret pour la reprendre.")
            now = utcnow()
            db.execute("UPDATE answer_sessions SET phone = ?, updated_at = ? WHERE id = ?", (phone, now, existing["id"]))
            db.execute("UPDATE participants SET email = ?, phone = ?, updated_at = ? WHERE id = ?", (email, phone, now, participant_id))
            db.commit()
            return jsonify({
                "sessionId": existing["id"],
                "questionnaireUrl": url_for("questionnaire", session_id=existing["id"]),
                "resumed": True,
            })
        now, opaque_id, resume_token = utcnow(), secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        db.execute(
            """INSERT INTO answer_sessions(id, participant_id, email, phone, resume_token_hash, status, started_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'started', ?, ?, ?)""",
            (opaque_id, participant_id, email, phone, resume_token_hash(resume_token), now, now, now),
        )
        db.execute("UPDATE participants SET email = ?, phone = ?, updated_at = ? WHERE id = ?", (email, phone, now, participant_id))
        db.commit()
        return jsonify({
            "sessionId": opaque_id, "questionnaireUrl": url_for("questionnaire", session_id=opaque_id),
            "resumeToken": resume_token,
        }), 201

    @app.get("/api/sessions/<session_id>/questions")
    def session_questions(session_id: str):
        answer_session = get_answer_session(session_id)
        rows = session_question_rows(session_id, answer_session["participant_id"])
        participants = _db().execute("SELECT * FROM participants WHERE is_active = 1 ORDER BY display_name").fetchall()
        questions = []
        for row in rows:
            targets = [row[key] for key in ("target_participant_id", "target_participant_2_id", "target_participant_3_id") if row[key] is not None]
            questions.append({
                "instanceId": row["id"], "questionId": row["question_id"],
                "body": row["rendered_body"], "type": row["type"], "category": row["category"],
                "targetParticipantIds": targets, "scaleMin": row["scale_min"], "scaleMax": row["scale_max"],
            })
        allowed_instance_ids = {row["id"] for row in rows}
        saved_rows = _db().execute(
            """SELECT question_instance_id, answer_text, answer_number, answer_json
               FROM answers WHERE session_id = ?""",
            (session_id,),
        ).fetchall()
        saved_answers: dict[str, Any] = {}
        for saved in saved_rows:
            if saved["question_instance_id"] not in allowed_instance_ids:
                continue
            value: Any = saved["answer_text"]
            if saved["answer_json"] is not None:
                value = json.loads(saved["answer_json"])
            elif saved["answer_number"] is not None:
                value = saved["answer_number"]
            saved_answers[str(saved["question_instance_id"])] = value
        return jsonify({
            "questions": questions,
            "participants": [participant_payload(row) for row in participants],
            "answersByInstance": saved_answers,
        })

    @app.post("/api/sessions/<session_id>/answers")
    def save_answer(session_id: str):
        answer_session = get_answer_session(session_id)
        data = json_body()
        try:
            instance_id = int(data.get("questionInstanceId"))
        except (TypeError, ValueError):
            abort_json(400, "Question invalide.")
        instance = _db().execute(
            """SELECT qi.*, q.type, q.scale_min, q.scale_max, q.allow_self_target
               FROM question_instances qi JOIN questions q ON q.id = qi.question_id
               WHERE qi.id = ? AND qi.is_active = 1 AND q.is_active = 1""", (instance_id,),
        ).fetchone()
        if not instance:
            abort_json(404, "Question introuvable.")
        allowed_instance_ids = {
            row["id"] for row in session_question_rows(session_id, answer_session["participant_id"])
        }
        if instance_id not in allowed_instance_ids:
            abort_json(403, "Cette question ne fait pas partie de votre questionnaire.")
        target_ids = [instance[key] for key in ("target_participant_id", "target_participant_2_id", "target_participant_3_id") if instance[key] is not None]
        if not instance["allow_self_target"] and answer_session["participant_id"] in target_ids:
            abort_json(403, "Vous ne pouvez pas répondre à cette question.")
        text, number, structured = validate_answer(instance, data.get("answer"), target_ids)
        now = utcnow()
        _db().execute(
            """INSERT INTO answers(session_id, author_participant_id, question_instance_id,
               target_participant_id, answer_text, answer_number, answer_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id, question_instance_id) DO UPDATE SET
               answer_text=excluded.answer_text, answer_number=excluded.answer_number,
               answer_json=excluded.answer_json, updated_at=excluded.updated_at""",
            (session_id, answer_session["participant_id"], instance_id, target_ids[0] if target_ids else None,
             text, number, json.dumps(structured, ensure_ascii=False) if structured is not None else None, now, now),
        )
        _db().execute("UPDATE answer_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        _db().commit()
        return jsonify({"saved": True})

    @app.post("/api/sessions/<session_id>/complete")
    def complete_session(session_id: str):
        answer_session = get_answer_session(session_id)
        expected_ids = {
            row["id"] for row in session_question_rows(session_id, answer_session["participant_id"])
        }
        answered_ids = {
            row["question_instance_id"]
            for row in _db().execute(
                "SELECT question_instance_id FROM answers WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        }
        missing = expected_ids - answered_ids
        if missing:
            abort_json(409, f"Il reste {len(missing)} réponse(s) à compléter.")
        now = utcnow()
        _db().execute("UPDATE answer_sessions SET status='completed', completed_at=?, updated_at=? WHERE id=?", (now, now, session_id))
        _db().commit()
        return jsonify({"completed": True, "redirectUrl": url_for("merci_session", session_id=session_id)})

    @app.post("/api/sessions/<session_id>/feedback")
    def save_feedback(session_id: str):
        get_answer_session(session_id)
        message = str(json_body().get("message", "")).strip()
        if not message or len(message) > 2000:
            abort_json(400, "Le message doit contenir entre 1 et 2000 caractères.")
        _db().execute("UPDATE answer_sessions SET feedback = ?, updated_at = ? WHERE id = ?", (message, utcnow(), session_id))
        _db().commit()
        return jsonify({"saved": True})

    register_admin_api(app)


def validate_answer(instance: sqlite3.Row, answer: Any, target_ids: list[int]) -> tuple[str | None, float | None, Any]:
    question_type = instance["type"]
    if question_type in {"free_text", "single_person_answer"}:
        text = str(answer or "").strip()
        if not text or len(text) > 4000:
            abort_json(400, "La réponse doit contenir entre 1 et 4000 caractères.")
        return text, None, None
    if question_type == "slider":
        try:
            number = float(answer)
        except (TypeError, ValueError):
            abort_json(400, "Valeur numérique invalide.")
        minimum = instance["scale_min"] if instance["scale_min"] is not None else 0
        maximum = instance["scale_max"] if instance["scale_max"] is not None else 100
        if not minimum <= number <= maximum:
            abort_json(400, f"La valeur doit être comprise entre {minimum:g} et {maximum:g}.")
        return None, number, None
    if not isinstance(answer, dict):
        abort_json(400, "Réponse structurée invalide.")
    active_ids = {row["id"] for row in _db().execute("SELECT id FROM participants WHERE is_active = 1")}
    if question_type in {"compare_two", "compare_three"}:
        try:
            selected = int(answer.get("selectedParticipantId"))
        except (TypeError, ValueError):
            abort_json(400, "Choix invalide.")
        if selected not in target_ids:
            abort_json(400, "Le participant choisi ne fait pas partie de la comparaison.")
        comment = str(answer.get("comment", "")).strip()
        if len(comment) > 1000:
            abort_json(400, "Commentaire trop long.")
        return None, None, {"selected_participant_id": selected, "comment": comment}
    if question_type == "ranking":
        values = answer.get("orderedParticipantIds")
        ids = normalize_id_list(values)
        if set(ids) != active_ids or len(ids) != len(active_ids):
            abort_json(400, "Le classement doit contenir chaque participant actif une seule fois.")
        return None, None, {"ordered_participant_ids": ids}
    if question_type == "binary_split":
        first, second = normalize_id_list(answer.get("categoryA")), normalize_id_list(answer.get("categoryB"))
        if set(first) & set(second) or set(first + second) != active_ids or len(first + second) != len(active_ids):
            abort_json(400, "Chaque participant actif doit apparaître dans une seule catégorie.")
        return None, None, {"category_a": first, "category_b": second}
    abort_json(400, "Type de question non pris en charge.")


def normalize_id_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        abort_json(400, "Liste de participants invalide.")
    try:
        result = [int(item) for item in value]
    except (TypeError, ValueError):
        abort_json(400, "Identifiant participant invalide.")
    if len(result) != len(set(result)):
        abort_json(400, "Un participant ne peut apparaître qu'une fois.")
    return result


def register_admin_api(app: Flask) -> None:
    @app.get("/api/admin/csrf")
    @admin_required
    def admin_csrf():
        return jsonify({"csrfToken": csrf_token()})

    @app.get("/api/admin/participants")
    @admin_required
    def admin_participants():
        rows = _db().execute("SELECT * FROM participants ORDER BY display_name").fetchall()
        return jsonify({"participants": [participant_payload(row, private=True) for row in rows]})

    @app.post("/api/admin/participants")
    @admin_required
    def admin_create_participant():
        data, now = json_body(), utcnow()
        name = str(data.get("displayName", "")).strip()
        if not name or len(name) > 100:
            abort_json(400, "Nom participant invalide.")
        cursor = _db().execute(
            """INSERT INTO participants(display_name, slug, avatar_url, profile_photo_url, secret_code, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, unique_slug(name), validate_asset_url(data.get("choicePhotoUrl", data.get("avatarUrl"))),
             validate_asset_url(data.get("profilePhotoUrl")),
             str(data.get("secretCode", "")).strip() or None, int(bool(data.get("isActive", True))), now, now),
        )
        _db().commit()
        row = _db().execute("SELECT * FROM participants WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(participant_payload(row, private=True)), 201

    @app.patch("/api/admin/participants/<int:participant_id>")
    @admin_required
    def admin_update_participant(participant_id: int):
        row = _db().execute("SELECT * FROM participants WHERE id = ?", (participant_id,)).fetchone()
        if not row:
            abort_json(404, "Participant introuvable.")
        data = json_body()
        name = str(data.get("displayName", row["display_name"])).strip()
        if not name or len(name) > 100:
            abort_json(400, "Nom participant invalide.")
        _db().execute(
            """UPDATE participants SET display_name=?, slug=?, avatar_url=?, profile_photo_url=?, secret_code=?, is_active=?, updated_at=? WHERE id=?""",
            (name, unique_slug(name, participant_id), validate_asset_url(data.get("choicePhotoUrl", data.get("avatarUrl", row["avatar_url"]))),
             validate_asset_url(data.get("profilePhotoUrl", row["profile_photo_url"])),
             data.get("secretCode", row["secret_code"]), int(bool(data.get("isActive", row["is_active"]))), utcnow(), participant_id),
        )
        _db().commit()
        return jsonify(participant_payload(_db().execute("SELECT * FROM participants WHERE id=?", (participant_id,)).fetchone(), private=True))

    @app.delete("/api/admin/participants/<int:participant_id>")
    @admin_required
    def admin_delete_participant(participant_id: int):
        cursor = _db().execute("UPDATE participants SET is_active=0, updated_at=? WHERE id=?", (utcnow(), participant_id))
        _db().commit()
        if not cursor.rowcount:
            abort_json(404, "Participant introuvable.")
        return jsonify({"deactivated": True})

    @app.get("/api/admin/questions")
    @admin_required
    def admin_questions():
        rows = _db().execute("SELECT * FROM questions ORDER BY display_order, id").fetchall()
        return jsonify({"questions": [question_payload(row) for row in rows]})

    @app.post("/api/admin/questions")
    @admin_required
    def admin_create_question():
        data = json_body()
        values = validated_question(data)
        now = utcnow()
        cursor = _db().execute(
            """INSERT INTO questions(title, body, type, category, target_mode, scale_min, scale_max,
               allow_self_target, is_active, display_order, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (*values, now, now),
        )
        _db().commit()
        return jsonify(question_payload(_db().execute("SELECT * FROM questions WHERE id=?", (cursor.lastrowid,)).fetchone())), 201

    @app.patch("/api/admin/questions/<int:question_id>")
    @admin_required
    def admin_update_question(question_id: int):
        current = _db().execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if not current:
            abort_json(404, "Question introuvable.")
        merged = {
            "title": current["title"], "body": current["body"], "type": current["type"],
            "category": current["category"], "targetMode": current["target_mode"],
            "scaleMin": current["scale_min"], "scaleMax": current["scale_max"],
            "allowSelfTarget": bool(current["allow_self_target"]), "isActive": bool(current["is_active"]),
            "displayOrder": current["display_order"], **json_body(),
        }
        values = validated_question(merged)
        _db().execute(
            """UPDATE questions SET title=?, body=?, type=?, category=?, target_mode=?, scale_min=?, scale_max=?,
               allow_self_target=?, is_active=?, display_order=?, updated_at=? WHERE id=?""", (*values, utcnow(), question_id),
        )
        _db().commit()
        return jsonify(question_payload(_db().execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()))

    @app.delete("/api/admin/questions/<int:question_id>")
    @admin_required
    def admin_delete_question(question_id: int):
        cursor = _db().execute("UPDATE questions SET is_active=0, updated_at=? WHERE id=?", (utcnow(), question_id))
        _db().execute("UPDATE question_instances SET is_active=0 WHERE question_id=?", (question_id,))
        _db().commit()
        if not cursor.rowcount:
            abort_json(404, "Question introuvable.")
        return jsonify({"deactivated": True})

    @app.post("/api/admin/questions/generate-instances")
    @admin_required
    def admin_generate_instances():
        return jsonify({"generated": generate_instances()})

    @app.post("/api/admin/uploads")
    @admin_required
    def admin_upload_image():
        uploaded = request.files.get("image")
        if not uploaded or not uploaded.filename:
            abort_json(400, "Choisis une image à envoyer.")
        data = uploaded.read(5_000_001)
        if not data or len(data) > 5_000_000:
            abort_json(413, "L’image ne doit pas dépasser 5 Mo.")
        extension = image_extension(data)
        if not extension:
            abort_json(400, "Format non accepté. Utilise PNG, JPEG, GIF ou WebP.")
        filename = f"{secrets.token_hex(16)}.{extension}"
        Path(app.config["UPLOAD_FOLDER"], filename).write_bytes(data)
        return jsonify({"url": url_for("uploaded_file", filename=filename)}), 201

    @app.get("/api/admin/settings")
    @admin_required
    def admin_settings():
        row = _db().execute("SELECT value FROM site_settings WHERE key = 'logo_url'").fetchone()
        return jsonify({"logoUrl": row["value"] if row else None})

    @app.patch("/api/admin/settings")
    @admin_required
    def admin_update_settings():
        logo_url = validate_asset_url(json_body().get("logoUrl"))
        _db().execute(
            """INSERT INTO site_settings(key, value, updated_at) VALUES ('logo_url', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (logo_url, utcnow()),
        )
        _db().commit()
        return jsonify({"logoUrl": logo_url})

    @app.get("/api/admin/feedback")
    @admin_required
    def admin_feedback():
        rows = _db().execute(
            """SELECT s.id, s.feedback, s.updated_at, p.id participant_id, p.display_name
               FROM answer_sessions s JOIN participants p ON p.id = s.participant_id
               WHERE s.feedback IS NOT NULL AND s.feedback != '' ORDER BY s.updated_at DESC"""
        ).fetchall()
        return jsonify({"feedback": [{
            "sessionId": row["id"], "participantId": row["participant_id"],
            "participant": row["display_name"], "message": row["feedback"], "updatedAt": row["updated_at"],
        } for row in rows]})

    @app.get("/api/admin/answers")
    @admin_required
    def admin_answers():
        clauses, params = [], []
        for query_key, column in (("authorId", "a.author_participant_id"), ("targetId", "a.target_participant_id"), ("questionId", "qi.question_id")):
            if request.args.get(query_key):
                clauses.append(f"{column} = ?")
                params.append(request.args[query_key])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = _db().execute(answer_export_query(where), params).fetchall()
        return jsonify({"answers": [answer_payload(row) for row in rows]})

    @app.get("/api/admin/export")
    @admin_required
    def admin_export():
        rows = _db().execute(answer_export_query()).fetchall()
        if request.args.get("format", "json").lower() == "csv":
            output = io.StringIO()
            fields = list(answer_payload(rows[0]).keys()) if rows else ["id", "author", "question", "answer"]
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                item = answer_payload(row)
                item["answer"] = json.dumps(item["answer"], ensure_ascii=False) if isinstance(item["answer"], (dict, list)) else item["answer"]
                writer.writerow(item)
            return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=t24-reponses.csv"})
        return Response(json.dumps([answer_payload(row) for row in rows], ensure_ascii=False, indent=2), mimetype="application/json", headers={"Content-Disposition": "attachment; filename=t24-reponses.json"})


def validated_question(data: dict[str, Any]) -> tuple[Any, ...]:
    title, body = str(data.get("title", "")).strip(), str(data.get("body", "")).strip()
    question_type, target_mode = data.get("type"), data.get("targetMode", "none")
    if not title or len(title) > 150 or not body or len(body) > 2000:
        abort_json(400, "Titre ou texte de question invalide.")
    if question_type not in QUESTION_TYPES or target_mode not in TARGET_MODES:
        abort_json(400, "Type ou ciblage de question invalide.")
    scale_min, scale_max = data.get("scaleMin"), data.get("scaleMax")
    if question_type == "slider":
        try:
            scale_min, scale_max = float(scale_min if scale_min is not None else 0), float(scale_max if scale_max is not None else 100)
        except (TypeError, ValueError):
            abort_json(400, "Bornes du curseur invalides.")
        if scale_min >= scale_max:
            abort_json(400, "Le minimum du curseur doit être inférieur au maximum.")
    return (
        title, body, question_type, str(data.get("category", "")).strip() or None, target_mode,
        scale_min, scale_max, int(bool(data.get("allowSelfTarget", False))),
        int(bool(data.get("isActive", True))), validated_display_order(data.get("displayOrder", 0)),
    )


def validated_display_order(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        abort_json(400, "Ordre d'affichage invalide.")


def answer_export_query(where: str = "") -> str:
    return """SELECT a.*, p.display_name author_name, tp.display_name target_name,
              q.id question_id, q.title question_title, qi.rendered_body,
              s.status session_status
              FROM answers a JOIN participants p ON p.id=a.author_participant_id
              LEFT JOIN participants tp ON tp.id=a.target_participant_id
              JOIN answer_sessions s ON s.id=a.session_id
              JOIN question_instances qi ON qi.id=a.question_instance_id
              JOIN questions q ON q.id=qi.question_id""" + where + " ORDER BY a.created_at DESC"


def answer_payload(row: sqlite3.Row) -> dict[str, Any]:
    answer: Any = row["answer_text"] if row["answer_text"] is not None else row["answer_number"]
    if row["answer_json"] is not None:
        answer = json.loads(row["answer_json"])
    return {
        "id": row["id"], "author": row["author_name"], "authorParticipantId": row["author_participant_id"],
        "sessionId": row["session_id"],
        "target": row["target_name"], "targetParticipantId": row["target_participant_id"],
        "questionId": row["question_id"], "questionInstanceId": row["question_instance_id"],
        "question": row["question_title"], "renderedQuestion": row["rendered_body"],
        "renderedBody": row["rendered_body"], "sessionCompleted": row["session_status"] == "completed",
        "answer": answer, "createdAt": row["created_at"],
    }


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("T24_DEBUG") == "1")
