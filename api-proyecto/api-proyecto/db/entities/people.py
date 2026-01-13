"""
Entity para la tabla people.
Representa personas involucradas en accidentes.
"""
from sqlalchemy import String, Integer, TIMESTAMP, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from db.entities.base import Base


class People(Base):
    """
    Tabla de personas involucradas en crashes.
    
    Atributos:
        person_id: ID único en formato Q0000001, Q0000002, etc.
        person_type: Tipo de persona (conductor, pasajero, peatón)
        crash_record_id: FK a crashes (opcional)
        vehicle_id: FK a vehicle (opcional)
        sex: Sexo de la persona
        age: Edad de la persona
        safety_equipment: Equipo de seguridad usado
        airbag_deployed: Estado del airbag
        injury_classification: Clasificación de lesión
    """
    __tablename__ = "people"

    person_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    person_type: Mapped[str | None] = mapped_column(String(50))

    crash_record_id: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("crashes.crash_record_id")
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("vehicle.vehicle_id")
    )

    sex: Mapped[str | None] = mapped_column(String(10))
    age: Mapped[int | None] = mapped_column(Integer)
    safety_equipment: Mapped[str | None] = mapped_column(String(200))
    airbag_deployed: Mapped[str | None] = mapped_column(String(100))
    injury_classification: Mapped[str | None] = mapped_column(String(100))

    # Relaciones
    crash = relationship("Crash", back_populates="people")
    vehicle = relationship("Vehicle", back_populates="people")
    driver_info = relationship("DriverInfo", back_populates="person", uselist=False, cascade="all, delete-orphan")