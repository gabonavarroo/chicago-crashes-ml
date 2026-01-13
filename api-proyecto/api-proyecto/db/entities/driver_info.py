"""
Entity para la tabla driver_info.
Representa información específica del conductor.
"""
from sqlalchemy import Float, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base


class DriverInfo(Base):
    """
    Información detallada del conductor involucrado en un crash.
    
    Atributos:
        person_id: FK a people (PK)
        driver_action: Acción del conductor
        driver_vision: Condición de visión del conductor
        physical_condition: Condición física del conductor
        bac_result_value: Nivel de alcohol en sangre (BAC)
        cell_phone_use: Indicador de uso de celular
        drivers_license_class: Clase de licencia del conductor
    """
    __tablename__ = "driver_info"

    person_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("people.person_id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True
    )

    driver_action: Mapped[str | None] = mapped_column(String(50))
    driver_vision: Mapped[str | None] = mapped_column(String(50))
    physical_condition: Mapped[str | None] = mapped_column(String(50))
    bac_result_value: Mapped[float | None] = mapped_column(Float)
    cell_phone_use: Mapped[bool | None] = mapped_column(Boolean)
    drivers_license_class: Mapped[str | None] = mapped_column(String(10))

    # Relación con people
    person = relationship("People", back_populates="driver_info")