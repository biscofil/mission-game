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
    description = db.Column(db.String(255), nullable=False)
    session_missions = db.relationship(
        "SessionMission", backref="mission", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Mission {self.id}: {self.description}>"


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    m_uuid = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    started_at = db.Column(db.DateTime, nullable=True)
    session_missions = db.relationship(
        "SessionMission", backref="session", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Session {self.id}, UUID: {self.m_uuid}, created_at: {self.created_at}, started_at: {self.started_at}>"


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
def index():
    response = make_response(render_template("index.html"))
    response.set_cookie("browser_session_id", get_or_generate_browser_session_id())
    return response


@app.route("/new-session", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        names = request.form.getlist("names[]")

        # Clean names: remove empty and duplicate names
        names = [name.strip() for name in names if name.strip()]
        names = list(dict.fromkeys(names))
        if len(names) < 3:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "At least three players are required to start a session.",
                    }
                ),
                400,
            )

        missions = Mission.query.order_by(db.func.random()).limit(len(names)).all()
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
            m_uuid=uuid.uuid4().hex, created_at=db.func.now(), started_at=None
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

        return redirect(f"/session?session_uuid={session.m_uuid}")

    else:
        return render_template("new_session.html")


@app.route("/session/ready", methods=["POST"])
def ready():
    session_uuid = request.form.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid).first()
    if not session:
        return "Session not found", 404

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

    return redirect(f"/session?session_uuid={session_uuid}")


@app.route("/session/not_ready", methods=["POST"])
def not_ready():
    session_uuid = request.form.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid).first()
    if not session:
        return "Session not found", 404

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

    return redirect(f"/session?session_uuid={session_uuid}")


@app.route("/session", methods=["GET"])
def session():
    session_uuid = request.args.get("session_uuid")
    session = Session.query.filter_by(m_uuid=session_uuid).first()
    if not session:
        return "Session not found", 404

    browser_session_id = get_or_generate_browser_session_id()

    session_data = {
        "uuid": session.m_uuid,
        "current_browser_logged": False,
        "players": [],
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

    return render_template(
        "session.html",
        session=session_data,
        current_browser_session_id=browser_session_id,
    )


@app.route("/session/ready", methods=["POST"])
def im_ready():

    session_uuid = request.form.get("session_uuid")
    player_id = request.form.get("player_id")
    session = Session.query.filter_by(m_uuid=session_uuid).first()
    if not session:
        return jsonify({"status": "error", "message": "Session not found"}), 404

    browser_session_id = get_or_generate_browser_session_id()

    any = SessionMission.query.filter_by(
        session_id=session.id, browser_session_id=browser_session_id
    ).first()
    if any:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "This browser session is already associated with a player in this session.",
                }
            ),
            400,
        )

    # Update the session mission with the browser session ID
    sm = SessionMission.query.filter_by(
        session_id=session.id, browser_session_id=None, id=player_id
    ).first()
    if sm:
        sm.browser_session_id = browser_session_id
        db.session.commit()

    return jsonify({"status": "success"}), 200


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
                            description=mission_data.get("description", "")
                        )
                        db.session.add(mission)
                    db.session.commit()

    app.run(debug=True, host="0.0.0.0", port=5000)
