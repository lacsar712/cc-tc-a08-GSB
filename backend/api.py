import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext

import equivalent
from claimer import start as start_claimer
from models import (
    ConversionLedger,
    ConvergenceLog,
    EquivalentSetting,
    SessionLocal,
    engine,
    init_schema,
    ledger_dict,
    row_dict,
    setting_dict,
)

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

app = Flask(__name__)


def seed():
    init_schema()
    db = SessionLocal()
    try:
        if db.query(EquivalentSetting).filter(EquivalentSetting.id == 1).first() is None:
            db.add(
                EquivalentSetting(
                    id=1,
                    coefficient=equivalent.DEFAULT_COEFF,
                    updated_by="system",
                    updated_at=datetime.now(timezone.utc),
                )
            )
        if db.query(ConvergenceLog).count() == 0:
            now = datetime.now(timezone.utc)
            for chainage, delta, expect in (("K12+180", 1.2, "合格"), ("K18+040", 5.6, "超限")):
                from rules import judge

                verdict, reason = judge(delta)
                assert verdict == expect
                db.add(
                    ConvergenceLog(
                        chainage=chainage,
                        delta_mm=delta,
                        input_mode="delta",
                        status="done",
                        verdict=verdict,
                        reason=reason,
                        created_by="surveyor",
                        created_at=now,
                        processed_at=now,
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


def require_writer(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        if user["role"] != "writer":
            return jsonify({"detail": "仅测量员可写，巡检员为只读"}), 403
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def get_coefficient(db) -> float:
    setting = db.query(EquivalentSetting).filter(EquivalentSetting.id == 1).first()
    return float(setting.coefficient) if setting else equivalent.DEFAULT_COEFF


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


@app.get("/api/equivalent")
@require_login
def get_equivalent():
    db = SessionLocal()
    try:
        setting = db.query(EquivalentSetting).filter(EquivalentSetting.id == 1).first()
        if setting is None:
            return jsonify(
                {
                    "coefficient": equivalent.DEFAULT_COEFF,
                    "updated_by": "system",
                    "updated_at": None,
                }
            )
        return jsonify(setting_dict(setting))
    finally:
        db.close()


@app.put("/api/equivalent")
@require_writer
def update_equivalent():
    body = request.get_json(silent=True) or {}
    # 当量填错或越界：先校验，把原因原样退回，不动库里的旧值。
    try:
        raw = equivalent.parse_number(body.get("coefficient"), "当量系数")
        coefficient = equivalent.validate_coefficient(raw)
    except ValueError as exc:
        return jsonify({"detail": f"当量系数被退回：{exc}"}), 400
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        setting = db.query(EquivalentSetting).filter(EquivalentSetting.id == 1).first()
        if setting is None:
            setting = EquivalentSetting(id=1)
            db.add(setting)
        setting.coefficient = coefficient
        setting.updated_by = g.user["username"]
        setting.updated_at = now
        db.commit()
        db.refresh(setting)
        return jsonify(setting_dict(setting))
    finally:
        db.close()


@app.post("/api/equivalent/preview")
@require_login
def preview_equivalent():
    """换算专页试算：弦长路按当前当量换算，直填毫米路原样归一，两路必须同一个数。"""
    body = request.get_json(silent=True) or {}
    has_chord = body.get("chord_mm") is not None
    has_delta = body.get("delta_mm") is not None
    if has_chord == has_delta:
        return jsonify({"detail": "弦长与毫米只能且必须选填一路"}), 400
    db = SessionLocal()
    try:
        coefficient = get_coefficient(db)
    finally:
        db.close()
    try:
        if has_chord:
            chord = equivalent.validate_chord(
                equivalent.parse_number(body.get("chord_mm"), "弦长读数")
            )
            delta_mm = round(chord * coefficient, 6)
            return jsonify(
                {
                    "input_mode": "chord",
                    "chord_mm": chord,
                    "coefficient": coefficient,
                    "delta_mm": delta_mm,
                }
            )
        delta_mm = equivalent.normalize_direct_delta(body.get("delta_mm"))
        return jsonify(
            {
                "input_mode": "delta",
                "chord_mm": None,
                "coefficient": None,
                "delta_mm": delta_mm,
            }
        )
    except ValueError as exc:
        return jsonify({"detail": f"试算被退回：{exc}"}), 400


@app.get("/api/ledger")
@require_login
def list_ledger():
    db = SessionLocal()
    try:
        rows = (
            db.query(ConversionLedger)
            .order_by(ConversionLedger.id.desc())
            .all()
        )
        return jsonify([ledger_dict(r) for r in rows])
    finally:
        db.close()


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
@require_writer
def create_log():
    body = request.get_json(silent=True) or {}
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400

    has_chord = body.get("chord_mm") is not None
    has_delta = body.get("delta_mm") is not None
    if has_chord and has_delta:
        return jsonify({"detail": "弦长读数与收敛毫米只能选填一路，不能同时提交"}), 400
    if not has_chord and not has_delta:
        return jsonify({"detail": "必须填写弦长读数或收敛毫米其中一路"}), 400

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        coefficient = get_coefficient(db)
        chord_mm = None
        used_coefficient = None
        try:
            if has_chord:
                # 测量员交弦长：后台按当前当量系数换算进单。
                chord_mm = equivalent.validate_chord(
                    equivalent.parse_number(body.get("chord_mm"), "弦长读数")
                )
                used_coefficient = equivalent.validate_coefficient(coefficient)
                delta_mm = round(chord_mm * used_coefficient, 6)
                input_mode = "chord"
            else:
                # 也可以直接填毫米：两路必须算出同一个数。
                delta_mm = equivalent.normalize_direct_delta(body.get("delta_mm"))
                input_mode = "delta"
        except ValueError as exc:
            return jsonify({"detail": f"读数被退回：{exc}"}), 400

        # 进队记录与换算流水同一事务、同一拍落下：要么一起可见，要么一起回滚。
        row = ConvergenceLog(
            chainage=chainage,
            delta_mm=delta_mm,
            chord_mm=chord_mm,
            coefficient=used_coefficient,
            input_mode=input_mode,
            status="pending",
            created_by=g.user["username"],
            created_at=now,
        )
        db.add(row)
        db.flush()  # 取 row.id 写流水，但尚未提交

        ledger = ConversionLedger(
            log_id=row.id,
            chainage=chainage,
            input_mode=input_mode,
            chord_mm=chord_mm,
            coefficient=used_coefficient,
            delta_mm=delta_mm,
            created_by=g.user["username"],
            created_at=now,
        )
        db.add(ledger)
        db.commit()
        db.refresh(row)
        return jsonify(row_dict(row)), 201
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
