import os
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

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
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EquivalentParam(Base):
    """当量参数（单行，id 固定为 1）：弦长按它换算成收敛毫米。"""

    __tablename__ = "equivalent_params"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factor: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_mm: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversionRecord(Base):
    """换算流水：每条进队记录对应一行，与进队记录同一事务落库。"""

    __tablename__ = "conversion_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    log_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("convergence_logs.id"), nullable=False, unique=True
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)  # chord=弦长换算 / direct=直填毫米
    chord_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_mm: Mapped[float] = mapped_column(Float, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def row_dict(row: ConvergenceLog) -> dict:
    return {
        "id": row.id,
        "chainage": row.chainage,
        "delta_mm": row.delta_mm,
        "status": row.status,
        "verdict": row.verdict,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


def equivalent_dict(row: EquivalentParam) -> dict:
    return {
        "factor": row.factor,
        "baseline_mm": row.baseline_mm,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def conversion_dict(row: ConversionRecord, chainage: str | None = None) -> dict:
    return {
        "id": row.id,
        "log_id": row.log_id,
        "chainage": chainage,
        "mode": row.mode,
        "chord_mm": row.chord_mm,
        "factor": row.factor,
        "baseline_mm": row.baseline_mm,
        "delta_mm": row.delta_mm,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
