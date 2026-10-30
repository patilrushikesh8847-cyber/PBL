"""Small, local-first API for the Interview Coach MVP.

This demo uses curated questions and transparent rule-based feedback.
It is not a production authentication or AI deployment template.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv

from app.services.anthropic_ai import (
    AIConfigurationError,
    AIServiceError,
    anthropic_is_selected,
    evaluate_session,
    generate_interview_questions,
    provider_config,
    validate_startup_config,
)

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATABASE_PATH = Path(os.getenv("INTERVIEW_COACH_DB", ROOT / "data" / "interview_coach.db"))
TOKEN_LIFETIME = timedelta(days=7)
PASSWORD_SALT_BYTES = 16
PASSWORD_N = 2**14
PASSWORD_R = 8
PASSWORD_P = 1

QUESTION_BANK: list[dict[str, Any]] = [
    {"id": "b1", "category": "behavioral", "difficulty": "beginner", "question_text": "Tell me about a time you worked with someone whose approach was different from yours. How did you work together?", "skills": ["teamwork", "communication"]},
    {"id": "b2", "category": "behavioral", "difficulty": "intermediate", "question_text": "Describe a challenge you faced while learning something new. What steps did you take, and what did you learn?", "skills": ["learning", "problem-solving"]},
    {"id": "b3", "category": "behavioral", "difficulty": "advanced", "question_text": "Tell me about a time a project did not go as planned. How did you respond and what would you change?", "skills": ["ownership", "reflection"]},
    {"id": "b4", "category": "behavioral", "difficulty": "intermediate", "question_text": "Give an example of how you prioritized competing deadlines. What trade-offs did you make?", "skills": ["prioritization", "decision-making"]},
    {"id": "b5", "category": "behavioral", "difficulty": "beginner", "question_text": "What is a project or accomplishment you are proud of, and what was your contribution?", "skills": ["ownership", "communication"]},
    {"id": "b6", "category": "behavioral", "difficulty": "intermediate", "question_text": "Describe a time you received feedback that changed how you approached your work.", "skills": ["growth", "self-awareness"]},
    {"id": "b7", "category": "behavioral", "difficulty": "beginner", "question_text": "Tell me about a time you had to explain a complex idea to someone new to the topic.", "skills": ["communication", "clarity"]},
    {"id": "b8", "category": "behavioral", "difficulty": "advanced", "question_text": "Describe a decision you made with incomplete information. How did you manage the risks?", "skills": ["decision-making", "judgment"]},
    {"id": "b9", "category": "behavioral", "difficulty": "intermediate", "question_text": "Tell me about a time you helped a group move forward when people disagreed.", "skills": ["collaboration", "conflict resolution"]},
    {"id": "b10", "category": "behavioral", "difficulty": "beginner", "question_text": "What is a skill you have worked to improve recently, and how did you practise it?", "skills": ["learning", "initiative"]},
    {"id": "t1", "category": "technical", "difficulty": "beginner", "question_text": "Explain the difference between an array and a linked list. When might you choose each?", "skills": ["data structures", "trade-offs"]},
    {"id": "t2", "category": "technical", "difficulty": "intermediate", "question_text": "What is a hash table, and how does it handle collisions?", "skills": ["data structures", "computer science"]},
    {"id": "t3", "category": "technical", "difficulty": "advanced", "question_text": "How would you investigate an API endpoint that has become noticeably slower under load?", "skills": ["debugging", "systems thinking"]},
    {"id": "t4", "category": "technical", "difficulty": "intermediate", "question_text": "Describe the trade-offs between synchronous and asynchronous operations in a web application.", "skills": ["web development", "trade-offs"]},
    {"id": "t5", "category": "technical", "difficulty": "beginner", "question_text": "What is the purpose of a database index, and what costs can it introduce?", "skills": ["databases", "trade-offs"]},
    {"id": "t6", "category": "technical", "difficulty": "beginner", "question_text": "What is the difference between a process and a thread?", "skills": ["operating systems", "computer science"]},
    {"id": "t7", "category": "technical", "difficulty": "intermediate", "question_text": "How would you design a paginated API endpoint for a large collection of records?", "skills": ["API design", "databases"]},
    {"id": "t8", "category": "technical", "difficulty": "advanced", "question_text": "How would you reason about caching data that changes frequently while keeping responses useful and fresh?", "skills": ["systems thinking", "trade-offs"]},
    {"id": "t9", "category": "technical", "difficulty": "intermediate", "question_text": "What is a database transaction, and why are atomicity and isolation useful?", "skills": ["databases", "computer science"]},
    {"id": "t10", "category": "technical", "difficulty": "beginner", "question_text": "What happens when a browser requests a page from a web server?", "skills": ["web development", "networking"]},
]
RUBRIC_VERSION = "rule-based-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                education_level TEXT,
                field_of_study TEXT,
                experience_level TEXT,
                target_role TEXT,
                preferred_categories TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS interviews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                target_role TEXT,
                status TEXT NOT NULL CHECK(status IN ('in_progress', 'completed')),
                question_ids TEXT NOT NULL,
                question_source TEXT NOT NULL DEFAULT 'curated',
                model_provider TEXT,
                model_name TEXT,
                summary_json TEXT,
                overall_score INTEGER,
                rubric_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_interviews_user_created
                ON interviews(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS answers (
                interview_id TEXT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                question_id TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                score INTEGER,
                feedback TEXT,
                evaluation_json TEXT,
                evaluated_at TEXT,
                PRIMARY KEY(interview_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS interview_questions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                question_text TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                UNIQUE(session_id, order_index)
            );
            """
        )
        for table, fields in {
            "interviews": (
                ("question_source", "TEXT NOT NULL DEFAULT 'curated'"),
                ("model_provider", "TEXT"),
                ("model_name", "TEXT"),
                ("summary_json", "TEXT"),
            ),
            "answers": (("evaluation_json", "TEXT"), ("evaluated_at", "TEXT")),
        }.items():
            existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            for name, definition in fields:
                if name not in existing:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        existing_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
        for name, definition in (
            ("education_level", "TEXT"),
            ("field_of_study", "TEXT"),
            ("experience_level", "TEXT"),
            ("target_role", "TEXT"),
            ("preferred_categories", "TEXT NOT NULL DEFAULT '[]'"),
            ("updated_at", "TEXT"),
        ):
            if name not in existing_columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")


@contextmanager
def http_error_on_sqlite_integrity():
    try:
        yield
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc


class Credentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address.")
        return value.lower()


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)


class InterviewSetup(BaseModel):
    category: str = Field(pattern="^(behavioral|technical|mixed)$")
    difficulty: str = Field(pattern="^(beginner|intermediate|advanced)$")
    question_count: int = Field(ge=1, le=10)
    target_role: str | None = Field(default=None, max_length=100)


class AnswerInput(BaseModel):
    answer_text: str = Field(min_length=1, max_length=5000)

    @field_validator("answer_text")
    @classmethod
    def answer_is_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Write an answer before submitting.")
        return value


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    education_level: str | None = Field(default=None, max_length=80)
    field_of_study: str | None = Field(default=None, max_length=100)
    experience_level: Literal["student", "entry_level", "early_career"] | None = None
    target_role: str | None = Field(default=None, max_length=100)
    preferred_categories: list[Literal["behavioral", "technical", "mixed"]] | None = Field(default=None, max_length=3)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        validate_startup_config()
    except AIConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc
    initialize_database()
    yield


app = FastAPI(
    title="Interview Coach API",
    version="0.1.0",
    description="Local MVP API; feedback is rule-based, not AI-generated.",
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "Fontend.html")


@app.get("/config.js", include_in_schema=False)
def frontend_config() -> FileResponse:
    return FileResponse(ROOT / "config.js", media_type="application/javascript")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        with connection() as db:
            db.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
    return {"status": "ready"}


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=PASSWORD_N, r=PASSWORD_R, p=PASSWORD_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, expected = stored.split("$", maxsplit=2)
        if algorithm != "scrypt":
            return False
        actual = hash_password(password, bytes.fromhex(salt_hex)).split("$", maxsplit=2)[2]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(db: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO auth_tokens(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hashlib.sha256(token.encode()).hexdigest(), user_id, (datetime.now(timezone.utc) + TOKEN_LIFETIME).isoformat()),
    )
    return token


def user_from_authorization(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue.")
    token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
    with connection() as db:
        db.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (utc_now(),))
        row = db.execute(
            """SELECT users.id, users.email, users.display_name, users.education_level,
                      users.field_of_study, users.experience_level, users.target_role,
                      users.preferred_categories
               FROM auth_tokens JOIN users ON users.id = auth_tokens.user_id
               WHERE auth_tokens.token_hash = ? AND auth_tokens.expires_at > ?""",
            (token_hash, utc_now()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Please sign in again.")
    return dict(row)


CurrentUser = Annotated[dict[str, Any], Depends(user_from_authorization)]


@app.post("/api/v1/auth/register", status_code=201)
def register(payload: Registration) -> dict[str, Any]:
    user_id = secrets.token_urlsafe(18)
    with http_error_on_sqlite_integrity():
        with connection() as db:
            db.execute(
                """INSERT INTO users(id, email, display_name, password_hash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, payload.email, payload.display_name, hash_password(payload.password), utc_now(), utc_now()),
            )
            token = issue_token(db, user_id)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user_id, "email": payload.email, "display_name": payload.display_name}}


@app.post("/api/v1/auth/login")
def login(payload: Credentials) -> dict[str, Any]:
    with connection() as db:
        row = db.execute("SELECT id, email, display_name, password_hash FROM users WHERE email = ?", (payload.email,)).fetchone()
        if row is None or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        token = issue_token(db, row["id"])
    return {"access_token": token, "token_type": "bearer", "user": {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}}


@app.post("/api/v1/auth/logout")
def logout(user: CurrentUser, authorization: Annotated[str, Header()]) -> dict[str, bool]:
    del user
    token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
    with connection() as db:
        db.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))
    return {"ok": True}


@app.get("/api/v1/profile")
def profile(user: CurrentUser) -> dict[str, Any]:
    result = dict(user)
    result["preferred_categories"] = json.loads(result["preferred_categories"])
    return result


@app.patch("/api/v1/profile")
def update_profile(payload: ProfileUpdate, user: CurrentUser) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one profile field to update.")
    with connection() as db:
        for field, value in updates.items():
            if field == "preferred_categories":
                value = json.dumps(value)
            db.execute(f"UPDATE users SET {field} = ?, updated_at = ? WHERE id = ?", (value, utc_now(), user["id"]))
    with connection() as db:
        row = db.execute(
            """SELECT id, email, display_name, education_level, field_of_study,
                      experience_level, target_role, preferred_categories
               FROM users WHERE id = ?""",
            (user["id"],),
        ).fetchone()
    result = dict(row)
    result["preferred_categories"] = json.loads(result["preferred_categories"])
    return result


@app.delete("/api/v1/profile", status_code=204, response_class=Response)
def delete_profile(user: CurrentUser) -> Response:
    with connection() as db:
        db.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    return Response(status_code=204)


@app.get("/api/v1/questions")
def list_questions(
    category: str | None = Query(default=None, pattern="^(behavioral|technical)$"),
    difficulty: str | None = Query(default=None, pattern="^(beginner|intermediate|advanced)$"),
    skill: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    questions = QUESTION_BANK
    if category:
        questions = [item for item in questions if item["category"] == category]
    if difficulty:
        questions = [item for item in questions if item["difficulty"] == difficulty]
    if skill:
        questions = [item for item in questions if any(skill.casefold() in tag.casefold() for tag in item["skills"])]
    if q:
        query = q.casefold()
        questions = [item for item in questions if query in item["question_text"].casefold()]
    total = len(questions)
    page = questions[offset : offset + limit]
    return {"questions": page, "total": total, "limit": limit, "offset": offset, "next_offset": offset + limit if offset + limit < total else None}


def get_owned_interview(db: sqlite3.Connection, interview_id: str, user_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return row


def get_session_questions(db: sqlite3.Connection, interview: sqlite3.Row) -> list[dict[str, Any]]:
    rows = db.execute(
        """SELECT id, question_text, category, difficulty, skills_json
           FROM interview_questions WHERE session_id = ? ORDER BY order_index""",
        (interview["id"],),
    ).fetchall()
    if rows:
        return [
            {
                "id": row["id"],
                "question_text": row["question_text"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "skills": json.loads(row["skills_json"]),
            }
            for row in rows
        ]
    ids = interview["question_ids"].split(",")
    question_by_id = {question["id"]: question for question in QUESTION_BANK}
    return [question_by_id[question_id] for question_id in ids if question_id in question_by_id]


@app.post("/api/v1/interviews", status_code=201)
def create_interview(payload: InterviewSetup, user: CurrentUser) -> dict[str, Any]:
    category_matches = [
        question for question in QUESTION_BANK
        if payload.category == "mixed" or question["category"] == payload.category
    ]
    difficulty_matches = [
        question for question in category_matches
        if question["difficulty"] == payload.difficulty
    ]
    selected_pool = difficulty_matches or category_matches
    if len(selected_pool) < payload.question_count:
        selected_pool = category_matches
    selected = random.sample(selected_pool, k=min(payload.question_count, len(selected_pool)))
    question_source = "curated"
    generation_notice = None
    model_provider = None
    model_name = None
    if anthropic_is_selected():
        model_provider = "anthropic"
        try:
            model_name = provider_config().model
            selected = generate_interview_questions(
                payload.category,
                payload.difficulty,
                payload.question_count,
                payload.target_role,
            )
            question_source = "anthropic_generated"
        except (AIConfigurationError, AIServiceError) as exc:
            question_source = "curated_fallback"
            generation_notice = str(exc)
    interview_id = secrets.token_urlsafe(18)
    ids = ",".join(question["id"] for question in selected)
    with connection() as db:
        db.execute(
            """INSERT INTO interviews(id, user_id, category, difficulty, target_role, status,
                                      question_ids, question_source, model_provider, model_name,
                                      rubric_version, created_at)
               VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?, ?, ?, ?, ?)""",
            (
                interview_id,
                user["id"],
                payload.category,
                payload.difficulty,
                payload.target_role,
                ids,
                question_source,
                model_provider,
                model_name,
                RUBRIC_VERSION,
                utc_now(),
            ),
        )
        for index, question in enumerate(selected):
            db.execute(
                """INSERT INTO interview_questions(id, session_id, question_text, category, difficulty, skills_json, order_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    question["id"],
                    interview_id,
                    question["question_text"],
                    question["category"],
                    question["difficulty"],
                    json.dumps(question["skills"]),
                    index,
                ),
            )
    return {
        "id": interview_id,
        "category": payload.category,
        "difficulty": payload.difficulty,
        "target_role": payload.target_role,
        "status": "in_progress",
        "question_count": len(selected),
        "question_source": question_source,
        "generation_notice": generation_notice,
        "questions": selected,
    }


@app.get("/api/v1/interviews")
def list_interviews(
    user: CurrentUser,
    category: str | None = Query(default=None, pattern="^(behavioral|technical|mixed)$"),
    difficulty: str | None = Query(default=None, pattern="^(beginner|intermediate|advanced)$"),
    session_status: str | None = Query(default=None, alias="status", pattern="^(in_progress|completed)$"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    conditions = ["user_id = ?"]
    parameters: list[Any] = [user["id"]]
    for column, value in (("category", category), ("difficulty", difficulty), ("status", session_status)):
        if value is not None:
            conditions.append(f"{column} = ?")
            parameters.append(value)
    with connection() as db:
        total = db.execute(f"SELECT COUNT(*) FROM interviews WHERE {' AND '.join(conditions)}", parameters).fetchone()[0]
        rows = db.execute(
            """SELECT id, category, difficulty, target_role, status, overall_score, rubric_version,
                      created_at, completed_at, question_ids
               FROM interviews WHERE """ + " AND ".join(conditions) + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*parameters, limit, (page - 1) * limit],
        ).fetchall()
    sessions = [dict(row) | {"question_count": len(row["question_ids"].split(","))} for row in rows]
    for session in sessions:
        session.pop("question_ids")
    return {"sessions": sessions, "total": total, "page": page, "limit": limit}


@app.put("/api/v1/interviews/{interview_id}/answers/{question_id}")
def save_answer(interview_id: str, question_id: str, payload: AnswerInput, user: CurrentUser) -> dict[str, bool]:
    with connection() as db:
        interview = get_owned_interview(db, interview_id, user["id"])
        if interview["status"] != "in_progress":
            raise HTTPException(status_code=409, detail="This interview is already complete.")
        if question_id not in interview["question_ids"].split(","):
            raise HTTPException(status_code=404, detail="Question not found in this interview.")
        db.execute(
            """INSERT INTO answers(interview_id, question_id, answer_text)
               VALUES (?, ?, ?) ON CONFLICT(interview_id, question_id)
               DO UPDATE SET answer_text = excluded.answer_text""",
            (interview_id, question_id, payload.answer_text),
        )
    return {"saved": True}


def evaluate_answer(answer: str, question: dict[str, Any]) -> tuple[int, str, list[str], list[str]]:
    words = answer.split()
    strengths: list[str] = []
    improvements: list[str] = []
    score = 25 if len(words) >= 8 else 10
    if len(words) >= 35:
        score += 20
        strengths.append("You provided enough detail to review.")
    else:
        improvements.append("Add more detail so your reasoning and contribution are clear.")
    lower = answer.lower()
    if any(term in lower for term in ("for example", "for instance", "when i", "in my", "such as")):
        score += 20
        strengths.append("You included a concrete example or experience.")
    else:
        improvements.append("Include one specific example to make the answer more memorable.")
    if any(term in lower for term in ("result", "outcome", "learn", "improved", "because", "therefore")):
        score += 20
        strengths.append("You described an outcome, reason, or learning.")
    else:
        improvements.append("Explain the result or what you learned.")
    if len(words) >= 8:
        score += 15
        strengths.append("You addressed the prompt with a complete response.")
    score = min(score, 100)
    feedback = "This is a lightweight writing checklist, not an evaluation of factual accuracy. " + (
        "Your answer contains some useful detail; consider how clearly it connects to the question."
        if len(words) >= 8
        else "Expand your answer with context, your actions, and the outcome."
    )
    return score, feedback, strengths, improvements


@app.post("/api/v1/interviews/{interview_id}/complete")
def complete_interview(interview_id: str, user: CurrentUser) -> dict[str, Any]:
    with connection() as db:
        interview = get_owned_interview(db, interview_id, user["id"])
        if interview["status"] == "completed" and interview["summary_json"]:
            return json.loads(interview["summary_json"])
        questions = get_session_questions(db, interview)
        answers = db.execute("SELECT * FROM answers WHERE interview_id = ?", (interview_id,)).fetchall()
        answers_by_id = {row["question_id"]: row for row in answers}
        missing = [question["id"] for question in questions if question["id"] not in answers_by_id or not answers_by_id[question["id"]]["answer_text"].strip()]
        if missing:
            raise HTTPException(status_code=409, detail="Answer every question before completing the interview.")
        evaluation_inputs = [
            {
                "question_id": question["id"],
                "question_text": question["question_text"],
                "category": question["category"],
                "skills": question["skills"],
                "answer_text": answers_by_id[question["id"]]["answer_text"],
            }
            for question in questions
        ]

    if anthropic_is_selected():
        try:
            provider_result = evaluate_session(interview["category"], interview["difficulty"], evaluation_inputs)
            model_name = provider_config().model
        except AIConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AIServiceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        question_by_id = {question["id"]: question for question in questions}
        evaluations = []
        answer_evaluations: dict[str, dict[str, Any]] = {}
        for item in provider_result.questions:
            question = question_by_id[item.question_id]
            item_data = item.model_dump()
            answer_evaluations[item.question_id] = item_data
            evaluations.append(
                {
                    "question_text": question["question_text"],
                    "score": item.score,
                    "feedback": item.feedback,
                    "dimensions": [dimension.model_dump() for dimension in item.dimensions],
                }
            )
        overall_score = provider_result.overall_score
        strengths = provider_result.strengths
        improvements = provider_result.improvements
        rubric_version = "anthropic-practice-v1"
        feedback_type = "anthropic"
        suggested_practice = provider_result.suggested_practice
        limitations = provider_result.limitations
        model_provider = "anthropic"
    else:
        evaluations = []
        strengths = []
        improvements = []
        answer_evaluations = {}
        for question in questions:
            score, feedback, answer_strengths, answer_improvements = evaluate_answer(
                answers_by_id[question["id"]]["answer_text"], question
            )
            evaluation = {
                "question_id": question["id"],
                "score": score,
                "dimensions": [],
                "strengths": answer_strengths,
                "improvements": answer_improvements,
                "feedback": feedback,
            }
            answer_evaluations[question["id"]] = evaluation
            strengths.extend(answer_strengths)
            improvements.extend(answer_improvements)
            evaluations.append({"question_text": question["question_text"], "score": score, "feedback": feedback})
        overall_score = round(sum(item["score"] for item in evaluations) / len(evaluations))
        rubric_version = RUBRIC_VERSION
        feedback_type = "rule_based_not_ai"
        suggested_practice = ["Continue practising with a new example and a clear outcome."]
        limitations = ["Rule-based demo feedback does not verify factual accuracy."]
        model_provider = "rule_based_demo"
        model_name = None

    result = {
        "id": interview_id,
        "category": interview["category"],
        "difficulty": interview["difficulty"],
        "question_count": len(questions),
        "overall_score": overall_score,
        "rubric_version": rubric_version,
        "question_source": interview["question_source"],
        "model_provider": model_provider,
        "model_name": model_name if anthropic_is_selected() else interview["model_name"],
        "strengths": list(dict.fromkeys(strengths))[:6] or ["You completed a practice session."],
        "improvements": list(dict.fromkeys(improvements))[:6] or ["Continue practising with new examples and clear outcomes."],
        "suggested_practice": suggested_practice,
        "limitations": limitations,
        "questions": evaluations,
        "feedback_type": feedback_type,
    }
    with connection() as db:
        current = get_owned_interview(db, interview_id, user["id"])
        if current["status"] == "completed" and current["summary_json"]:
            return json.loads(current["summary_json"])
        for question_id, evaluation in answer_evaluations.items():
            db.execute(
                """UPDATE answers SET score = ?, feedback = ?, evaluation_json = ?, evaluated_at = ?
                   WHERE interview_id = ? AND question_id = ?""",
                (
                    evaluation["score"],
                    evaluation["feedback"],
                    json.dumps(evaluation),
                    utc_now(),
                    interview_id,
                    question_id,
                ),
            )
        db.execute(
            """UPDATE interviews
               SET status = 'completed', overall_score = ?, rubric_version = ?,
                   model_provider = ?, model_name = ?, summary_json = ?, completed_at = ?
               WHERE id = ?""",
            (
                overall_score,
                rubric_version,
                model_provider,
                result["model_name"],
                json.dumps(result),
                utc_now(),
                interview_id,
            ),
        )
    return result


@app.get("/api/v1/interviews/{interview_id}")
def interview_detail(interview_id: str, user: CurrentUser) -> dict[str, Any]:
    with connection() as db:
        interview = get_owned_interview(db, interview_id, user["id"])
        answers = db.execute("SELECT question_id, answer_text, score, feedback FROM answers WHERE interview_id = ?", (interview_id,)).fetchall()
        questions = get_session_questions(db, interview)
    return {"id": interview_id, "status": interview["status"], "category": interview["category"], "difficulty": interview["difficulty"], "question_source": interview["question_source"], "questions": questions, "answers": [dict(row) for row in answers]}


@app.delete("/api/v1/interviews/{interview_id}", status_code=204, response_class=Response)
def delete_interview(interview_id: str, user: CurrentUser) -> Response:
    with connection() as db:
        get_owned_interview(db, interview_id, user["id"])
        db.execute("DELETE FROM interviews WHERE id = ? AND user_id = ?", (interview_id, user["id"]))
    return Response(status_code=204)
