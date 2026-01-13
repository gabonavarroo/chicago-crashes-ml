from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base

class VehicleManeuvers(Base):
    __tablename__ = "vehicle_maneuvers"

    vehicle_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehicle.vehicle_id"),
        primary_key=True
    )
    maneuver: Mapped[str | None] = mapped_column(String(150))

    vehicle = relationship("Vehicle", back_populates="maneuvers")
