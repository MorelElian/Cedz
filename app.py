from __future__ import annotations

import csv
import base64
import hashlib
import html
import io
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from functools import wraps
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from werkzeug.security import check_password_hash, generate_password_hash

from flask import (
    Flask,
    Response,
    abort,
    current_app,
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
    "choose_one",
    "ranking",
    "binary_split",
    "slider",
}
TARGET_MODES = {"none", "one_person", "two_people", "three_people", "all_people"}
QUESTIONNAIRE_TARGET_SIZE = 30
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 .()\-]{6,24}$")
REVELATION_STATUSES = {"candidate", "in_review", "skipped", "rejected", "sent"}
INTRO_TONES = {"pique", "positif"}
INTRO_PHRASE_CATALOG_VERSION = "2"
LEGACY_INTRO_PHRASES = (
    ("Pas la pêche aujourd'hui ?", "pique"),
    ("Ton ego avait besoin de nouvelles.", "pique"),
    ("On a encore parlé de toi.", "pique"),
    ("Une petite vérité avant l'entraînement ?", "pique"),
    ("Le comité n'oublie jamais.", "pique"),
    ("Tu pensais passer entre les gouttes ?", "pique"),
    ("Ton cardio ne lira peut-être pas ça.", "pique"),
    ("Une information parfaitement objective.", "pique"),
    ("Bonne nouvelle : quelqu'un croit en toi.", "positif"),
    ("Aujourd'hui, on te donne un peu de force.", "positif"),
    ("Le vestiaire a aussi de belles choses à dire.", "positif"),
    ("Petit rayon de soleil avant le T24.", "positif"),
    ("Quelqu'un mise clairement sur toi.", "positif"),
    ("Tu vas peut-être finir par nous impressionner.", "positif"),
    ("Garde ça pour ton prochain coup de mou.", "positif"),
)
DEFAULT_INTRO_PHRASES = (
    ("Tu chiales Aujourd'hui ?", "pique"),
    ("Sort les mouchoirs.", "pique"),
    ("On a encore parlé de toi.", "pique"),
    ("T'avais la flemme de t'entrainer ?", "pique"),
    ("La cedz tire vers le haut.", "pique"),
    ("Tu pensais passer entre les gouttes ?", "pique"),
    ("Ta grand mère la chauve.", "pique"),
    ("On voulait te dire un truc.", "pique"),
    ("Bonne nouvelle : quelqu'un croit en toi.", "positif"),
    ("Aujourd'hui, on te donne un peu de force.", "positif"),
    ("On t'aime bro.", "positif"),
    ("Ca vaut peut-être pas un café du BôB, mais ça va te faire plaisir.", "positif"),
    ("Quelqu'un a mis toutes ses économies sur toi.", "positif"),
    ("Tu vas peut-être finir par nous impressionner.", "positif"),
    ("Keep pushing mate!", "positif"),
)

BINARY_SPLIT_LABELS = {
    "Physique ou chance": ("Physique", "Chance"),
    "Se révéler ou craquer": ("Peut se révéler", "Peut craquer"),
    "Mental ou force": ("Gros mental", "Grosse force physique"),
    "Silence ou larmes": ("Souffre en silence", "Va chialer"),
    "Après minuit": ("Meilleur de nuit", "Négocie avec son âme"),
    "Gestion du chaos": ("Va gérer", "Ne va pas gérer"),
    "Moteurs ou diesels": ("Motive les autres", "À motiver"),
    "Sourire final": ("Finit avec le sourire", "Sourit pour les photos"),
    "Zug ou Bellagio": ("Se la met à Zug", "Chille à Bellagio"),
}

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
EXPORTED_PROFILE_NAMES = {index + 5: profile[0] for index, profile in enumerate(PROFILE_CATALOG)}

QUESTION_CATALOG = [
    ("Classement nage", "Classe les participants pour la nage.", "ranking", "Classement · Nage", "all_people", None, None),
    ("Classement vélo", "Classe les participants pour le vélo.", "ranking", "Classement · Vélo", "all_people", None, None),
    ("Classement course", "Classe les participants pour la course.", "ranking", "Classement · Course", "all_people", None, None),

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

    ("Comparaison de niveau", "Si tu devais comparer le niveau de {person1} à celui de {person2}, tu penses qu'ils pourraient devenir qui ?", "free_text", "Duels", "two_people", None, None),
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
        MAILS_FILE=os.environ.get("T24_MAILS_FILE", str(Path(__file__).with_name("mails.csv"))),
        ANSWERS_FILE=os.environ.get(
            "T24_ANSWERS_FILE", str(Path(__file__).with_name("answers") / "t24-reponses(1).json")
        ),
        AUTO_IMPORT_ANSWERS=False,
        MAIL_MODE=os.environ.get("T24_MAIL_MODE", "gmail").strip().lower(),
        SMTP_HOST=os.environ.get("T24_SMTP_HOST", "smtp.gmail.com"),
        SMTP_PORT=int(os.environ.get("T24_SMTP_PORT", "587")),
        SMTP_USERNAME=os.environ.get("T24_SMTP_USER", ""),
        SMTP_PASSWORD=os.environ.get("T24_SMTP_PASSWORD", ""),
        GMAIL_CLIENT_ID=os.environ.get("T24_GMAIL_CLIENT_ID", ""),
        GMAIL_CLIENT_SECRET=os.environ.get("T24_GMAIL_CLIENT_SECRET", ""),
        GMAIL_REFRESH_TOKEN=os.environ.get("T24_GMAIL_REFRESH_TOKEN", ""),
        GMAIL_USER=os.environ.get("T24_GMAIL_USER", ""),
        MAIL_FROM=os.environ.get(
            "T24_MAIL_FROM", os.environ.get("T24_GMAIL_USER", os.environ.get("T24_SMTP_USER", ""))
        ),
        PUBLIC_BASE_URL=os.environ.get("T24_PUBLIC_BASE_URL", "").strip().rstrip("/"),
        SMTP_TIMEOUT=20,
        MAX_CONTENT_LENGTH=6_000_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("T24_SECURE_COOKIE", "0") == "1",
    )
    if config:
        app.config.update(config)
    if app.config["TESTING"] and not (config and "MAIL_MODE" in config):
        app.config["MAIL_MODE"] = "simulate"
    if app.config["MAIL_MODE"] not in {"simulate", "gmail", "gmail_api"}:
        raise RuntimeError("T24_MAIL_MODE doit valoir 'simulate', 'gmail' ou 'gmail_api'.")
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
        seed_communication_data(app.config["MAILS_FILE"])
        if app.config["AUTO_IMPORT_ANSWERS"]:
            answers_path = Path(app.config["ANSWERS_FILE"])
            if answers_path.is_file():
                import_answers(json.loads(answers_path.read_text(encoding="utf-8")), answers_path.name)
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
        CREATE TABLE IF NOT EXISTS question_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_participant_id INTEGER NOT NULL REFERENCES participants(id),
            body TEXT NOT NULL, question_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'submitted',
            admin_note TEXT, approved_question_id INTEGER REFERENCES questions(id),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS daily_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL REFERENCES participants(id),
            question_id INTEGER NOT NULL REFERENCES questions(id),
            target_participant_id INTEGER REFERENCES participants(id),
            target_participant_2_id INTEGER REFERENCES participants(id),
            target_participant_3_id INTEGER REFERENCES participants(id),
            rendered_body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
            available_after TEXT, imported_answer_id INTEGER REFERENCES imported_answers(id),
            assigned_at TEXT NOT NULL, answered_at TEXT, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_daily_questions_participant ON daily_questions(participant_id, status);
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imported_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL UNIQUE,
            source_session_id TEXT,
            external_answer_id INTEGER,
            author_participant_id INTEGER NOT NULL REFERENCES participants(id),
            target_participant_id INTEGER REFERENCES participants(id),
            question_id INTEGER,
            question_instance_id INTEGER,
            question_title TEXT NOT NULL,
            rendered_question TEXT NOT NULL,
            question_type TEXT NOT NULL,
            answer_text TEXT,
            answer_number REAL,
            answer_json TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            source_created_at TEXT,
            imported_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_imported_answers_author ON imported_answers(author_participant_id);
        CREATE INDEX IF NOT EXISTS idx_imported_answers_target ON imported_answers(target_participant_id);
        CREATE TABLE IF NOT EXISTS intro_phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            tone TEXT NOT NULL CHECK(tone IN ('pique', 'positif')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS revelations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_answer_id INTEGER NOT NULL REFERENCES imported_answers(id),
            recipient_participant_id INTEGER NOT NULL REFERENCES participants(id),
            author_participant_id INTEGER NOT NULL REFERENCES participants(id),
            question_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'candidate',
            tone TEXT NOT NULL DEFAULT 'pique',
            intro_phrase_id INTEGER REFERENCES intro_phrases(id),
            intro_text TEXT,
            final_content TEXT,
            admin_edited INTEGER NOT NULL DEFAULT 0,
            content_json TEXT NOT NULL,
            subject_snapshot TEXT,
            html_snapshot TEXT,
            content_snapshot TEXT,
            recipient_email_snapshot TEXT,
            sent_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(imported_answer_id, recipient_participant_id)
        );
        CREATE INDEX IF NOT EXISTS idx_revelations_review ON revelations(recipient_participant_id, status);
        CREATE TABLE IF NOT EXISTS revelation_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revelation_id INTEGER NOT NULL UNIQUE REFERENCES revelations(id),
            participant_id INTEGER NOT NULL REFERENCES participants(id),
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS participant_intro_usage (
            participant_id INTEGER NOT NULL REFERENCES participants(id),
            intro_phrase_id INTEGER NOT NULL REFERENCES intro_phrases(id),
            use_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            PRIMARY KEY(participant_id, intro_phrase_id)
        );
        """
    )
    _db().execute(
        "UPDATE questions SET title=substr(title, 14) WHERE title LIKE 'Suggestion · %'"
    )
    participant_columns = {row["name"] for row in _db().execute("PRAGMA table_info(participants)")}
    if "profile_photo_url" not in participant_columns:
        _db().execute("ALTER TABLE participants ADD COLUMN profile_photo_url TEXT")
    session_columns = {row["name"] for row in _db().execute("PRAGMA table_info(answer_sessions)")}
    if "feedback" not in session_columns:
        _db().execute("ALTER TABLE answer_sessions ADD COLUMN feedback TEXT")
    if "resume_token_hash" not in session_columns:
        _db().execute("ALTER TABLE answer_sessions ADD COLUMN resume_token_hash TEXT")
    if "password_hash" not in participant_columns:
        _db().execute("ALTER TABLE participants ADD COLUMN password_hash TEXT")
    revelation_columns = {row["name"] for row in _db().execute("PRAGMA table_info(revelations)")}
    if "admin_edited" not in revelation_columns:
        _db().execute("ALTER TABLE revelations ADD COLUMN admin_edited INTEGER NOT NULL DEFAULT 0")
    imported_columns = {row["name"] for row in _db().execute("PRAGMA table_info(imported_answers)")}
    if "source_session_id" not in imported_columns:
        _db().execute("ALTER TABLE imported_answers ADD COLUMN source_session_id TEXT")
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


def seed_communication_data(mails_file: str) -> None:
    db, now = _db(), utcnow()
    catalog_version = db.execute(
        "SELECT value FROM site_settings WHERE key='intro_phrase_catalog_version'"
    ).fetchone()
    if not catalog_version or catalog_version["value"] != INTRO_PHRASE_CATALOG_VERSION:
        managed_texts = {text for text, _ in LEGACY_INTRO_PHRASES + DEFAULT_INTRO_PHRASES}
        placeholders = ",".join("?" for _ in managed_texts)
        db.execute(
            f"UPDATE intro_phrases SET is_active=0, updated_at=? WHERE text IN ({placeholders})",
            (now, *managed_texts),
        )
        for (legacy_text, _), (text, tone) in zip(LEGACY_INTRO_PHRASES, DEFAULT_INTRO_PHRASES):
            phrase = db.execute(
                "SELECT id FROM intro_phrases WHERE text=? ORDER BY id LIMIT 1", (text,)
            ).fetchone()
            if not phrase:
                phrase = db.execute(
                    "SELECT id FROM intro_phrases WHERE text=? ORDER BY id LIMIT 1", (legacy_text,)
                ).fetchone()
            if phrase:
                db.execute(
                    "UPDATE intro_phrases SET text=?, tone=?, is_active=1, updated_at=? WHERE id=?",
                    (text, tone, now, phrase["id"]),
                )
            else:
                phrase = db.execute(
                    "INSERT INTO intro_phrases(text, tone, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (text, tone, now, now),
                )
            phrase_id = phrase["id"] if isinstance(phrase, sqlite3.Row) else phrase.lastrowid
            db.execute(
                """UPDATE revelations SET intro_text=?, updated_at=?
                   WHERE intro_phrase_id=? AND status!='sent' AND admin_edited=0""",
                (text, now, phrase_id),
            )
        db.execute(
            """INSERT INTO site_settings(key, value, updated_at)
               VALUES ('intro_phrase_catalog_version', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (INTRO_PHRASE_CATALOG_VERSION, now),
        )
    path = Path(mails_file)
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as handle:
            for item in csv.DictReader(handle):
                email = str(item.get("email", "")).strip().lower()
                name = str(item.get("display_name", "")).strip()
                participant = db.execute(
                    "SELECT id,display_name FROM participants WHERE display_name=? COLLATE NOCASE", (name,)
                ).fetchone()
                if not participant:
                    try:
                        participant = db.execute("SELECT id,display_name FROM participants WHERE id=?",
                                                 (int(item.get("participant_id", "")),)).fetchone()
                    except ValueError:
                        participant = None
                if participant and (not email or EMAIL_RE.fullmatch(email)):
                    db.execute(
                        "UPDATE participants SET email=COALESCE(NULLIF(?, ''), email), updated_at=? WHERE id=?",
                        (email, now, participant["id"]),
                    )
    db.commit()


def participant_ids_in_text(value: str) -> list[int]:
    return [row["id"] for row in _db().execute(
        "SELECT id, display_name FROM participants WHERE is_active=1 ORDER BY id"
    ) if re.search(rf"(?<!\w){re.escape(row['display_name'])}(?!\w)", value, re.IGNORECASE)]


def infer_question_type(item: dict[str, Any], answer: Any) -> str:
    if isinstance(answer, dict):
        if "ordered_participant_ids" in answer:
            return "ranking"
        if "category_a" in answer and "category_b" in answer:
            return "binary_split"
        if "selected_participant_id" in answer:
            rendered = str(item.get("renderedQuestion") or item.get("renderedBody") or "")
            return "compare_three" if len(participant_ids_in_text(rendered)) >= 3 else "compare_two"
    if isinstance(answer, (int, float)) and not isinstance(answer, bool):
        return "slider"
    return {values[0]: values[2] for values in QUESTION_CATALOG}.get(str(item.get("question", "")), "free_text")


def import_answers(items: Any, source_name: str = "manual.json") -> dict[str, int]:
    del source_name
    if isinstance(items, dict):
        items = items.get("answers")
    if not isinstance(items, list):
        raise ValueError("Le fichier doit contenir une liste de réponses.")
    db, now = _db(), utcnow()
    people = db.execute("SELECT id,display_name,email FROM participants").fetchall()
    names = {row["display_name"].casefold(): row["id"] for row in people}
    emails = {row["id"]: row["email"] or "" for row in people}
    valid_ids = set(emails)

    def resolved_id(value: Any) -> int:
        try:
            external = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Identifiant participant externe invalide : {value!r}.") from error
        exported_name = EXPORTED_PROFILE_NAMES.get(external)
        result = names.get(exported_name.casefold()) if exported_name else external
        if result not in valid_ids:
            raise ValueError(f"Participant externe inconnu : {external}.")
        return result

    normalized = []
    for index, original in enumerate(items):
        if not isinstance(original, dict):
            raise ValueError(f"Réponse #{index + 1} invalide.")
        item = dict(original)
        author_id = names.get(str(item.get("author", "")).casefold())
        if not author_id and item.get("authorParticipantId") is not None:
            author_id = resolved_id(item["authorParticipantId"])
        if not author_id:
            raise ValueError(f"Auteur inconnu pour la réponse #{index + 1}.")
        target_id = names.get(str(item.get("target", "")).casefold())
        if not target_id and item.get("targetParticipantId") is not None:
            target_id = resolved_id(item["targetParticipantId"])
        answer = item.get("answer")
        if isinstance(answer, dict):
            answer = dict(answer)
            for key in ("ordered_participant_ids", "category_a", "category_b"):
                if key in answer:
                    if not isinstance(answer[key], list):
                        raise ValueError(f"Liste {key} invalide dans la réponse #{index + 1}.")
                    answer[key] = [resolved_id(value) for value in answer[key]]
            if "selected_participant_id" in answer:
                answer["selected_participant_id"] = resolved_id(answer["selected_participant_id"])
        item["_author_id"], item["_target_id"], item["_answer"] = author_id, target_id, answer
        normalized.append(item)

    imported = updated = 0
    db.execute("BEGIN IMMEDIATE")
    try:
        for item in normalized:
            answer, external_id = item["_answer"], item.get("id")
            source_key = (f"answer:{external_id}" if external_id is not None else "hash:" + hashlib.sha256(
                json.dumps(item, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest())
            values = (
                str(item.get("sessionId") or "") or None, external_id, item["_author_id"], item["_target_id"],
                item.get("questionId"), item.get("questionInstanceId"), str(item.get("question") or "Question"),
                str(item.get("renderedQuestion") or item.get("renderedBody") or item.get("question") or "Question"),
                infer_question_type(item, answer), answer if isinstance(answer, str) else None,
                float(answer) if isinstance(answer, (int, float)) and not isinstance(answer, bool) else None,
                json.dumps(answer, ensure_ascii=False, sort_keys=True) if isinstance(answer, (dict, list)) else None,
                str(item.get("createdAt") or "") or None, now,
            )
            existing = db.execute("SELECT id FROM imported_answers WHERE source_key=?", (source_key,)).fetchone()
            if existing:
                db.execute(
                    """UPDATE imported_answers SET source_session_id=?,external_answer_id=?,author_participant_id=?,
                       target_participant_id=?,question_id=?,question_instance_id=?,question_title=?,rendered_question=?,
                       question_type=?,answer_text=?,answer_number=?,answer_json=?,is_active=1,source_created_at=?,updated_at=?
                       WHERE source_key=?""", (*values, source_key),
                )
                updated += 1
            else:
                db.execute(
                    """INSERT INTO imported_answers(source_key,source_session_id,external_answer_id,author_participant_id,
                       target_participant_id,question_id,question_instance_id,question_title,rendered_question,question_type,
                       answer_text,answer_number,answer_json,source_created_at,imported_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (source_key, *values, now),
                )
                imported += 1
        sessions: dict[str, tuple[int, bool, str]] = {}
        for item in normalized:
            session_id = str(item.get("sessionId") or "")
            if not session_id:
                continue
            previous = sessions.get(session_id)
            sessions[session_id] = (item["_author_id"], bool(item.get("sessionCompleted")) or bool(previous and previous[1]),
                                    str(item.get("createdAt") or now))
        for session_id, (author_id, completed, created_at) in sessions.items():
            status = "completed" if completed else "started"
            db.execute(
                """INSERT INTO answer_sessions(id,participant_id,email,phone,status,started_at,completed_at,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                   participant_id=excluded.participant_id,
                   status=CASE WHEN answer_sessions.status='completed' OR excluded.status='completed' THEN 'completed' ELSE 'started' END,
                   completed_at=COALESCE(answer_sessions.completed_at,excluded.completed_at),updated_at=excluded.updated_at""",
                (session_id, author_id, emails[author_id], "", status, created_at,
                 created_at if completed else None, created_at, now),
            )
        generated = generate_revelation_candidates(commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"imported": imported, "updated": updated, "ignored": 0, "generated": generated}


def revelation_recipient_ids(row: sqlite3.Row, answer: Any) -> list[int]:
    if row["question_type"] == "choose_one":
        ids = [answer.get("selected_participant_id")] if isinstance(answer, dict) else []
    elif row["question_type"] == "ranking":
        ids = answer.get("ordered_participant_ids", []) if isinstance(answer, dict) else []
    elif row["question_type"] == "binary_split":
        ids = answer.get("category_a", []) + answer.get("category_b", []) if isinstance(answer, dict) else []
    else:
        ids = participant_ids_in_text(row["rendered_question"])
        if row["target_participant_id"] and row["target_participant_id"] not in ids:
            ids.insert(0, row["target_participant_id"])
    valid = {item["id"] for item in _db().execute("SELECT id FROM participants WHERE is_active=1")}
    return list(dict.fromkeys(int(value) for value in ids if value in valid and value != row["author_participant_id"]))


def revelation_content(row: sqlite3.Row, recipient_id: int, answer: Any) -> dict[str, Any]:
    names = {item["id"]: item["display_name"] for item in _db().execute("SELECT id,display_name FROM participants")}
    base = {"question": row["rendered_question"], "questionTitle": row["question_title"],
            "author": names[row["author_participant_id"]], "recipient": names[recipient_id]}
    if row["question_type"] in {"compare_two", "compare_three", "choose_one"}:
        selected = int(answer.get("selected_participant_id"))
        base.update(selectedParticipant=names.get(selected), selected=selected == recipient_id,
                    comment=str(answer.get("comment", "")))
    elif row["question_type"] == "ranking":
        ordered = [int(value) for value in answer.get("ordered_participant_ids", [])]
        if recipient_id not in ordered:
            raise ValueError("Classement incomplet dans l'export.")
        position = ordered.index(recipient_id) + 1
        base.update(position=position, ahead=names.get(ordered[position - 2]) if position > 1 else None,
                    discipline=row["question_title"].replace("Classement", "").strip().casefold())
    elif row["question_type"] == "binary_split":
        first, second = answer.get("category_a", []), answer.get("category_b", [])
        labels = BINARY_SPLIT_LABELS.get(row["question_title"], ("Groupe A", "Groupe B"))
        base.update(groups=[{"label": labels[0], "people": [names.get(int(i), str(i)) for i in first]},
                            {"label": labels[1], "people": [names.get(int(i), str(i)) for i in second]}],
                    recipientGroup=labels[0] if recipient_id in first else labels[1])
    else:
        base["answer"] = row["answer_text"] if row["answer_text"] is not None else row["answer_number"]
    return base


def generate_revelation_candidates(*, commit: bool = True) -> int:
    db, now, generated = _db(), utcnow(), 0
    positive_tokens = ("motivation", "qualité", "surprise", "respect", "meilleure version")
    for row in db.execute("SELECT * FROM imported_answers WHERE is_active=1 ORDER BY id").fetchall():
        answer = json.loads(row["answer_json"]) if row["answer_json"] else (
            row["answer_text"] if row["answer_text"] is not None else row["answer_number"])
        for recipient_id in revelation_recipient_ids(row, answer):
            content = revelation_content(row, recipient_id, answer)
            tone = "positif" if any(token in row["question_title"].casefold() for token in positive_tokens) else "pique"
            existed = db.execute(
                "SELECT 1 FROM revelations WHERE imported_answer_id=? AND recipient_participant_id=?",
                (row["id"], recipient_id),
            ).fetchone()
            db.execute(
                """INSERT INTO revelations(imported_answer_id,recipient_participant_id,author_participant_id,
                   question_type,tone,content_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(imported_answer_id,recipient_participant_id) DO UPDATE SET
                   content_json=excluded.content_json,question_type=excluded.question_type,
                   author_participant_id=excluded.author_participant_id,tone=excluded.tone,
                   final_content=CASE WHEN revelations.admin_edited=1 THEN revelations.final_content ELSE NULL END,
                   updated_at=excluded.updated_at
                   WHERE revelations.status NOT IN ('sent','rejected')""",
                (row["id"], recipient_id, row["author_participant_id"], row["question_type"], tone,
                 json.dumps(content, ensure_ascii=False), now, now),
            )
            generated += int(not existed)
    if commit:
        db.commit()
    return generated


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
    if not catalog_version or catalog_version["value"] != "3":
        comparison_body = next(
            body for title, body, *_ in QUESTION_CATALOG if title == "Comparaison de niveau"
        )
        # Preserve old answers while retiring the six placeholders from the MVP.
        db.execute("UPDATE questions SET is_active = 0, updated_at = ? WHERE category = 'Démo'", (now,))
        db.execute(
            """UPDATE questions SET is_active = 0, updated_at = ?
               WHERE title = 'Classement des disciplines'""",
            (now,),
        )
        # The original Markdown expects a free comparison, not a forced choice
        # between the two named people. Keep any historic answers on the retired row.
        db.execute(
            """UPDATE questions SET is_active = 0, updated_at = ?
               WHERE title = 'Comparaison de niveau'
                 AND (body != ? OR type != 'free_text')""",
            (now, comparison_body),
        )
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
            """INSERT INTO site_settings(key, value, updated_at) VALUES ('question_catalog_version', '3', ?)
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


DAILY_QUESTION_TYPES = {"free_text", "compare_two", "compare_three", "choose_one", "slider"}


def daily_question_payload(row: sqlite3.Row) -> dict[str, Any]:
    targets = [{"id": row[key], "displayName": row[f"{key}_name"]}
               for key in ("target_participant_id", "target_participant_2_id", "target_participant_3_id")
               if row[key] is not None]
    if row["type"] == "choose_one":
        targets = [participant_payload(person) for person in _db().execute(
            "SELECT * FROM participants WHERE is_active=1 AND id!=? ORDER BY display_name", (row["participant_id"],)
        ).fetchall()]
    return {
        "id": row["id"], "questionId": row["question_id"], "title": row["title"],
        "body": row["rendered_body"], "type": row["type"], "category": row["category"],
        "scaleMin": row["scale_min"], "scaleMax": row["scale_max"],
        "targets": targets,
        "status": row["status"], "availableAfter": row["available_after"],
    }


def current_daily_question(participant_id: int, *, force: bool = False, question_id: int | None = None) -> sqlite3.Row | None:
    db = _db()
    active = db.execute(
        """SELECT d.*,q.title,q.type,q.category,q.scale_min,q.scale_max,
                  p1.display_name target_participant_id_name,p2.display_name target_participant_2_id_name,
                  p3.display_name target_participant_3_id_name
           FROM daily_questions d JOIN questions q ON q.id=d.question_id
           LEFT JOIN participants p1 ON p1.id=d.target_participant_id
           LEFT JOIN participants p2 ON p2.id=d.target_participant_2_id
           LEFT JOIN participants p3 ON p3.id=d.target_participant_3_id
           WHERE d.participant_id=? AND d.status='active' ORDER BY d.id DESC LIMIT 1""", (participant_id,)
    ).fetchone()
    if active and not force:
        return active
    if active:
        db.execute("UPDATE daily_questions SET status='replaced',updated_at=? WHERE id=?", (utcnow(), active["id"]))
    latest = db.execute(
        "SELECT available_after FROM daily_questions WHERE participant_id=? AND status='answered' ORDER BY answered_at DESC LIMIT 1",
        (participant_id,),
    ).fetchone()
    if not force and latest and latest["available_after"] and latest["available_after"] > utcnow():
        return None
    people = db.execute("SELECT id,display_name FROM participants WHERE is_active=1 AND id!=? ORDER BY id", (participant_id,)).fetchall()
    candidates = db.execute(
        "SELECT * FROM questions WHERE is_active=1 AND type IN ('free_text','compare_two','compare_three','slider')"
        + (" AND id=?" if question_id else "") + " ORDER BY id", ((question_id,) if question_id else ())
    ).fetchall()
    rng = secrets.SystemRandom()
    rng.shuffle(candidates)
    for question in candidates:
        count = {"free_text": 1, "slider": 1, "compare_two": 2, "compare_three": 3, "choose_one": 0}[question["type"]]
        if len(people) < count:
            continue
        group = rng.sample(people, count)
        ids = sorted(person["id"] for person in group)
        seen = db.execute(
            """SELECT 1 FROM daily_questions WHERE participant_id=? AND question_id=?
               AND COALESCE(target_participant_id,-1)=? AND COALESCE(target_participant_2_id,-1)=?
               AND COALESCE(target_participant_3_id,-1)=? AND status!='replaced' LIMIT 1""",
            (participant_id, question["id"], *(ids + [-1] * (3 - len(ids)))),
        ).fetchone()
        if seen and not force:
            continue
        ordered = [next(person for person in people if person["id"] == target_id) for target_id in ids]
        now = utcnow()
        cursor = db.execute(
            """INSERT INTO daily_questions(participant_id,question_id,target_participant_id,target_participant_2_id,target_participant_3_id,
               rendered_body,status,assigned_at,updated_at) VALUES (?,?,?,?,?,?, 'active',?,?)""",
            (participant_id, question["id"], *(ids + [None] * (3 - len(ids))), render_question(question["body"], ordered), now, now),
        )
        db.commit()
        return current_daily_question(participant_id)
    db.commit()
    return None


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


def participant_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        participant_id = session.get("participant_id")
        participant = None
        if participant_id:
            participant = _db().execute(
                "SELECT * FROM participants WHERE id = ? AND is_active = 1", (participant_id,)
            ).fetchone()
        if not participant:
            if request.path.startswith("/api/"):
                abort_json(401, "Authentification participant requise.")
            return redirect(url_for("participant_login", next=request.path))
        g.current_participant = participant
        return view(*args, **kwargs)

    return wrapped


def require_session_owner(answer_session: sqlite3.Row, *, allow_completed: bool = False) -> None:
    if not session.get("participant_id") or session["participant_id"] != answer_session["participant_id"]:
        abort_json(403, "Cette participation appartient à un autre compte.")
    if not allow_completed and answer_session["status"] == "completed":
        abort_json(403, "Ce questionnaire est déjà terminé.")


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)
    return session["csrf_token"]


def protect_admin_mutations() -> None:
    is_protected_mutation = (
        request.method in {"POST", "PATCH", "PUT", "DELETE"}
        and (
            request.path.startswith("/api/admin/")
            or request.path.startswith("/api/account/")
            or request.path in {"/admin/logout", "/logout"}
        )
    )
    if not is_protected_mutation:
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
        result.update(email=row["email"], phone=row["phone"], secretCode=row["secret_code"],
                      hasPassword=bool(row["password_hash"]))
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
        """SELECT qi.*, q.title, q.type, q.category, q.scale_min, q.scale_max, q.allow_self_target, q.display_order
           FROM question_instances qi JOIN questions q ON q.id = qi.question_id
           WHERE qi.is_active = 1 AND q.is_active = 1
             AND (q.allow_self_target = 1 OR ? NOT IN (
                 COALESCE(qi.target_participant_id, -1), COALESCE(qi.target_participant_2_id, -1),
                 COALESCE(qi.target_participant_3_id, -1)))
           ORDER BY q.display_order, qi.id""",
        (participant_id,),
    ).fetchall()
    selected: list[sqlite3.Row] = []
    variants: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        variants.setdefault(row["question_id"], []).append(row)
    for question_id, candidates in variants.items():
        candidates.sort(
            key=lambda row: hashlib.sha256(
                f"{session_id}:{question_id}:{row['id']}".encode()
            ).digest()
        )
        selected.extend(candidates[:2])
    mandatory = [row for row in selected if row["type"] == "ranking"]
    optional = [row for row in selected if row["type"] != "ranking"]
    optional.sort(
        key=lambda row: hashlib.sha256(
            f"{session_id}:questionnaire:{row['id']}".encode()
        ).digest()
    )
    optional_slots = max(0, QUESTIONNAIRE_TARGET_SIZE - len(mandatory))
    selected = mandatory + optional[:optional_slots]
    imported_keys = {
        (row["question_title"], row["rendered_question"])
        for row in _db().execute(
            """SELECT question_title,rendered_question FROM imported_answers
               WHERE source_session_id=? AND is_active=1""", (session_id,)
        )
    }
    answered_rows = [row for row in rows if (row["title"], row["rendered_body"]) in imported_keys]
    selected_ids = {row["id"] for row in selected}
    for row in answered_rows:
        if row["id"] not in selected_ids:
            selected.append(row)
            selected_ids.add(row["id"])
    protected_ids = {row["id"] for row in mandatory + answered_rows}
    while len(selected) > QUESTIONNAIRE_TARGET_SIZE:
        removable = next((row for row in reversed(selected) if row["id"] not in protected_ids), None)
        if not removable:
            break
        selected.remove(removable)
    return sorted(selected, key=lambda row: (row["display_order"], row["id"]))


def imported_session_answers(session_id: str, question_rows: list[sqlite3.Row]) -> dict[int, Any]:
    by_key = {(row["title"], row["rendered_body"]): row["id"] for row in question_rows}
    result: dict[int, Any] = {}
    for row in _db().execute(
        """SELECT * FROM imported_answers WHERE source_session_id=? AND is_active=1
           ORDER BY source_created_at,id""", (session_id,)
    ):
        instance_id = by_key.get((row["question_title"], row["rendered_question"]))
        if instance_id is not None:
            result[instance_id] = answer_value(row)
    return result


def session_answer_values(session_id: str, question_rows: list[sqlite3.Row]) -> dict[int, Any]:
    """Return every saved answer that belongs to this participant's 30-question set."""
    allowed_instance_ids = {row["id"] for row in question_rows}
    result = imported_session_answers(session_id, question_rows)
    for saved in _db().execute(
        """SELECT question_instance_id, answer_text, answer_number, answer_json
           FROM answers WHERE session_id = ?""",
        (session_id,),
    ):
        instance_id = saved["question_instance_id"]
        if instance_id not in allowed_instance_ids:
            continue
        value: Any = saved["answer_text"]
        if saved["answer_json"] is not None:
            value = json.loads(saved["answer_json"])
        elif saved["answer_number"] is not None:
            value = saved["answer_number"]
        result[instance_id] = value
    return result


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

    @app.route("/login", methods=["GET", "POST"])
    def participant_login():
        error = None
        if request.method == "POST":
            data = request.get_json(silent=True) if request.is_json else request.form
            name = str((data or {}).get("name", "")).strip()
            password = str((data or {}).get("password", ""))
            participant = _db().execute(
                "SELECT * FROM participants WHERE display_name = ? COLLATE NOCASE AND is_active = 1",
                (name,),
            ).fetchone()
            if participant and participant["password_hash"] and check_password_hash(participant["password_hash"], password):
                session.clear()
                session["participant_id"] = participant["id"]
                token = csrf_token()
                destination = request.args.get("next") or url_for("account_page")
                if not destination.startswith("/") or destination.startswith("//"):
                    destination = url_for("account_page")
                if request.is_json:
                    return jsonify({"authenticated": True, "redirectUrl": destination, "csrfToken": token})
                return redirect(destination)
            error = "Nom ou mot de passe incorrect."
            if request.is_json:
                abort_json(401, error)
        return render_template("participant_login.html", error=error)

    @app.post("/logout")
    def participant_logout():
        session.clear()
        return redirect(url_for("participant_login"))

    @app.get("/compte")
    @app.get("/mon-compte")
    @participant_required
    def account_page():
        return render_template("participant_dashboard.html", csrf_token=csrf_token())

    @app.get("/revelations/<int:revelation_id>")
    @participant_required
    def revelation_detail_page(revelation_id: int):
        row = _db().execute(
            "SELECT 1 FROM revelations WHERE id=? AND recipient_participant_id=? AND status='sent'",
            (revelation_id, g.current_participant["id"]),
        ).fetchone()
        if not row:
            abort(404)
        return render_template("revelation_detail.html", revelation_id=revelation_id, csrf_token=csrf_token())

    @app.get("/questionnaire/<session_id>")
    @participant_required
    def questionnaire(session_id: str):
        answer_session = get_answer_session(session_id)
        require_session_owner(answer_session)
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
        if not session.get("participant_id"):
            abort_json(401, "Authentification participant requise.")
        if session["participant_id"] != participant_id:
            abort_json(403, "Tu ne peux ouvrir que ta propre participation.")
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
        require_session_owner(answer_session)
        rows = session_question_rows(session_id, answer_session["participant_id"])
        participants = _db().execute("SELECT * FROM participants WHERE is_active = 1 ORDER BY display_name").fetchall()
        questions = []
        for row in rows:
            targets = [row[key] for key in ("target_participant_id", "target_participant_2_id", "target_participant_3_id") if row[key] is not None]
            questions.append({
                "instanceId": row["id"], "questionId": row["question_id"],
                "title": row["title"],
                "body": row["rendered_body"], "type": row["type"], "category": row["category"],
                "targetParticipantIds": targets, "scaleMin": row["scale_min"], "scaleMax": row["scale_max"],
                "categoryLabels": BINARY_SPLIT_LABELS.get(row["title"]),
            })
        saved_values = session_answer_values(session_id, rows)
        remaining_questions = [item for item in questions if item["instanceId"] not in saved_values]
        return jsonify({
            "questions": remaining_questions,
            "participants": [participant_payload(row) for row in participants],
            "answersByInstance": {str(key): value for key, value in saved_values.items()},
            "answeredCount": len(saved_values),
            "remainingCount": len(remaining_questions),
            "totalCount": len(rows),
        })

    @app.post("/api/sessions/<session_id>/answers")
    def save_answer(session_id: str):
        answer_session = get_answer_session(session_id)
        require_session_owner(answer_session)
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
        require_session_owner(answer_session)
        expected_ids = {
            row["id"] for row in session_question_rows(session_id, answer_session["participant_id"])
        }
        answered_ids = set(session_answer_values(
            session_id, list(session_question_rows(session_id, answer_session["participant_id"]))
        ))
        missing = expected_ids - answered_ids
        if missing:
            abort_json(409, f"Il reste {len(missing)} réponse(s) à compléter.")
        now = utcnow()
        _db().execute("UPDATE answer_sessions SET status='completed', completed_at=?, updated_at=? WHERE id=?", (now, now, session_id))
        _db().commit()
        return jsonify({"completed": True, "redirectUrl": url_for("merci_session", session_id=session_id)})

    @app.post("/api/sessions/<session_id>/feedback")
    def save_feedback(session_id: str):
        answer_session = get_answer_session(session_id)
        require_session_owner(answer_session, allow_completed=True)
        message = str(json_body().get("message", "")).strip()
        if not message or len(message) > 2000:
            abort_json(400, "Le message doit contenir entre 1 et 2000 caractères.")
        _db().execute("UPDATE answer_sessions SET feedback = ?, updated_at = ? WHERE id = ?", (message, utcnow(), session_id))
        _db().commit()
        return jsonify({"saved": True})

    register_account_api(app)
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
    if question_type in {"compare_two", "compare_three", "choose_one"}:
        try:
            selected = int(answer.get("selectedParticipantId"))
        except (TypeError, ValueError):
            abort_json(400, "Choix invalide.")
        allowed_ids = active_ids if question_type == "choose_one" else set(target_ids)
        if selected not in allowed_ids:
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
        lap_time = str(answer.get("lapTime", answer.get("lap_time", ""))).strip()
        if not lap_time or len(lap_time) > 100:
            abort_json(400, "Le temps par tour doit contenir entre 1 et 100 caractères.")
        return None, None, {"ordered_participant_ids": ids, "lap_time": lap_time}
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


def answer_value(row: sqlite3.Row) -> Any:
    if row["answer_json"] is not None:
        return json.loads(row["answer_json"])
    return row["answer_text"] if row["answer_text"] is not None else row["answer_number"]


def format_revelation_content(row: sqlite3.Row) -> str:
    content = json.loads(row["content_json"])
    author, question = content["author"], content["question"]
    kind = row["question_type"]
    if kind in {"compare_two", "compare_three", "choose_one"}:
        verdict = "Il t'a choisi." if content["selected"] else f"Il a choisi {content['selectedParticipant']}."
        comment = f" Son commentaire : {content['comment']}" if content.get("comment") else ""
        return f"On a demandé à {author} : {question} {verdict}{comment}"
    if kind == "ranking":
        if content["position"] == 1:
            verdict = "Il t'a mis premier. Bravo, ne prends pas trop la confiance."
        else:
            verdict = f"Il t'a mis {content['position']}e, juste derrière {content['ahead']}. Mange-le !"
        return f"Pour le classement {content['discipline']}, {author} a parlé : {verdict}"
    if kind == "binary_split":
        groups = " — ".join(
            f"{group['label']} : {', '.join(group['people'])}" for group in content["groups"]
        )
        return f"{author} a dû répartir tout le monde pour « {question} ». {groups}"
    return f"Voilà ce que {author} pense de toi lorsqu'on lui demande : « {question} » Réponse : {content.get('answer')}"


def render_revelation_email(row: sqlite3.Row, final_content: str) -> str:
    data = json.loads(row["content_json"])
    kind = row["question_type"]
    public_base = str(current_app.config.get("PUBLIC_BASE_URL", "")).rstrip("/")
    detail_path = url_for("revelation_detail_page", revelation_id=row["id"])
    detail_url = public_base + detail_path if public_base else url_for(
        "revelation_detail_page", revelation_id=row["id"], _external=True
    )
    account_path = url_for("account_page")
    account_url = public_base + account_path if public_base else url_for("account_page", _external=True)
    daily_row = _db().execute(
        """SELECT rendered_body FROM daily_questions
           WHERE participant_id=? AND status='active' ORDER BY id DESC LIMIT 1""",
        (row["recipient_participant_id"],),
    ).fetchone()
    daily_question = daily_row["rendered_body"] if daily_row else "Une nouvelle question bonus t'attend dans ton espace."
    logo_row = _db().execute("SELECT value FROM site_settings WHERE key='logo_url'").fetchone()
    logo_path = logo_row["value"] if logo_row and logo_row["value"] else url_for("project_logo")
    logo_url = ((public_base or request.url_root.rstrip("/")) + logo_path
                if logo_path.startswith("/") else logo_path)
    photo_url = row["author_photo"] or ""
    if photo_url.startswith("/"):
        photo_url = (public_base or request.url_root.rstrip("/")) + photo_url
    if kind in {"compare_two", "compare_three", "choose_one"}:
        verdict = "CHOISI" if data["selected"] else f"{data['selectedParticipant']} choisi"
        detail = ("<div class='verdict' style='margin:26px 0 8px;color:#d45a45;"
                  f"font-size:46px;font-weight:900;line-height:1.1'>{html.escape(verdict)}</div>")
        if data.get("comment"):
            detail += ("<blockquote style='margin:24px 0 0;padding:18px 22px;border-left:4px solid #ffc83d;"
                       f"background:#f4f1e9;font-size:18px;line-height:1.65'>{html.escape(data['comment'])}</blockquote>")
    elif kind == "ranking":
        position = int(data["position"])
        detail = ("<div class='rank' style='margin:26px 0 8px;color:#d45a45;font-size:46px;"
                  f"font-weight:900;line-height:1.1'>{position}<sup>e</sup></div>")
        detail += ("<p>Première place. Propre.</p>" if position == 1 else
                   f"<p>Juste devant toi : <strong>{html.escape(data['ahead'])}</strong>. Mange-le !</p>")
    elif kind == "binary_split":
        columns = []
        for group in data["groups"]:
            people = "".join(f"<li>{html.escape(name)}</li>" for name in group["people"])
            columns.append("<td class='group' style='width:50%;padding:20px;vertical-align:top;"
                           f"background:#f4f1e9;border-radius:12px'><h3 style='margin:0 0 12px'>{html.escape(group['label'])}</h3>"
                           f"<ul style='margin:0;padding-left:18px'>{people}</ul></td>")
        detail = ("<table class='groups' role='presentation' style='width:100%;margin-top:24px;"
                  f"border-spacing:10px 0'><tr>{''.join(columns)}</tr></table>")
    elif kind == "slider":
        detail = ("<div class='number' style='margin:26px 0 8px;color:#d45a45;font-size:46px;"
                  f"font-weight:900;line-height:1.1'>{html.escape(str(data.get('answer')))}</div>")
    else:
        detail = ("<blockquote style='margin:24px 0 0;padding:18px 22px;border-left:4px solid #ffc83d;"
                  f"background:#f4f1e9;font-size:18px;line-height:1.65'>{html.escape(str(data.get('answer', '')))}</blockquote>")
    copy_parts = []
    for paragraph in re.split(r"(?:\r?\n){2,}|(?<=[.!?])\s+(?=[A-ZÀ-Ö])", final_content.strip()):
        if paragraph.strip():
            copy_parts.append(f"<p style='margin:0 0 16px'>{html.escape(paragraph.strip())}</p>")
    final_copy = "".join(copy_parts)
    author_photo = (f"<img class='author' src='{html.escape(photo_url, quote=True)}' alt='' "
                    "style='display:block;width:68px;height:68px;margin:0 0 8px auto;border-radius:50%;object-fit:cover'>"
                    if photo_url else "")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "body{margin:0;background:#ece9df;color:#17213a;font-family:Arial,sans-serif;line-height:1.65}"
        ".shell{width:100%;padding:36px 14px}.mail{width:100%;max-width:640px;margin:auto;background:#fff;border-radius:20px;overflow:hidden}"
        ".header{padding:22px 34px;background:#f3c952}.logo{display:block;width:150px;max-width:100%}.header-link{display:inline-block;padding:10px 13px;border-radius:8px;background:#17213a;color:#fff;font-size:12px;font-weight:bold;line-height:1.25;text-align:center;text-decoration:none}"
        ".section{padding:28px 40px;border-bottom:1px solid #e7e3d9}.intro-table{width:100%;border-collapse:collapse}.intro-author{width:150px;padding-left:24px;text-align:right;vertical-align:middle}.eyebrow{margin:0 0 12px;color:#d45a45;font-size:12px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase}"
        "h1{margin:0;font-size:32px;line-height:1.2}h2{margin:0;font-size:23px;line-height:1.4}h3{margin:0 0 12px;font-size:16px}"
        ".author{display:block;width:68px;height:68px;margin:0 0 8px auto;border-radius:50%;object-fit:cover}.author-copy{margin:0;font-size:14px;line-height:1.35}"
        ".rank,.number,.verdict{margin:26px 0 8px;color:#d45a45;font-size:46px;font-weight:900;line-height:1.1}"
        ".groups{width:100%;margin-top:24px;border-spacing:10px 0}.group{width:50%;padding:20px;vertical-align:top;background:#f4f1e9;border-radius:12px}.group ul{margin:0;padding-left:18px}"
        "blockquote{margin:24px 0 0;padding:18px 22px;border-left:4px solid #ffc83d;background:#f4f1e9;font-size:18px;line-height:1.65}"
        ".copy p{margin:0 0 16px}.copy p:last-child{margin-bottom:0}.bonus{padding:24px 40px;background:#f4f1e9;text-align:center}.actions{padding:22px 40px 28px}.actions-table{width:100%}"
        ".actions a{display:inline-block;padding:15px 18px;border-radius:9px;color:#fff;text-decoration:none;font-size:16px;font-weight:bold}.reply-link{background:#f05b42}.daily-link{background:#17213a}"
        "@media(max-width:520px){.section,.bonus,.actions{padding:22px}.intro-author{width:110px;padding-left:12px}.header{padding:22px}.groups{border-spacing:5px 0}.group{padding:14px}.actions a{padding:13px 11px;font-size:14px}}"
        "</style></head><body style='margin:0;background:#ece9df;color:#17213a;font-family:Arial,sans-serif;line-height:1.65'>"
        "<table class='shell' role='presentation' style='width:100%;padding:36px 14px;background:#ece9df'><tr><td>"
        "<main class='mail' style='display:block;width:100%;max-width:640px;margin:auto;background:#ffffff;border-radius:20px;overflow:hidden'>"
        f"<header class='header' style='padding:22px 34px;background:#f3c952'><table role='presentation' style='width:100%'><tr><td><img class='logo' src='{html.escape(logo_url, quote=True)}' alt='Cedz' style='display:block;width:150px;max-width:100%'></td><td align='right'><a class='header-link' href='{html.escape(account_url, quote=True)}' style='display:inline-block;padding:10px 13px;border-radius:8px;background:#17213a;color:#ffffff;font-size:12px;font-weight:bold;line-height:1.25;text-align:center;text-decoration:none'>Proposer une<br>nouvelle question</a></td></tr></table></header>"
        f"<section class='section' style='display:block;padding:28px 40px;border-bottom:1px solid #e7e3d9'><table class='intro-table' role='presentation' style='width:100%;border-collapse:collapse'><tr><td valign='middle'><p class='eyebrow' style='margin:0 0 12px;color:#d45a45;font-size:12px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase'>T24 · dossier confidentiel</p><h1 style='margin:0;font-size:32px;line-height:1.2'>{html.escape(row['intro_text'] or 'On a parlé de toi.')}</h1></td><td class='intro-author' align='right' valign='middle' style='width:150px;padding-left:24px;text-align:right'>{author_photo}<p class='author-copy' style='margin:0;font-size:14px;line-height:1.35'><strong>{html.escape(row['author_name'])}</strong><br>a parlé de toi.</p></td></tr></table></section>"
        f"<section class='section' style='display:block;padding:32px 40px;border-bottom:1px solid #e7e3d9'><p class='eyebrow' style='margin:0 0 12px;color:#d45a45;font-size:12px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase'>La question</p><h2 style='margin:0;font-size:23px;line-height:1.4'>{html.escape(data['question'])}</h2>{detail}</section>"
        f"<section class='section copy' style='display:block;padding:32px 40px;border-bottom:1px solid #e7e3d9'>{final_copy}</section>"
        f"<section class='bonus' style='display:block;padding:24px 40px;background:#f4f1e9;text-align:center'><p class='eyebrow' style='margin:0 0 12px;color:#d45a45;font-size:12px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase'>Aujourd’hui, la question bonus</p><h2 style='margin:0;font-size:23px;line-height:1.4'>{html.escape(daily_question)}</h2></section>"
        f"<section class='actions' style='display:block;padding:22px 40px 28px'><table class='actions-table' role='presentation' style='width:100%'><tr><td align='left'><a class='reply-link' href='{html.escape(detail_url, quote=True)}' style='display:inline-block;padding:15px 18px;border-radius:9px;background:#f05b42;color:#fff;text-decoration:none;font-size:16px;font-weight:bold'>Réponds-lui&nbsp;→</a></td><td align='right'><a class='daily-link' href='{html.escape(account_url, quote=True)}' style='display:inline-block;padding:15px 18px;border-radius:9px;background:#17213a;color:#fff;text-decoration:none;font-size:16px;font-weight:bold'>Réponds à la question&nbsp;→</a></td></tr></table></section>"
        "</main></td></tr></table></body></html>"
    )


class MailDeliveryError(RuntimeError):
    pass


def deliver_email(recipient: str, subject: str, html_body: str) -> str:
    """Deliver one transactional email; simulation is reserved for automated tests."""
    mode = str(current_app.config["MAIL_MODE"]).lower()
    if mode == "simulate":
        return "simulated"

    sender = str(current_app.config["MAIL_FROM"]).strip()
    sender_address = parseaddr(sender)[1]
    if (not EMAIL_RE.fullmatch(recipient) or not EMAIL_RE.fullmatch(sender_address)
            or any(char in subject + sender + recipient for char in "\r\n")):
        raise MailDeliveryError("Adresse Gmail ou destinataire invalide.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    text_body = re.sub(r"<style\b[^>]*>.*?</style>", "", html_body, flags=re.I | re.S)
    text_body = re.sub(r"<[^>]+>", " ", text_body)
    text_body = re.sub(r"\s+", " ", html.unescape(text_body)).strip()
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    if mode == "gmail_api":
        client_id = str(current_app.config["GMAIL_CLIENT_ID"]).strip()
        client_secret = str(current_app.config["GMAIL_CLIENT_SECRET"])
        refresh_token = str(current_app.config["GMAIL_REFRESH_TOKEN"])
        if not client_id or not client_secret or not refresh_token:
            raise MailDeliveryError("Configuration OAuth Gmail incomplète.")
        try:
            token_request = Request(
                "https://oauth2.googleapis.com/token",
                data=urlencode({
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urlopen(token_request, timeout=float(current_app.config["SMTP_TIMEOUT"])) as response:
                access_token = str(json.load(response).get("access_token", ""))
            if not access_token:
                raise ValueError("missing access token")
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
            send_request = Request(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                data=json.dumps({"raw": raw_message}).encode(),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(send_request, timeout=float(current_app.config["SMTP_TIMEOUT"])) as response:
                result = json.load(response)
            if not result.get("id"):
                raise ValueError("missing Gmail message id")
        except (HTTPError, URLError, OSError, ValueError, TypeError, AttributeError) as exc:
            http_status = getattr(exc, "code", None)
            current_app.logger.warning(
                "Gmail API delivery failed: %s%s",
                type(exc).__name__,
                f" (HTTP {http_status})" if http_status else "",
            )
            raise MailDeliveryError("L’API Gmail a refusé ou interrompu l’envoi.") from exc
        return "gmail_api"

    username = str(current_app.config["SMTP_USERNAME"]).strip()
    password = str(current_app.config["SMTP_PASSWORD"])
    if not EMAIL_RE.fullmatch(username) or not password:
        raise MailDeliveryError("Configuration SMTP Gmail incomplète.")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(
            str(current_app.config["SMTP_HOST"]),
            int(current_app.config["SMTP_PORT"]),
            timeout=float(current_app.config["SMTP_TIMEOUT"]),
        ) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailDeliveryError("Gmail a refusé ou interrompu l’envoi.") from exc
    return "gmail"


def choose_intro(revelation: sqlite3.Row) -> sqlite3.Row | None:
    rows = _db().execute(
        """SELECT ip.*, COALESCE(piu.use_count, 0) use_count
           FROM intro_phrases ip
           LEFT JOIN participant_intro_usage piu
             ON piu.intro_phrase_id = ip.id AND piu.participant_id = ?
           WHERE ip.is_active = 1 AND ip.tone = ?
           ORDER BY ip.id""",
        (revelation["recipient_participant_id"], revelation["tone"]),
    ).fetchall()
    if not rows:
        return None
    least_used = min(row["use_count"] for row in rows)
    return secrets.SystemRandom().choice([row for row in rows if row["use_count"] == least_used])


def revelation_payload(row: sqlite3.Row, *, admin: bool = False) -> dict[str, Any]:
    content = json.loads(row["content_json"])
    author = {"id": row["author_participant_id"], "displayName": row["author_name"],
              "profilePhotoUrl": row["author_photo"]}
    recipient = {"id": row["recipient_participant_id"], "displayName": row["recipient_name"],
                 "profilePhotoUrl": row["recipient_photo"]}
    result = {
        "id": row["id"], "status": row["status"], "questionType": row["question_type"],
        "type": row["question_type"], "typeLabel": row["question_type"].replace("_", " ").title(),
        "tone": row["tone"], "intro": row["intro_text"],
        "finalContent": row["final_content"] or format_revelation_content(row),
        "content": content, "contentData": content, "question": content["question"], "author": author, "recipient": recipient,
        "authorName": row["author_name"], "recipientName": row["recipient_name"],
        "subject": row["subject_snapshot"], "sentAt": row["sent_at"], "canReply": row["status"] == "sent",
    }
    if admin:
        result.update(
            recipientId=row["recipient_participant_id"], authorId=row["author_participant_id"],
            recipientEmail=row["recipient_email"], recipientPhotoUrl=row["recipient_photo"],
            authorPhotoUrl=row["author_photo"], rawAnswerId=row["imported_answer_id"],
            subjectSnapshot=row["subject_snapshot"], htmlSnapshot=row["html_snapshot"],
        )
    return result


def revelation_query(where: str = "") -> str:
    return """SELECT r.*, recipient.email recipient_email, recipient.display_name recipient_name,
              recipient.profile_photo_url recipient_photo, author.display_name author_name,
              author.profile_photo_url author_photo
              FROM revelations r
              JOIN participants recipient ON recipient.id = r.recipient_participant_id
              JOIN participants author ON author.id = r.author_participant_id""" + where


def deliver_revelation(row: sqlite3.Row) -> dict[str, Any]:
    """Send and persist one validated in-review revelation in the current transaction."""
    db = _db()
    content = row["final_content"] or format_revelation_content(row)
    subject = f"Cedz — une révélation pour {json.loads(row['content_json'])['recipient']}"
    html_snapshot = render_revelation_email(row, content)
    delivery_mode = deliver_email(row["recipient_email"], subject, html_snapshot)
    now = utcnow()
    db.execute(
        """UPDATE revelations SET status='sent', subject_snapshot=?, html_snapshot=?,
           content_snapshot=?, recipient_email_snapshot=?, sent_at=?, updated_at=? WHERE id=?""",
        (subject, html_snapshot, content, row["recipient_email"], now, now, row["id"]),
    )
    if row["intro_phrase_id"]:
        db.execute(
            """INSERT INTO participant_intro_usage(participant_id, intro_phrase_id, use_count, last_used_at)
               VALUES (?, ?, 1, ?) ON CONFLICT(participant_id, intro_phrase_id) DO UPDATE SET
               use_count=use_count+1, last_used_at=excluded.last_used_at""",
            (row["recipient_participant_id"], row["intro_phrase_id"], now),
        )
    db.commit()
    sent = db.execute(revelation_query(" WHERE r.id=?"), (row["id"],)).fetchone()
    payload = revelation_payload(sent, admin=True)
    payload["deliveryMode"] = delivery_mode
    return payload


def select_review_candidate(participant_id: int, exclude_id: int | None = None) -> sqlite3.Row | None:
    db = _db()
    current = db.execute(
        revelation_query(" WHERE r.recipient_participant_id=? AND r.status='in_review' ORDER BY r.id LIMIT 1"),
        (participant_id,),
    ).fetchone()
    if current and current["id"] != exclude_id:
        if not current["admin_edited"]:
            intro = choose_intro(current)
            db.execute(
                "UPDATE revelations SET intro_phrase_id=?, intro_text=?, updated_at=? WHERE id=?",
                (intro["id"] if intro else None, intro["text"] if intro else "On a parlé de toi.",
                 utcnow(), current["id"]),
            )
            db.commit()
            current = db.execute(revelation_query(" WHERE r.id=?"), (current["id"],)).fetchone()
        return current
    last = db.execute(
        "SELECT question_type FROM revelations WHERE recipient_participant_id=? AND status='sent' ORDER BY sent_at DESC LIMIT 1",
        (participant_id,),
    ).fetchone()
    rows = db.execute(
        revelation_query(" WHERE r.recipient_participant_id=? AND r.status IN ('candidate','skipped') ORDER BY CASE r.status WHEN 'candidate' THEN 0 ELSE 1 END, r.id"),
        (participant_id,),
    ).fetchall()
    rows = [row for row in rows if row["id"] != exclude_id]
    if not rows:
        return None
    different = [row for row in rows if not last or row["question_type"] != last["question_type"]]
    chosen = secrets.SystemRandom().choice(different or rows)
    intro = choose_intro(chosen)
    db.execute(
        """UPDATE revelations SET status='in_review',
           intro_phrase_id=CASE WHEN admin_edited=1 THEN intro_phrase_id ELSE ? END,
           intro_text=CASE WHEN admin_edited=1 THEN intro_text ELSE ? END,
           final_content=COALESCE(final_content, ?), updated_at=? WHERE id=?""",
        (intro["id"] if intro else None, intro["text"] if intro else "On a parlé de toi.",
         format_revelation_content(chosen), utcnow(), chosen["id"]),
    )
    db.commit()
    return db.execute(revelation_query(" WHERE r.id=?"), (chosen["id"],)).fetchone()


def register_account_api(app: Flask) -> None:
    @app.get("/api/account/dashboard")
    @participant_required
    def account_dashboard():
        participant = g.current_participant
        db = _db()
        answer_rows = db.execute(
            "SELECT * FROM imported_answers WHERE author_participant_id=? AND is_active=1 ORDER BY source_created_at, id",
            (participant["id"],),
        ).fetchall()
        catalog_categories = {values[0]: values[3] for values in QUESTION_CATALOG}
        own_answers = [{
            "id": row["id"], "category": catalog_categories.get(row["question_title"], "Autres"),
            "question": row["rendered_question"], "questionType": row["question_type"],
            "answer": answer_value(row), "createdAt": row["source_created_at"],
        } for row in answer_rows]
        received_rows = db.execute(
            revelation_query(" WHERE r.recipient_participant_id=? AND r.status='sent' ORDER BY r.sent_at DESC"),
            (participant["id"],),
        ).fetchall()
        received = []
        ranking_values: dict[str, list[int]] = {}
        for row in received_rows:
            item = revelation_payload(row)
            reply = db.execute("SELECT message, created_at FROM revelation_replies WHERE revelation_id=?", (row["id"],)).fetchone()
            item["reply"] = dict(reply) if reply else None
            received.append(item)
            content = item["content"]
            if row["question_type"] == "ranking":
                ranking_values.setdefault(content["discipline"], []).append(int(content["position"]))
        ranking_stats = [{"discipline": key, "averagePosition": round(sum(values) / len(values), 2), "revealedCount": len(values)}
                         for key, values in sorted(ranking_values.items())]
        reply_rows = db.execute(
            """SELECT rr.message, rr.created_at, r.id revelation_id, p.display_name from_participant,
                      r.content_json, r.content_snapshot, r.final_content
               FROM revelation_replies rr JOIN revelations r ON r.id=rr.revelation_id
               JOIN participants p ON p.id=rr.participant_id
               WHERE r.author_participant_id=? AND r.status='sent' ORDER BY rr.created_at DESC""",
            (participant["id"],),
        ).fetchall()
        replies_received = []
        for row in reply_rows:
            content = json.loads(row["content_json"])
            replies_received.append({
                "message": row["message"],
                "created_at": row["created_at"],
                "revelation_id": row["revelation_id"],
                "from_participant": row["from_participant"],
                "original_question": content.get("question", ""),
                "original_message": row["content_snapshot"] or row["final_content"] or "",
            })
        answer_session = db.execute(
            "SELECT id, status FROM answer_sessions WHERE participant_id=? ORDER BY created_at LIMIT 1",
            (participant["id"],),
        ).fetchone()
        questionnaire_payload = None
        if answer_session:
            question_rows = session_question_rows(answer_session["id"], participant["id"])
            answered_count = len(session_answer_values(answer_session["id"], question_rows))
            questionnaire_payload = {
                "sessionId": answer_session["id"],
                "status": answer_session["status"],
                "completed": answer_session["status"] == "completed",
                "answeredCount": answered_count,
                "remainingCount": max(0, len(question_rows) - answered_count),
                "totalCount": len(question_rows),
                "url": (url_for("questionnaire", session_id=answer_session["id"])
                        if answer_session["status"] != "completed" else None),
            }
        daily = current_daily_question(participant["id"]) if answer_session and answer_session["status"] == "completed" else None
        return jsonify({
            "csrfToken": csrf_token(), "participant": participant_payload(participant),
            "questionnaire": questionnaire_payload,
            "answers": own_answers, "revelations": received, "rankingStats": ranking_stats, "rankings": ranking_stats,
            "repliesReceived": replies_received,
            "dailyQuestion": daily_question_payload(daily) if daily else None,
            "dailyQuestionEnabled": bool(answer_session and answer_session["status"] == "completed"),
        })

    @app.post("/api/account/question-suggestions")
    @participant_required
    def create_question_suggestion():
        data = json_body()
        body, question_type = str(data.get("body", "")).strip(), str(data.get("type", "free_text"))
        required = {"free_text": ("{person}",), "slider": ("{person}",), "compare_two": ("{person1}", "{person2}"), "compare_three": ("{person1}", "{person2}", "{person3}"), "choose_one": ()}
        if not body or len(body) > 300 or question_type not in DAILY_QUESTION_TYPES:
            abort_json(400, "Suggestion invalide.")
        if any(marker not in body for marker in required[question_type]):
            abort_json(400, "Utilise les emplacements indiqués pour ce type de question.")
        now = utcnow()
        cursor = _db().execute(
            "INSERT INTO question_suggestions(author_participant_id,body,question_type,created_at,updated_at) VALUES (?,?,?,?,?)",
            (g.current_participant["id"], body, question_type, now, now),
        )
        _db().commit()
        return jsonify({"id": cursor.lastrowid, "submitted": True}), 201

    @app.post("/api/account/daily-question/<int:daily_id>/answer")
    @participant_required
    def answer_daily_question(daily_id: int):
        db = _db()
        row = db.execute(
            """SELECT d.*,q.title,q.type,q.category,q.scale_min,q.scale_max,q.allow_self_target
               FROM daily_questions d JOIN questions q ON q.id=d.question_id
               WHERE d.id=? AND d.participant_id=? AND d.status='active'""",
            (daily_id, g.current_participant["id"]),
        ).fetchone()
        if not row:
            abort_json(404, "Question du jour introuvable.")
        targets = [row[key] for key in ("target_participant_id", "target_participant_2_id", "target_participant_3_id") if row[key] is not None]
        text, number, structured = validate_answer(row, json_body().get("answer"), targets)
        now = utcnow()
        cursor = db.execute(
            """INSERT INTO imported_answers(source_key,author_participant_id,target_participant_id,question_id,question_title,
               rendered_question,question_type,answer_text,answer_number,answer_json,is_active,imported_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,?)""",
            (f"daily:{daily_id}", g.current_participant["id"], targets[0] if targets else None, row["question_id"],
             row["title"], row["rendered_body"], row["type"], text, number,
             json.dumps(structured, ensure_ascii=False) if structured is not None else None, 1, now, now),
        )
        available_after = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
        db.execute("UPDATE daily_questions SET status='answered',imported_answer_id=?,answered_at=?,available_after=?,updated_at=? WHERE id=?",
                   (cursor.lastrowid, now, available_after, now, daily_id))
        generate_revelation_candidates(commit=False)
        db.commit()
        return jsonify({"saved": True, "nextAvailableAt": available_after})

    @app.get("/api/account/revelations/<int:revelation_id>")
    @participant_required
    def account_revelation_detail(revelation_id: int):
        row = _db().execute(
            revelation_query(" WHERE r.id=? AND r.recipient_participant_id=? AND r.status='sent'"),
            (revelation_id, g.current_participant["id"]),
        ).fetchone()
        if not row:
            abort_json(404, "Révélation envoyée introuvable.")
        payload = revelation_payload(row)
        reply = _db().execute("SELECT message,created_at FROM revelation_replies WHERE revelation_id=?",
                              (revelation_id,)).fetchone()
        payload["reply"] = dict(reply) if reply else None
        return jsonify(payload)

    @app.patch("/api/account/password")
    @participant_required
    def account_password():
        data = json_body()
        current, new = str(data.get("currentPassword", "")), str(data.get("newPassword", ""))
        participant = g.current_participant
        if not participant["password_hash"] or not check_password_hash(participant["password_hash"], current):
            abort_json(403, "Mot de passe actuel incorrect.")
        if len(new) < 8 or len(new) > 128:
            abort_json(400, "Le nouveau mot de passe doit contenir entre 8 et 128 caractères.")
        _db().execute("UPDATE participants SET password_hash=?, updated_at=? WHERE id=?",
                      (generate_password_hash(new), utcnow(), participant["id"]))
        _db().commit()
        return jsonify({"updated": True})

    @app.post("/api/account/revelations/<int:revelation_id>/reply")
    @participant_required
    def reply_to_revelation(revelation_id: int):
        participant = g.current_participant
        revelation = _db().execute(
            "SELECT * FROM revelations WHERE id=? AND recipient_participant_id=? AND status='sent'",
            (revelation_id, participant["id"]),
        ).fetchone()
        if not revelation:
            abort_json(404, "Révélation envoyée introuvable.")
        message = str(json_body().get("message", "")).strip()
        if not message or len(message) > 2000:
            abort_json(400, "La réponse doit contenir entre 1 et 2000 caractères.")
        try:
            _db().execute("INSERT INTO revelation_replies(revelation_id, participant_id, message, created_at) VALUES (?, ?, ?, ?)",
                          (revelation_id, participant["id"], message, utcnow()))
            _db().commit()
        except sqlite3.IntegrityError:
            abort_json(409, "Tu as déjà répondu à cette révélation.")
        return jsonify({"created": True, "reply": {"message": message, "createdAt": utcnow()}}), 201


def register_admin_api(app: Flask) -> None:
    @app.get("/api/admin/question-suggestions")
    @admin_required
    def admin_question_suggestions():
        rows = _db().execute(
            """SELECT s.*,p.display_name author_name FROM question_suggestions s
               JOIN participants p ON p.id=s.author_participant_id ORDER BY s.created_at DESC"""
        ).fetchall()
        return jsonify({"suggestions": [dict(id=row["id"], authorName=row["author_name"], body=row["body"],
                      type=row["question_type"], status=row["status"], adminNote=row["admin_note"]) for row in rows]})

    @app.patch("/api/admin/question-suggestions/<int:suggestion_id>")
    @admin_required
    def admin_update_question_suggestion(suggestion_id: int):
        db = _db(); row = db.execute("SELECT * FROM question_suggestions WHERE id=?", (suggestion_id,)).fetchone()
        if not row: abort_json(404, "Suggestion introuvable.")
        data, status = json_body(), str(json_body().get("status", row["status"]))
        if status not in {"approved", "rejected"}: abort_json(400, "Statut invalide.")
        question_id = row["approved_question_id"]
        if status == "approved" and not question_id:
            question_type = str(data.get("type", row["question_type"]))
            body = str(data.get("body", row["body"])).strip()
            modes = {"free_text":"one_person","slider":"one_person","compare_two":"two_people","compare_three":"three_people","choose_one":"all_people"}
            if question_type not in DAILY_QUESTION_TYPES or not body or len(body)>300: abort_json(400, "Question invalide.")
            cursor = db.execute(
                """INSERT INTO questions(title,body,type,category,target_mode,is_active,display_order,created_at,updated_at)
                   VALUES (?,?,?,?,?,1,999,?,?)""",
                (body[:150], body, question_type, "Questions du jour", modes[question_type], utcnow(), utcnow()),
            ); question_id = cursor.lastrowid
        db.execute("UPDATE question_suggestions SET status=?,admin_note=?,approved_question_id=?,updated_at=? WHERE id=?",
                   (status, str(data.get("adminNote", "")).strip() or None, question_id, utcnow(), suggestion_id))
        db.commit()
        return jsonify({"updated": True, "questionId": question_id})

    @app.get("/api/admin/daily-questions")
    @admin_required
    def admin_daily_questions():
        people = _db().execute("SELECT id,display_name FROM participants WHERE is_active=1 ORDER BY display_name").fetchall()
        items=[]
        for person in people:
            row=current_daily_question(person["id"])
            items.append({"participantId":person["id"],"participantName":person["display_name"],
                          "question":daily_question_payload(row) if row else None})
        return jsonify({"dailyQuestions":items})

    @app.post("/api/admin/daily-questions/<int:participant_id>/regenerate")
    @admin_required
    def admin_regenerate_daily_question(participant_id: int):
        if not _db().execute("SELECT 1 FROM participants WHERE id=? AND is_active=1", (participant_id,)).fetchone():
            abort_json(404, "Participant introuvable.")
        data=json_body()
        try: question_id=int(data["questionId"]) if data.get("questionId") else None
        except (TypeError,ValueError): abort_json(400, "Question invalide.")
        row=current_daily_question(participant_id,force=True,question_id=question_id)
        if not row: abort_json(409, "Aucune question compatible.")
        return jsonify({"question":daily_question_payload(row)})

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
        email = str(data.get("email", "")).strip().lower()
        if not name or len(name) > 100:
            abort_json(400, "Nom participant invalide.")
        if email and not EMAIL_RE.fullmatch(email):
            abort_json(400, "Adresse email invalide.")
        cursor = _db().execute(
            """INSERT INTO participants(display_name, slug, email, avatar_url, profile_photo_url, secret_code, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, unique_slug(name), email or None,
             validate_asset_url(data.get("choicePhotoUrl", data.get("avatarUrl"))), validate_asset_url(data.get("profilePhotoUrl")),
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
        email = str(data.get("email", row["email"] or "")).strip().lower()
        if not name or len(name) > 100:
            abort_json(400, "Nom participant invalide.")
        if email and not EMAIL_RE.fullmatch(email):
            abort_json(400, "Adresse email invalide.")
        _db().execute(
            """UPDATE participants SET display_name=?, slug=?, email=?, avatar_url=?, profile_photo_url=?, secret_code=?, is_active=?, updated_at=? WHERE id=?""",
            (name, unique_slug(name, participant_id), email or None, validate_asset_url(data.get("choicePhotoUrl", data.get("avatarUrl", row["avatar_url"]))),
             validate_asset_url(data.get("profilePhotoUrl", row["profile_photo_url"])),
             data.get("secretCode", row["secret_code"]), int(bool(data.get("isActive", row["is_active"]))), utcnow(), participant_id),
        )
        _db().commit()
        return jsonify(participant_payload(_db().execute("SELECT * FROM participants WHERE id=?", (participant_id,)).fetchone(), private=True))

    @app.patch("/api/admin/participants/<int:participant_id>/password")
    @admin_required
    def admin_participant_password(participant_id: int):
        if not _db().execute("SELECT 1 FROM participants WHERE id=?", (participant_id,)).fetchone():
            abort_json(404, "Participant introuvable.")
        password = str(json_body().get("password", ""))
        if len(password) < 8 or len(password) > 128:
            abort_json(400, "Le mot de passe doit contenir entre 8 et 128 caractères.")
        _db().execute("UPDATE participants SET password_hash=?, updated_at=? WHERE id=?",
                      (generate_password_hash(password), utcnow(), participant_id))
        _db().commit()
        return jsonify({"updated": True})

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
        filters = {key: request.args[key] for key in ("authorId", "targetId", "questionId") if request.args.get(key)}
        return jsonify({"answers": combined_admin_answers(filters)})

    @app.get("/api/admin/stats")
    @admin_required
    def admin_stats():
        answers = combined_admin_answers({})
        progress = []
        for participant in _db().execute("SELECT id,display_name FROM participants WHERE is_active=1 ORDER BY display_name"):
            session_row = _db().execute(
                "SELECT id,status FROM answer_sessions WHERE participant_id=? ORDER BY created_at LIMIT 1",
                (participant["id"],),
            ).fetchone()
            count = sum(item["authorParticipantId"] == participant["id"] for item in answers)
            progress.append({
                "participantId": participant["id"], "participant": participant["display_name"],
                "answered": count, "total": QUESTIONNAIRE_TARGET_SIZE,
                "percent": min(100, round(count / QUESTIONNAIRE_TARGET_SIZE * 100)),
                "status": session_row["status"] if session_row else None,
            })
        return jsonify({
            "completed": sum(item["status"] == "completed" for item in progress),
            "answerCount": len(answers), "progress": progress,
        })

    @app.post("/api/admin/import-answers")
    @admin_required
    def admin_import_answers():
        try:
            if request.files.get("file"):
                uploaded = request.files["file"]
                items = json.loads(uploaded.read().decode("utf-8"))
                source_name = uploaded.filename or "upload.json"
            else:
                payload = request.get_json(silent=True)
                items = payload.get("answers") if isinstance(payload, dict) else payload
                source_name = "api.json"
            return jsonify(import_answers(items, source_name))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            abort_json(400, str(error))

    @app.get("/api/admin/raw-answers")
    @admin_required
    def admin_raw_answers():
        rows = _db().execute(
            """SELECT ia.*, p.display_name author_name, tp.display_name target_name
               FROM imported_answers ia JOIN participants p ON p.id=ia.author_participant_id
               LEFT JOIN participants tp ON tp.id=ia.target_participant_id ORDER BY ia.id DESC"""
        ).fetchall()
        return jsonify({"answers": [{
            "id": row["id"], "externalId": row["external_answer_id"], "author": row["author_name"],
            "authorParticipantId": row["author_participant_id"], "target": row["target_name"],
            "targetParticipantId": row["target_participant_id"], "question": row["rendered_question"],
            "questionTitle": row["question_title"], "questionType": row["question_type"],
            "answer": answer_value(row), "isActive": bool(row["is_active"]), "createdAt": row["source_created_at"],
        } for row in rows]})

    @app.patch("/api/admin/raw-answers/<int:answer_id>")
    @admin_required
    def admin_update_raw_answer(answer_id: int):
        active = bool(json_body().get("isActive", True))
        cursor = _db().execute("UPDATE imported_answers SET is_active=?, updated_at=? WHERE id=?",
                               (int(active), utcnow(), answer_id))
        if not cursor.rowcount:
            abort_json(404, "Réponse importée introuvable.")
        if not active:
            _db().execute("UPDATE revelations SET status='rejected', updated_at=? WHERE imported_answer_id=? AND status!='sent'",
                          (utcnow(), answer_id))
        _db().commit()
        if active:
            generate_revelation_candidates()
        return jsonify({"updated": True, "isActive": active})

    @app.get("/api/admin/revelations/review")
    @admin_required
    def admin_revelations_review():
        cards = []
        participants = _db().execute("SELECT id FROM participants WHERE is_active=1 ORDER BY display_name").fetchall()
        for participant in participants:
            row = select_review_candidate(participant["id"])
            if row:
                cards.append(revelation_payload(row, admin=True))
        return jsonify({"revelations": cards, "expectedCount": len(participants)})

    @app.get("/api/admin/revelations/sent")
    @admin_required
    def admin_revelations_sent():
        rows = _db().execute(revelation_query(" WHERE r.status='sent' ORDER BY r.sent_at DESC")).fetchall()
        return jsonify({"revelations": [revelation_payload(row, admin=True) for row in rows]})

    @app.get("/api/admin/revelation-replies")
    @admin_required
    def admin_revelation_replies():
        rows = _db().execute(
            """SELECT rr.id,rr.revelation_id,rr.message,rr.created_at,
                      recipient.id participant_id,recipient.display_name participant_name,
                      author.id author_id,author.display_name author_name,
                      r.content_json,r.content_snapshot,r.final_content
               FROM revelation_replies rr JOIN revelations r ON r.id=rr.revelation_id
               JOIN participants recipient ON recipient.id=rr.participant_id
               JOIN participants author ON author.id=r.author_participant_id
               ORDER BY rr.created_at DESC"""
        ).fetchall()
        replies = []
        for row in rows:
            content = json.loads(row["content_json"])
            replies.append({
                "id": row["id"], "revelationId": row["revelation_id"], "message": row["message"],
                "participantId": row["participant_id"], "participantName": row["participant_name"],
                "authorId": row["author_id"], "authorName": row["author_name"], "createdAt": row["created_at"],
                "originalQuestion": content.get("question", ""),
                "originalMessage": row["content_snapshot"] or row["final_content"] or "",
            })
        return jsonify({"replies": replies})

    @app.patch("/api/admin/revelations/<int:revelation_id>")
    @admin_required
    def admin_update_revelation(revelation_id: int):
        row = _db().execute("SELECT * FROM revelations WHERE id=?", (revelation_id,)).fetchone()
        if not row or row["status"] == "sent":
            abort_json(404, "Révélation modifiable introuvable.")
        data = json_body()
        intro = str(data.get("intro", row["intro_text"] or "")).strip()
        content = str(data.get("finalContent", row["final_content"] or format_revelation_content(row))).strip()
        if not intro or len(intro) > 300 or not content or len(content) > 5000:
            abort_json(400, "Introduction ou contenu invalide.")
        _db().execute("UPDATE revelations SET intro_text=?, final_content=?, admin_edited=1, updated_at=? WHERE id=?",
                      (intro, content, utcnow(), revelation_id))
        _db().commit()
        updated = _db().execute(revelation_query(" WHERE r.id=?"), (revelation_id,)).fetchone()
        return jsonify(revelation_payload(updated, admin=True))

    @app.post("/api/admin/revelations/<int:revelation_id>/refresh")
    @admin_required
    def admin_refresh_revelation(revelation_id: int):
        action = json_body().get("action")
        if action not in {"later", "reject"}:
            abort_json(400, "Choisis « later » ou « reject ».")
        row = _db().execute("SELECT * FROM revelations WHERE id=? AND status='in_review'", (revelation_id,)).fetchone()
        if not row:
            abort_json(404, "Proposition en review introuvable.")
        _db().execute("UPDATE revelations SET status=?, updated_at=? WHERE id=?",
                      ("skipped" if action == "later" else "rejected", utcnow(), revelation_id))
        _db().commit()
        replacement = select_review_candidate(row["recipient_participant_id"], exclude_id=revelation_id)
        return jsonify({"revelation": revelation_payload(replacement, admin=True) if replacement else None})

    @app.post("/api/admin/revelations/<int:revelation_id>/send")
    @admin_required
    def admin_send_revelation(revelation_id: int):
        db = _db()
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(revelation_query(" WHERE r.id=?"), (revelation_id,)).fetchone()
        if not row:
            abort_json(404, "Révélation introuvable.")
        if row["status"] == "sent":
            payload = revelation_payload(row, admin=True)
            payload["alreadySent"] = True
            return jsonify(payload)
        if row["status"] != "in_review":
            abort_json(409, "Cette révélation n'est pas en review.")
        if not row["recipient_email"] or not EMAIL_RE.fullmatch(row["recipient_email"]):
            abort_json(409, "Ajoute une adresse email valide au participant avant l'envoi.")
        try:
            payload = deliver_revelation(row)
        except MailDeliveryError:
            db.rollback()
            abort_json(502, "L’envoi Gmail a échoué. La révélation reste prête à être renvoyée.")
        return jsonify(payload)

    @app.post("/api/admin/revelations/send-active")
    @admin_required
    def admin_send_active_revelations():
        db = _db()
        rows = db.execute(
            revelation_query(
                " WHERE r.status='in_review' AND recipient.is_active=1 ORDER BY recipient.display_name, r.id"
            )
        ).fetchall()
        sent, failed, skipped = [], [], []
        for initial_row in rows:
            if not initial_row["recipient_email"] or not EMAIL_RE.fullmatch(initial_row["recipient_email"]):
                skipped.append({
                    "id": initial_row["id"],
                    "recipientName": initial_row["recipient_name"],
                    "recipientEmail": initial_row["recipient_email"],
                })
                continue
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(revelation_query(" WHERE r.id=? AND r.status='in_review'"),
                             (initial_row["id"],)).fetchone()
            if not row:
                db.rollback()
                continue
            try:
                sent.append(deliver_revelation(row))
            except MailDeliveryError:
                db.rollback()
                failed.append({
                    "id": row["id"],
                    "recipientName": row["recipient_name"],
                    "recipientEmail": row["recipient_email"],
                })
        return jsonify({
            "sent": sent,
            "sentCount": len(sent),
            "failed": failed,
            "failedCount": len(failed),
            "skipped": skipped,
            "skippedCount": len(skipped),
        })

    @app.get("/api/admin/intro-phrases")
    @admin_required
    def admin_intro_phrases():
        rows = _db().execute("SELECT * FROM intro_phrases ORDER BY id").fetchall()
        return jsonify({"phrases": [{"id": row["id"], "text": row["text"],
                                     "tone": "positive" if row["tone"] == "positif" else row["tone"],
                                     "isActive": bool(row["is_active"])} for row in rows]})

    @app.post("/api/admin/intro-phrases")
    @admin_required
    def admin_create_intro_phrase():
        data, now = json_body(), utcnow()
        text, tone = str(data.get("text", "")).strip(), data.get("tone")
        tone = "positif" if tone == "positive" else tone
        if not text or len(text) > 300 or tone not in INTRO_TONES:
            abort_json(400, "Phrase ou ton invalide.")
        cursor = _db().execute("INSERT INTO intro_phrases(text,tone,created_at,updated_at) VALUES (?,?,?,?)",
                               (text, tone, now, now))
        _db().commit()
        return jsonify({"id": cursor.lastrowid, "text": text,
                        "tone": "positive" if tone == "positif" else tone, "isActive": True}), 201

    @app.patch("/api/admin/intro-phrases/<int:phrase_id>")
    @admin_required
    def admin_update_intro_phrase(phrase_id: int):
        row = _db().execute("SELECT * FROM intro_phrases WHERE id=?", (phrase_id,)).fetchone()
        if not row:
            abort_json(404, "Phrase introuvable.")
        data = json_body()
        text, tone = str(data.get("text", row["text"])).strip(), data.get("tone", row["tone"])
        tone = "positif" if tone == "positive" else tone
        active = bool(data.get("isActive", row["is_active"]))
        if not text or len(text) > 300 or tone not in INTRO_TONES:
            abort_json(400, "Phrase ou ton invalide.")
        _db().execute("UPDATE intro_phrases SET text=?,tone=?,is_active=?,updated_at=? WHERE id=?",
                      (text, tone, int(active), utcnow(), phrase_id))
        _db().commit()
        return jsonify({"id": phrase_id, "text": text,
                        "tone": "positive" if tone == "positif" else tone, "isActive": active})

    @app.delete("/api/admin/intro-phrases/<int:phrase_id>")
    @admin_required
    def admin_delete_intro_phrase(phrase_id: int):
        cursor = _db().execute("UPDATE intro_phrases SET is_active=0,updated_at=? WHERE id=?", (utcnow(), phrase_id))
        _db().commit()
        if not cursor.rowcount:
            abort_json(404, "Phrase introuvable.")
        return jsonify({"deactivated": True})

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


def combined_admin_answers(filters: dict[str, Any]) -> list[dict[str, Any]]:
    legacy_columns = {"authorId": "a.author_participant_id", "targetId": "a.target_participant_id",
                      "questionId": "qi.question_id"}
    imported_columns = {"authorId": "ia.author_participant_id", "targetId": "ia.target_participant_id",
                        "questionId": "ia.question_id"}
    legacy_clauses, imported_clauses, params = [], ["ia.is_active=1"], []
    for key, value in filters.items():
        legacy_clauses.append(f"{legacy_columns[key]}=?")
        imported_clauses.append(f"{imported_columns[key]}=?")
        params.append(value)
    legacy_where = " WHERE " + " AND ".join(legacy_clauses) if legacy_clauses else ""
    legacy = [answer_payload(row) for row in _db().execute(answer_export_query(legacy_where), params).fetchall()]
    imported_clauses.append(
        "NOT EXISTS (SELECT 1 FROM answers a WHERE a.id=ia.external_answer_id AND a.session_id=ia.source_session_id)"
    )
    imported_query = """SELECT ia.*,p.display_name author_name,tp.display_name target_name,
                        s.status session_status
                 FROM imported_answers ia JOIN participants p ON p.id=ia.author_participant_id
                 LEFT JOIN participants tp ON tp.id=ia.target_participant_id
                 LEFT JOIN answer_sessions s ON s.id=ia.source_session_id
                 WHERE """ + " AND ".join(imported_clauses) + " ORDER BY ia.source_created_at DESC,ia.id DESC"
    imported_rows = _db().execute(imported_query, params).fetchall()
    imported = [{
        "id": row["external_answer_id"] if row["external_answer_id"] is not None else f"imported-{row['id']}",
        "importedAnswerId": row["id"], "author": row["author_name"],
        "authorParticipantId": row["author_participant_id"], "sessionId": row["source_session_id"],
        "target": row["target_name"], "targetParticipantId": row["target_participant_id"],
        "questionId": row["question_id"], "questionInstanceId": row["question_instance_id"],
        "question": row["question_title"], "renderedQuestion": row["rendered_question"],
        "renderedBody": row["rendered_question"], "sessionCompleted": row["session_status"] == "completed",
        "answer": answer_value(row), "createdAt": row["source_created_at"],
    } for row in imported_rows]
    return sorted(legacy + imported, key=lambda item: str(item.get("createdAt") or ""), reverse=True)


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("T24_DEBUG") == "1")
