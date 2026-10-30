from fastapi.testclient import TestClient
import pytest

from app import main
from app.services import anthropic_ai


@pytest.fixture(autouse=True)
def use_rule_based_demo_by_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AI_PROVIDER", "rule_based_demo")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)


def test_registration_interview_feedback_and_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        first = client.post(
            "/api/v1/auth/register",
            json={"email": "one@example.com", "password": "safe-passphrase-123", "display_name": "One"},
        )
        assert first.status_code == 201
        token = first.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "behavioral", "difficulty": "beginner", "question_count": 1},
        )
        assert created.status_code == 201
        interview = created.json()
        question = interview["questions"][0]

        saved = client.put(
            f"/api/v1/interviews/{interview['id']}/answers/{question['id']}",
            headers=headers,
            json={"answer_text": "For example, in my class project I worked with a team and we improved the result."},
        )
        assert saved.status_code == 200

        result = client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=headers)
        assert result.status_code == 200
        assert result.json()["feedback_type"] == "rule_based_not_ai"
        assert 0 <= result.json()["overall_score"] <= 100

        other = client.post(
            "/api/v1/auth/register",
            json={"email": "two@example.com", "password": "safe-passphrase-456", "display_name": "Two"},
        )
        other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
        denied = client.get(f"/api/v1/interviews/{interview['id']}", headers=other_headers)
        assert denied.status_code == 404


def test_cannot_complete_without_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        user = client.post(
            "/api/v1/auth/register",
            json={"email": "three@example.com", "password": "safe-passphrase-789", "display_name": "Three"},
        ).json()
        headers = {"Authorization": f"Bearer {user['access_token']}"}
        created = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "technical", "difficulty": "intermediate", "question_count": 1},
        ).json()
        response = client.post(f"/api/v1/interviews/{created['id']}/complete", headers=headers)
        assert response.status_code == 409


def test_ten_question_category_session_keeps_unique_question_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        user = client.post(
            "/api/v1/auth/register",
            json={"email": "four@example.com", "password": "safe-passphrase-123", "display_name": "Four"},
        ).json()
        headers = {"Authorization": f"Bearer {user['access_token']}"}
        created = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "behavioral", "difficulty": "intermediate", "question_count": 10},
        )
        assert created.status_code == 201
        questions = created.json()["questions"]
        assert len(questions) == 10
        assert len({question["id"] for question in questions}) == 10


def test_health_readiness_question_filters_and_auth_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/api/v1/interviews").status_code == 401
        filtered = client.get("/api/v1/questions?category=technical&difficulty=beginner&limit=2")
        assert filtered.status_code == 200
        assert filtered.json()["total"] > 0
        assert len(filtered.json()["questions"]) <= 2
        assert all(question["category"] == "technical" for question in filtered.json()["questions"])
        assert all(question["difficulty"] == "beginner" for question in filtered.json()["questions"])


def test_profile_update_and_account_deletion_remove_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": "profile@example.com", "password": "safe-passphrase-123", "display_name": "Profile"},
        ).json()
        headers = {"Authorization": f"Bearer {registration['access_token']}"}
        updated = client.patch(
            "/api/v1/profile",
            headers=headers,
            json={"target_role": "Engineer", "experience_level": "student", "preferred_categories": ["technical"]},
        )
        assert updated.status_code == 200
        assert updated.json()["target_role"] == "Engineer"
        assert updated.json()["preferred_categories"] == ["technical"]

        interview = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "technical", "difficulty": "beginner", "question_count": 1},
        ).json()
        history = client.get("/api/v1/interviews", headers=headers)
        assert history.status_code == 200
        assert history.json()["total"] == 1
        assert history.json()["sessions"][0]["id"] == interview["id"]
        deleted = client.delete("/api/v1/profile", headers=headers)
        assert deleted.status_code == 204
        with main.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM interviews").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == 0
        assert client.get("/api/v1/profile", headers=headers).status_code == 401
        assert client.get(f"/api/v1/interviews/{interview['id']}", headers=headers).status_code == 401


def test_login_logout_and_duplicate_registration(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        credentials = {"email": "auth@example.com", "password": "safe-passphrase-123"}
        registration = client.post(
            "/api/v1/auth/register",
            json={**credentials, "display_name": "Auth"},
        )
        assert registration.status_code == 201
        duplicate = client.post(
            "/api/v1/auth/register",
            json={**credentials, "display_name": "Duplicate"},
        )
        assert duplicate.status_code == 409
        login = client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/v1/profile", headers=headers).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/profile", headers=headers).status_code == 401


def test_other_user_cannot_update_or_delete_interview(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        owner = client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "safe-passphrase-123", "display_name": "Owner"},
        ).json()
        intruder = client.post(
            "/api/v1/auth/register",
            json={"email": "intruder@example.com", "password": "safe-passphrase-456", "display_name": "Intruder"},
        ).json()
        owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
        intruder_headers = {"Authorization": f"Bearer {intruder['access_token']}"}
        interview = client.post(
            "/api/v1/interviews",
            headers=owner_headers,
            json={"category": "behavioral", "difficulty": "beginner", "question_count": 1},
        ).json()
        question_id = interview["questions"][0]["id"]
        update = client.put(
            f"/api/v1/interviews/{interview['id']}/answers/{question_id}",
            headers=intruder_headers,
            json={"answer_text": "Unauthorized answer"},
        )
        delete = client.delete(f"/api/v1/interviews/{interview['id']}", headers=intruder_headers)
        assert update.status_code == 404
        assert delete.status_code == 404


def test_anthropic_question_and_evaluation_schema(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-server-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setattr(
        anthropic_ai,
        "_request_json",
        lambda *args, **kwargs: {
            "questions": [
                {
                    "category": "technical",
                    "question_text": "How would you explain a database index to a teammate?",
                    "skills": ["databases", "communication"],
                }
            ]
        },
    )
    questions = anthropic_ai.generate_interview_questions("technical", "beginner", 1, None)
    assert questions[0]["category"] == "technical"

    monkeypatch.setattr(
        anthropic_ai,
        "_request_json",
        lambda *args, **kwargs: {
            "overall_score": 1,
            "questions": [
                {
                    "question_id": "q1",
                    "score": 1,
                    "dimensions": [
                        {
                            "name": name,
                            "score": 80,
                            "explanation": "Clear evidence in this answer.",
                        }
                        for name in ["Technical correctness", "Completeness", "Reasoning", "Practical application", "Trade-offs"]
                    ],
                    "strengths": ["Explains a useful example."],
                    "improvements": ["Clarify the trade-off."],
                    "feedback": "The explanation includes a relevant example.",
                }
            ],
            "strengths": ["Used a concrete example."],
            "improvements": ["Explain one limitation."],
            "suggested_practice": ["Practise explaining trade-offs."],
            "limitations": ["Technical facts may need independent verification."],
        },
    )
    evaluation = anthropic_ai.evaluate_session(
        "technical",
        "beginner",
        [{"question_id": "q1", "question_text": "Explain an index.", "category": "technical", "answer_text": "A clear example."}],
    )
    assert evaluation.questions[0].score == 80
    assert evaluation.overall_score == 80

    behavioral_dimensions = [
        {"name": name, "score": 70, "explanation": "Relevant evidence from the response."}
        for name in ["Relevance", "Structure", "Specific evidence", "Reflection", "Clarity"]
    ]
    technical_dimensions = [
        {"name": name, "score": 90, "explanation": "Relevant evidence from the response."}
        for name in ["Technical correctness", "Completeness", "Reasoning", "Practical application", "Trade-offs"]
    ]
    monkeypatch.setattr(
        anthropic_ai,
        "_request_json",
        lambda *args, **kwargs: {
            "overall_score": 1,
            "questions": [
                {
                    "question_id": question_id,
                    "score": 1,
                    "dimensions": dimensions,
                    "strengths": [],
                    "improvements": [],
                    "feedback": "The answer gives relevant detail.",
                }
                for question_id, dimensions in [("behavioral-q", behavioral_dimensions), ("technical-q", technical_dimensions)]
            ],
            "strengths": [],
            "improvements": [],
            "suggested_practice": [],
            "limitations": [],
        },
    )
    mixed_evaluation = anthropic_ai.evaluate_session(
        "mixed",
        "intermediate",
        [
            {"question_id": "behavioral-q", "question_text": "Tell me about a challenge.", "category": "behavioral", "answer_text": "I adapted."},
            {"question_id": "technical-q", "question_text": "Explain an index.", "category": "technical", "answer_text": "It speeds up a lookup."},
        ],
    )
    assert [item.score for item in mixed_evaluation.questions] == [70, 90]
    assert mixed_evaluation.overall_score == 80


def test_anthropic_request_uses_server_key_and_retries_rate_limits(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-server-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("AI_MAX_RETRIES", "1")
    requests = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.is_error = status_code >= 400
            self.payload = payload

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 30

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, headers, json):
            requests.append({"url": url, "headers": headers, "json": json})
            if len(requests) == 1:
                return FakeResponse(429, {})
            return FakeResponse(200, {"content": [{"type": "text", "text": '{"ok":true}'}]})

    monkeypatch.setattr(anthropic_ai.httpx, "Client", FakeClient)
    monkeypatch.setattr(anthropic_ai.time, "sleep", lambda delay: None)
    result = anthropic_ai._request_json("system", {"sample": "input"}, max_tokens=100)
    assert result == {"ok": True}
    assert len(requests) == 2
    assert requests[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert requests[0]["headers"]["x-api-key"] == "test-server-key"
    assert requests[0]["json"]["model"] == "test-model"


def test_anthropic_session_path_is_persisted_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-server-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setattr(
        main,
        "generate_interview_questions",
        lambda *args: [
            {
                "id": "generated-q1",
                "category": "technical",
                "difficulty": "intermediate",
                "question_text": "How would you describe an index to a teammate?",
                "skills": ["databases"],
            }
        ],
    )
    dimensions = [
        anthropic_ai.ScoreDimension(name=name, score=80, explanation="Clear relevant detail.")
        for name in ["Technical correctness", "Completeness", "Reasoning", "Practical application", "Trade-offs"]
    ]
    evaluations = []

    def fake_evaluate(*args):
        evaluations.append(True)
        return anthropic_ai.SessionEvaluation(
            overall_score=80,
            questions=[
                anthropic_ai.AnswerEvaluation(
                    question_id="generated-q1",
                    score=80,
                    dimensions=dimensions,
                    strengths=["Relevant example."],
                    improvements=["Explain one trade-off."],
                    feedback="The answer gives a relevant example.",
                )
            ],
            strengths=["Relevant example."],
            improvements=["Explain one trade-off."],
            suggested_practice=["Practise concise explanations."],
            limitations=["Check technical details independently."],
        )

    monkeypatch.setattr(main, "evaluate_session", fake_evaluate)
    with TestClient(main.app) as client:
        user = client.post(
            "/api/v1/auth/register",
            json={"email": "anthropic@example.com", "password": "safe-passphrase-123", "display_name": "AI Test"},
        ).json()
        headers = {"Authorization": f"Bearer {user['access_token']}"}
        interview = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "technical", "difficulty": "intermediate", "question_count": 1},
        ).json()
        assert interview["question_source"] == "anthropic_generated"
        client.put(
            f"/api/v1/interviews/{interview['id']}/answers/generated-q1",
            headers=headers,
            json={"answer_text": "I used a database index to speed up a query and measured the result."},
        )
        first_result = client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=headers)
        second_result = client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=headers)
        assert first_result.status_code == 200
        assert first_result.json()["feedback_type"] == "anthropic"
        assert first_result.json()["model_name"] == "test-model"
        assert first_result.json() == second_result.json()
        assert len(evaluations) == 1


def test_anthropic_failure_keeps_saved_answers_and_session_in_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-server-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setattr(
        main,
        "generate_interview_questions",
        lambda *args: [
            {
                "id": "generated-q1",
                "category": "behavioral",
                "difficulty": "beginner",
                "question_text": "Tell me about a time you learned a difficult new skill.",
                "skills": ["learning"],
            }
        ],
    )
    monkeypatch.setattr(
        main,
        "evaluate_session",
        lambda *args: (_ for _ in ()).throw(anthropic_ai.AIServiceError("Provider unavailable; retry later.")),
    )
    with TestClient(main.app) as client:
        user = client.post(
            "/api/v1/auth/register",
            json={"email": "provider-failure@example.com", "password": "safe-passphrase-123", "display_name": "Failure"},
        ).json()
        headers = {"Authorization": f"Bearer {user['access_token']}"}
        interview = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "behavioral", "difficulty": "beginner", "question_count": 1},
        ).json()
        answer = "For example, I practised a new skill and learned to break the challenge into steps."
        client.put(
            f"/api/v1/interviews/{interview['id']}/answers/generated-q1",
            headers=headers,
            json={"answer_text": answer},
        )
        failed = client.post(f"/api/v1/interviews/{interview['id']}/complete", headers=headers)
        detail = client.get(f"/api/v1/interviews/{interview['id']}", headers=headers).json()
        assert failed.status_code == 503
        assert detail["status"] == "in_progress"
        assert detail["answers"][0]["answer_text"] == answer


def test_dashboard_analytics_returns_real_completed_data(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_PATH", tmp_path / "analytics.db")
    main.initialize_database()
    with TestClient(main.app) as client:
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": "analytics@example.com", "password": "safe-passphrase-123", "display_name": "Analytics"},
        )
        assert registration.status_code == 201
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

        interview = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"category": "behavioral", "difficulty": "beginner", "question_count": 1},
        )
        assert interview.status_code == 201
        session = interview.json()
        question = session["questions"][0]
        saved = client.put(
            f"/api/v1/interviews/{session['id']}/answers/{question['id']}",
            headers=headers,
            json={"answer_text": "I used clear evidence, described my contribution, and reflected on the result with a specific example."},
        )
        assert saved.status_code == 200

        completed = client.post(f"/api/v1/interviews/{session['id']}/complete", headers=headers)
        assert completed.status_code == 200

        analytics = client.get("/api/v1/analytics", headers=headers)
        assert analytics.status_code == 200
        data = analytics.json()
        assert data["completed_sessions"] == 1
        assert data["questions_answered"] == 1
        assert 0 <= data["average_score"] <= 100
        assert isinstance(data["trend"], list)
        assert isinstance(data["skills"], list)
        assert isinstance(data["interviews"], list)
        assert isinstance(data["activity"], list)

        filtered = client.get("/api/v1/analytics?start_date=2099-01-01", headers=headers)
        assert filtered.status_code == 200
        assert filtered.json()["completed_sessions"] == 0
