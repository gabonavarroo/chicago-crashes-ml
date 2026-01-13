from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base


class CrashDate(Base):
    """
    Tabla de información temporal de crashes.
    
    Almacena el día de la semana y mes del incidente para análisis temporal.
    Esta tabla tiene una relación 1:1 con crashes (un crash tiene un único registro de fecha).
    
    Atributos:
        crash_record_id: ID único del crash (FK a crashes, PK)
        crash_day_of_week: Día de la semana (1=Lunes, 7=Domingo)
        crash_month: Mes del año (1=Enero, 12=Diciembre)
    """
    __tablename__ = "crash_date"

    crash_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("crashes.crash_record_id", ondelete="CASCADE"),
        primary_key=True,
        doc="ID único del crash (referencia a crashes.crash_record_id)"
    )
    crash_day_of_week: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Día de la semana (1=Lunes a 7=Domingo)"
    )
    crash_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Mes del año (1=Enero a 12=Diciembre)"
    )

    # Relación con Crash
    crash = relationship("Crash", back_populates="date_info")
    
    def __repr__(self) -> str:
        """Representación en string de CrashDate."""
        return f"CrashDate(crash_record_id={self.crash_record_id}, day={self.crash_day_of_week}, month={self.crash_month})"
