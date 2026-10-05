import os
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from equivalent import DEFAULT_COEFF

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54401/tunnelconv")
engine = create_engine(DSN, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class ConvergenceLog(Base):
    __tablename__ = "convergence_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chainage: Mapped[str] = mapped_column(String, nullable=False)
    delta_mm: Mapped[float] = mapped_column(Float, nullable=False)
    # 弦长路留痕：原始弦长与换算所用当量系数；直填毫米路两者均为空。
    chord_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    coefficient: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_mode: Mapped[str] = mapped_column(String, nullable=False, default="delta")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EquivalentSetting(Base):
    """当量系数单行表：id 恒为 1，测量员维护，巡检员只读。"""

    __tablename__ = "equivalent_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coefficient: Mapped[float] = mapped_column(Float, nullable=False, default=DEFAULT_COEFF)
    updated_by: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversionLedger(Base):
    """换算流水：与进队记录在同一事务、同一拍落下。"""

    __tablename__ = "conversion_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    log_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chainage: Mapped[str] = mapped_column(String, nullable=False)
    input_mode: Mapped[str] = mapped_column(String, nullable=False)
    chord_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    coefficient: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_mm: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def init_schema():
    """建表并对既有表做轻量加列迁移（基线库可能已存在）。"""
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("convergence_logs")}
    add_cols = {
        "chord_mm": "ADD COLUMN chord_mm DOUBLE PRECISION",
        "coefficient": "ADD COLUMN coefficient DOUBLE PRECISION",
        "input_mode": "ADD COLUMN input_mode VARCHAR NOT NULL DEFAULT 'delta'",
    }
    with engine.begin() as conn:
        for name, ddl in add_cols.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE convergence_logs {ddl}"))


def row_dict(row: ConvergenceLog) -> dict:
    return {
        "id": row.id,
        "chainage": row.chainage,
        "delta_mm": row.delta_mm,
        "chord_mm": row.chord_mm,
        "coefficient": row.coefficient,
        "input_mode": row.input_mode,
        "status": row.status,
        "verdict": row.verdict,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


def setting_dict(row: EquivalentSetting) -> dict:
    return {
        "coefficient": row.coefficient,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def ledger_dict(row: ConversionLedger) -> dict:
    return {
        "id": row.id,
        "log_id": row.log_id,
        "chainage": row.chainage,
        "input_mode": row.input_mode,
        "chord_mm": row.chord_mm,
        "coefficient": row.coefficient,
        "delta_mm": row.delta_mm,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
