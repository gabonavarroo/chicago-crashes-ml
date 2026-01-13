"""
Entity para la tabla crash_classification.
Representa la clasificación y causas de un crash.
"""
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base


class CrashClassification(Base):
    """
    Clasificación y causas contributivas de un crash.
    
    Atributos:
        crash_record_id: FK a crashes (PK)
        first_crash_type: Primer tipo de crash
        crash_type: Tipo de crash
        prim_contributory_cause: Causa contributiva primaria
        sec_contributory_cause: Causa contributiva secundaria
        damage: Nivel de daño
        hit_and_run_i: Indicador de hit and run
    """
    __tablename__ = "crash_classification"

    crash_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("crashes.crash_record_id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True
    )
    first_crash_type: Mapped[str | None] = mapped_column(String(150))
    crash_type: Mapped[str | None] = mapped_column(String(150))
    prim_contributory_cause: Mapped[str | None] = mapped_column(String(255))
    sec_contributory_cause: Mapped[str | None] = mapped_column(String(255))
    damage: Mapped[str | None] = mapped_column(String(100))
    hit_and_run_i: Mapped[bool | None] = mapped_column(Boolean)

    # Relación con crash
    crash = relationship("Crash", back_populates="classification")