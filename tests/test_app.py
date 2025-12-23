import uuid
import json
import pytest
from werkzeug.datastructures import MultiDict

from app import app, db, Mission, Session, SessionMission


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        # seed some missions with languages for the tests
        for i in range(5):
            db.session.add(
                Mission(
                    description_en=f"English Mission {i}",
                    description_it=f"Missione Italiana {i}",
                    description_fr=f"Mission Française {i}",
                    approved_on=db.func.now(),
                )
            )
        db.session.commit()

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_index_sets_cookie(client):
    resp = client.get("/")
    assert resp.status_code == 200
    # Flask sets the cookie in the Set-Cookie header
    assert "browser_session_id" in resp.headers.get("Set-Cookie", "")


def test_new_session_too_few_players(client):
    data = MultiDict([("names[]", "Alice"), ("names[]", "Bob")])
    resp = client.post("/new-session", data=data)
    assert resp.status_code == 400
    j = resp.get_json()
    assert j is not None and j.get("status") == "error"


def test_new_session_with_english(client):
    data = MultiDict([
        ("names[]", "Alice"),
        ("names[]", "Bob"),
        ("names[]", "Charlie"),
        ("language", "en"),
    ])
    resp = client.post("/new-session", data=data, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/session?session_uuid=" in resp.headers.get("Location", resp.location or "")

    # Verify session was created with English language
    with app.app_context():
        session = Session.query.first()
        assert session is not None
        assert session.language == "en"


def test_new_session_with_italian(client):
    data = MultiDict([
        ("names[]", "Alice"),
        ("names[]", "Bob"),
        ("names[]", "Charlie"),
        ("language", "it"),
    ])
    resp = client.post("/new-session", data=data, follow_redirects=False)
    assert resp.status_code in (302, 303)

    with app.app_context():
        session = Session.query.first()
        assert session is not None
        assert session.language == "it"


def test_new_session_with_french(client):
    data = MultiDict([
        ("names[]", "Alice"),
        ("names[]", "Bob"),
        ("names[]", "Charlie"),
        ("language", "fr"),
    ])
    resp = client.post("/new-session", data=data, follow_redirects=False)
    assert resp.status_code in (302, 303)

    with app.app_context():
        session = Session.query.first()
        assert session is not None
        assert session.language == "fr"


def test_mission_get_description_english(client):
    with app.app_context():
        mission = Mission.query.first()
        assert mission is not None
        assert mission.get_description("en") == "English Mission 0"
        assert mission.get_description("EN") == "English Mission 0"  # case insensitive


def test_mission_get_description_italian(client):
    with app.app_context():
        mission = Mission.query.first()
        assert mission is not None
        assert mission.get_description("it") == "Missione Italiana 0"


def test_mission_get_description_french(client):
    with app.app_context():
        mission = Mission.query.first()
        assert mission is not None
        assert mission.get_description("fr") == "Mission Française 0"


def test_mission_get_description_default_english(client):
    with app.app_context():
        mission = Mission.query.first()
        assert mission is not None
        # Default language should be English
        assert mission.get_description() == "English Mission 0"
        assert mission.get_description("invalid_lang") == "English Mission 0"


def test_session_not_found(client):
    resp = client.get("/session?session_uuid=nonexistent")
    assert resp.status_code == 404


def test_session_shows_translated_mission(client):
    """Test that sessions store the language and can retrieve missions."""
    with app.app_context():
        # Create a French-language session with a mission
        s = Session(m_uuid=uuid.uuid4().hex, language="fr")
        db.session.add(s)
        db.session.flush()
        
        m = Mission.query.first()
        assert m is not None, "No mission found in database"
        
        sm = SessionMission(
            session_id=s.id,
            mission_id=m.id,
            player_name="P1",
            target_player_name="P2",
            browser_session_id="test-browser-session",
        )
        db.session.add(sm)
        db.session.commit()

        session_uuid = s.m_uuid
        session_id = s.id

    # Verify the session language is stored correctly
    with app.app_context():
        session = Session.query.filter_by(m_uuid=session_uuid).first()
        assert session is not None
        assert session.language == "fr"
        
        # Verify mission can be retrieved in French
        sm = SessionMission.query.filter_by(session_id=session_id).first()
        assert sm is not None
        mission_text = sm.mission.get_description("fr")
        assert mission_text is not None
        assert len(mission_text) > 0
        assert "Française" in mission_text  # Check for French accent support
