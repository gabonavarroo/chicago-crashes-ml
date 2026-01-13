"""
Entity para la tabla vehicle_violations.
Representa violaciones y condiciones del vehículo durante el crash.
"""
from sqlalchemy import Boolean, String, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base


class VehicleViolations(Base):
    """
    Tabla de violaciones del vehículo.
    
    Almacena información sobre:
    - Si es vehículo comercial
    - Si excedió el límite de velocidad
    - Si transportaba materiales peligrosos
    - Defectos del vehículo
    
    Atributos:
        vehicle_id: FK a vehicle (PK)
        cmrc_veh_i: Indicador de vehículo comercial (booleano)
        exceed_speed_limit_i: Indicador de exceso de velocidad (booleano)
        hazmat_present_i: Indicador de materiales peligrosos (booleano)
        vehicle_defect: Descripción del defecto del vehículo
    
    Relaciones:
        - vehicle: Relación many-to-one con Vehicle
    
    Constraints:
        - PK: vehicle_id
        - FK: vehicle_id REFERENCES vehicle(vehicle_id)
        - Un vehículo solo puede tener un registro de violaciones
    """
    __tablename__ = "vehicle_violations"

    vehicle_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehicle.vehicle_id"),
        primary_key=True
    )
    cmrc_veh_i: Mapped[bool | None] = mapped_column(Boolean)
    exceed_speed_limit_i: Mapped[bool | None] = mapped_column(Boolean)
    hazmat_present_i: Mapped[bool | None] = mapped_column(Boolean)
    vehicle_defect: Mapped[str | None] = mapped_column(String(100))

    # Relación con vehicle
    vehicle = relationship("Vehicle", back_populates="violations")