from typing import Optional
from flask import Flask, render_template, request, jsonify, redirect, make_response
from flask_sqlalchemy import SQLAlchemy
import json
from pathlib import Path
from random import shuffle
import uuid
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mission-game.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.secret_key = os.getenv("SECRET_KEY", "default-dev-key")

db = SQLAlchemy(app)


class Mission(db.Model):
    __tablename__ = "missions"

    id = db.Column(db.Integer, primary_key=True)
    description_en = db.Column(db.String(255), nullable=False)
    description_it = db.Column(db.String(255), nullable=False)
    description_fr = db.Column(db.String(255), nullable=False)
    approved_on = db.Column(db.DateTime, nullable=True)
    session_missions = db.relationship(
        "SessionMission", backref="mission", lazy=True, cascade="all, delete-orphan"
    )

    def get_description(self, lang: str = "en") -> str:
        """Get mission description in the specified language (en, it, fr)."""
        lang = lang.lower()
        if lang == "it":
            return self.description_it
        elif lang == "fr":
            return self.description_fr
        else:
            return self.description_en

    def __repr__(self):
        return f"<Mission {self.id}: {self.description_en}>"


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    m_uuid = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    language = db.Column(db.String(5), default="en", nullable=False)
    session_missions = db.relationship(
        "SessionMission", backref="session", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Session {self.id}, UUID: {self.m_uuid}, created_at: {self.created_at}, started_at: {self.started_at}, language: {self.language}>"


class SessionMission(db.Model):
    __tablename__ = "session_missions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    player_name = db.Column(db.String(100), nullable=False, default="")
    target_player_name = db.Column(db.String(100), nullable=False, default="")
    browser_session_id = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"<SessionMission session_id={self.session_id}, mission_id={self.mission_id}, player_name={self.player_name}, target_player_name={self.target_player_name}, browser_session_id={self.browser_session_id}>"


def get_browser_session_id() -> Optional[str]:
    # Get the browser session ID from cookies, create if not present
    return request.cookies.get("browser_session_id")


def get_or_generate_browser_session_id() -> str:
    # Get the browser session ID from cookies, create if not present
    browser_session_id = get_browser_session_id()
    if not browser_session_id:
        browser_session_id = uuid.uuid4().hex
    return browser_session_id


@app.route("/", methods=["GET"])
def home():
    response = make_response(render_template("index.html"))
    response.set_cookie("browser_session_id", get_or_generate_browser_session_id())
    return response


@app.route("/new-session", methods=["GET", "POST"])
def new_session():
    if request.method == "POST":
        names = request.form.getlist("names[]")

        language = request.form.get("language", "en").lower()
        if language not in ["en", "it", "fr"]:
            language = "en"

        # Clean names: remove empty and duplicate names
        names = [name.strip().capitalize() for name in names if name.strip()]
        names = list(dict.fromkeys(names))
        if len(names) < 3 or len(names) > 20:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "The number of players must be between 3 and 20.",
                    }
                ),
                400,
            )

        missions = (
            Mission.query.filter(Mission.approved_on != None)
            .order_by(db.func.random())
            .limit(len(names))
            .all()
        )

        if len(missions) < len(names):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Not enough missions in the database.",
                    }
                ),
                400,
            )

        session = Session(
            m_uuid=uuid.uuid4().hex,
            created_at=db.func.now(),
            started_at=None,
            language=language,
        )
        db.session.add(session)
        db.session.flush()

        # Shuffle names
        shuffle(names)
        # Each player is assigned to the next player in the shuffled list
        target_players = names[1:] + [names[0]]

        # shuffle the items to randomize assignment order and IDs
        items = list(zip(names, target_players, missions))
        shuffle(items)

        for player_name, target_player_name, mission in items:

            session_mission = SessionMission(
                session_id=session.id,
                mission_id=mission.id,
                player_name=player_name,
                target_player_name=target_player_name,
                browser_session_id=None,
            )
            db.session.add(session_mission)

        db.session.commit()

        response = make_response(redirect(f"/session?session_uuid={session.m_uuid}"))
        response.set_cookie("browser_session_id", get_or_generate_browser_session_id())
        return response

    else:
        return render_template("new_session.html")


@app.route("/session/ready", methods=["POST"])
def ready():
    session_uuid = request.form.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid).filter_by(started_at=None).first()
    if not session:
        return "Session not found or already started", 404

    player_id = request.form.get("player_id")

    browser_session_id = get_browser_session_id()
    if not browser_session_id:
        return "Browser session ID not found", 400

    sm = SessionMission.query.filter_by(
        session_id=session.id, browser_session_id=None, id=player_id
    ).first()
    if sm:
        sm.browser_session_id = browser_session_id
        db.session.commit()
    else:
        return "Player not found or already checked in", 404

    # No cookie set here
    return redirect(f"/session?session_uuid={session_uuid}")


@app.route("/session/not_ready", methods=["POST"])
def not_ready():
    session_uuid = request.form.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid, started_at=None).first()
    if not session:
        return "Session not found or already started", 404

    browser_session_id = get_browser_session_id()
    if not browser_session_id:
        return "Browser session ID not found", 400

    sm = SessionMission.query.filter_by(
        session_id=session.id, browser_session_id=browser_session_id
    ).first()
    if sm:
        sm.browser_session_id = None
        db.session.commit()
    else:
        return "Player not found or already checked in", 404

    # No cookie set here
    return redirect(f"/session?session_uuid={session_uuid}")


@app.route("/session/start", methods=["POST"])
def start_session():
    session_uuid = request.form.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid, started_at=None).first()
    if not session:
        return "Session not found or already started", 404
    
    # Check if all players are ready
    not_ready_players = SessionMission.query.filter_by(session_id=session.id, browser_session_id=None).all()
    if not_ready_players:
        return "Not all players are ready", 400

    # Update the session's started_at timestamp
    session.started_at = db.func.now()
    db.session.commit()

    # No cookie set here
    return redirect(f"/session?session_uuid={session_uuid}")


@app.route("/session", methods=["GET"])
def session():
    session_uuid = request.args.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid).first()
    if not session:
        return "Session not found", 404

    browser_session_id = get_or_generate_browser_session_id()

    session_data = {
        "session": session,
        "current_browser_logged": False,
        "players": [],
        "player_mission": None,
    }

    if session.started_at:
        sm = SessionMission.query.filter_by(
            session_id=session.id, browser_session_id=browser_session_id
        ).first()
        if sm:
            session_data["player_mission"] = {
                "mission_description": sm.mission.get_description(session.language),
                "target_player_name": sm.target_player_name,
            }

    ready = True
    for sm in session.session_missions:
        if sm.browser_session_id == browser_session_id:
            session_data["current_browser_logged"] = True
        if sm.browser_session_id is None:
            ready = False
        session_data["players"].append(
            {
                "player_name": sm.player_name,
                "player_id": sm.id,
                "ready": sm.browser_session_id is not None,
                "browser_session_id": sm.browser_session_id,
            }
        )
    session_data["all_ready"] = ready

    # Sort session data by player_name to hide assignment order
    session_data["players"].sort(key=lambda x: x["player_name"])

    response = make_response(
        render_template(
            "session.html",
            session=session_data,
            current_browser_session_id=browser_session_id,
        )
    )
    response.set_cookie("browser_session_id", browser_session_id)
    return response


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        if Mission.query.first() is None:
            seed_file = Path(__file__).parent / "db_seed.json"
            if seed_file.exists():
                with open(seed_file, "r") as f:
                    missions = json.load(f)
                    for mission_data in missions.get("missions", []):
                        mission = Mission(
                            description_en=mission_data.get("description_en", ""),
                            description_it=mission_data.get("description_it", ""),
                            description_fr=mission_data.get("description_fr", ""),
                            approved_on=db.func.now(),
                        )
                        db.session.add(mission)
                    db.session.commit()

    app.run(debug=True, host="0.0.0.0", port=5000)
