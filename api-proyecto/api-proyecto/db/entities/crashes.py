from sqlalchemy import String, Numeric, TIMESTAMP, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from db.entities.base import Base

class Crash(Base):
    """
    Tabla principal de crashes (accidentes).
    
    Atributos:
        crash_record_id: ID único generado por hash SHA-512
        incident_date: Fecha y hora del incidente
        latitude: Latitud del accidente (truncada a 6 decimales)
        longitude: Longitud del accidente (truncada a 6 decimales)
        street_no: Número de calle
        street_name: Nombre de calle
    """
    __tablename__ = "crashes"

    crash_record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    incident_date: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    street_no: Mapped[int | None] = mapped_column(Integer)
    street_name: Mapped[str | None] = mapped_column(String(255))

    # Relaciones con tablas dependientes
    date_info = relationship("CrashDate", back_populates="crash", uselist=False, cascade="all, delete-orphan")
    circumstances = relationship("CrashCircumstances", back_populates="crash", uselist=False, cascade="all, delete-orphan")
    injuries = relationship("CrashInjuries", back_populates="crash", uselist=False, cascade="all, delete-orphan")
    classification = relationship("CrashClassification", back_populates="crash", uselist=False, cascade="all, delete-orphan")

    # Relaciones con vehículos y personas
    vehicles = relationship("Vehicle", back_populates="crash", cascade="all, delete-orphan")
    people = relationship("People", back_populates="crash")