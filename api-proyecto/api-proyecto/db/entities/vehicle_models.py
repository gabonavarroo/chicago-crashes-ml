"""
Entity para la tabla vehicle_specs (especificaciones de vehículos).
Representa las especificaciones de uso y configuración de vehículos.
"""
from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base

class VehicleModels(Base):
    """
    Tabla de especificaciones de vehículos.
    
    Nota: El nombre de la clase es VehicleModels pero la tabla es vehicle_specs
    (por razones históricas del proyecto).
    
    Atributos:
        vehicle_id: FK a vehicle (PK)
        vehicle_use: Uso del vehículo (comercial, personal, etc.)
        vehicle_config: Configuración del vehículo
        cargo_body_type: Tipo de carrocería de carga
    """
    __tablename__ = "vehicle_specs"

    vehicle_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehicle.vehicle_id"),
        primary_key=True
    )

    vehicle_use: Mapped[str | None] = mapped_column(String(150))
    vehicle_config: Mapped[str | None] = mapped_column(String(150))
    cargo_body_type: Mapped[str | None] = mapped_column(String(150))

    # Relación con vehicle
    vehicle = relationship("Vehicle", back_populates="models")