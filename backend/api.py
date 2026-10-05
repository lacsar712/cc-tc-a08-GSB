import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext

from claimer import start as start_claimer
from models import (
    Base,
    ConversionRecord,
    ConvergenceLog,
    EquivalentParam,
    SessionLocal,
    conversion_dict,
    engine,
    equivalent_dict,
    row_dict,
)
from rules import (
    LIMIT_MM,
    convert_chord,
    judge,
    round_reading,
    validate_chord,
    validate_equivalent,
    validate_reading,
)

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

EQUIVALENT_ID = 1  # 当量参数单行 id
DEFAULT_FACTOR = 0.5
DEFAULT_BASELINE_MM = 0.0

app = Flask(__name__)


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        if db.get(EquivalentParam, EQUIVALENT_ID) is None:
            db.add(
                EquivalentParam(
                    id=EQUIVALENT_ID,
                    factor=DEFAULT_FACTOR,
                    baseline_mm=DEFAULT_BASELINE_MM,
                    updated_by="system",
                    updated_at=now,
                )
            )
            db.commit()
        if db.query(ConvergenceLog).count() > 0:
            return
        for chainage, delta, expect in (("K12+180", 1.2, "合格"), ("K18+040", 5.6, "超限")):
            verdict, reason = judge(delta)
            assert verdict == expect
            row = ConvergenceLog(
                chainage=chainage,
                delta_mm=delta,
                status="done",
                verdict=verdict,
                reason=reason,
                created_by="surveyor",
                created_at=now,
                processed_at=now,
            )
            db.add(row)
            db.flush()  # 先取 id，流水与进队记录同一事务落库
            db.add(
                ConversionRecord(
                    log_id=row.id,
                    mode="direct",
                    chord_mm=None,
                    factor=None,
                    baseline_mm=None,
                    delta_mm=delta,
                    created_by="surveyor",
                    created_at=now,
                )
            )
        db.commit()
    finally:
        db.close()


seed()
start_claimer()


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    sub = payload.get("sub")
    if sub not in USERS:
        return None
    return {"username": sub, "role": payload.get("role")}


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def require_writer(detail):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"detail": "未登录"}), 401
            if user["role"] != "writer":
                return jsonify({"detail": detail}), 403
            g.user = user
            return fn(*args, **kwargs)

        return wrapper

    return deco


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "tunnel-convergence-desk"})


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = USERS.get(username)
    if not user or not pwd.verify(password, user["password_hash"]):
        return jsonify({"detail": "用户名或密码错误"}), 401
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode(
        {"sub": username, "role": user["role"], "exp": exp}, SECRET, algorithm="HS256"
    )
    return jsonify({"access_token": token, "username": username, "role": user["role"]})


@app.get("/api/logs")
@require_login
def list_logs():
    db = SessionLocal()
    try:
        rows = db.query(ConvergenceLog).order_by(ConvergenceLog.id.desc()).all()
        return jsonify([row_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/logs")
@require_writer("仅测量员可提交收敛读数")
def create_log():
    body = request.get_json(silent=True) or {}
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400
    has_chord = body.get("chord_mm") is not None
    has_delta = body.get("delta_mm") is not None
    if has_chord and has_delta:
        return jsonify({"detail": "弦长与直填毫米只能二选一"}), 400
    if not has_chord and not has_delta:
        return jsonify({"detail": "请填写弦长或收敛毫米值"}), 400

    db = SessionLocal()
    try:
        if has_chord:
            try:
                chord_mm = validate_chord(body.get("chord_mm"))
            except ValueError as exc:
                return jsonify({"detail": str(exc)}), 400
            equiv = db.get(EquivalentParam, EQUIVALENT_ID)
            if equiv is None:
                return jsonify({"detail": "当量参数未初始化"}), 500
            # 后台按当前当量换算成收敛毫米，快照当量进流水
            delta_mm = convert_chord(chord_mm, equiv.factor, equiv.baseline_mm)
            mode, factor, baseline_mm = "chord", equiv.factor, equiv.baseline_mm
        else:
            try:
                delta_mm = round_reading(validate_reading(body.get("delta_mm")))
            except ValueError as exc:
                return jsonify({"detail": str(exc)}), 400
            chord_mm, mode, factor, baseline_mm = None, "direct", None, None

        now = datetime.now(timezone.utc)
        row = ConvergenceLog(
            chainage=chainage,
            delta_mm=delta_mm,
            status="pending",
            created_by=g.user["username"],
            created_at=now,
        )
        db.add(row)
        db.flush()  # 先取 id，换算流水与进队记录同一事务落库
        conv = ConversionRecord(
            log_id=row.id,
            mode=mode,
            chord_mm=chord_mm,
            factor=factor,
            baseline_mm=baseline_mm,
            delta_mm=delta_mm,
            created_by=g.user["username"],
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.refresh(row)
        db.refresh(conv)
        return jsonify({**row_dict(row), "conversion": conversion_dict(conv, chainage)}), 201
    finally:
        db.close()


@app.get("/api/equivalent")
@require_login
def get_equivalent():
    db = SessionLocal()
    try:
        row = db.get(EquivalentParam, EQUIVALENT_ID)
        if row is None:
            return jsonify({"detail": "当量参数未初始化"}), 500
        return jsonify({**equivalent_dict(row), "limit_mm": LIMIT_MM})
    finally:
        db.close()


@app.put("/api/equivalent")
@require_writer("仅测量员可维护当量参数，巡检员只读")
def update_equivalent():
    body = request.get_json(silent=True) or {}
    try:
        factor, baseline_mm = validate_equivalent(body.get("factor"), body.get("baseline_mm"))
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400
    db = SessionLocal()
    try:
        row = db.get(EquivalentParam, EQUIVALENT_ID)
        if row is None:
            return jsonify({"detail": "当量参数未初始化"}), 500
        row.factor = factor
        row.baseline_mm = baseline_mm
        row.updated_by = g.user["username"]
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(row)
        return jsonify({**equivalent_dict(row), "limit_mm": LIMIT_MM})
    finally:
        db.close()


@app.get("/api/conversions")
@require_login
def list_conversions():
    db = SessionLocal()
    try:
        rows = (
            db.query(ConversionRecord, ConvergenceLog.chainage)
            .join(ConvergenceLog, ConversionRecord.log_id == ConvergenceLog.id)
            .order_by(ConversionRecord.id.desc())
            .all()
        )
        return jsonify([conversion_dict(conv, chainage) for conv, chainage in rows])
    finally:
        db.close()
