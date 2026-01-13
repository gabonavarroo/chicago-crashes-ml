from sqlalchemy import BigInteger, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base

class Vehicle(Base):
    __tablename__ = "vehicle"

    vehicle_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    crash_unit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    crash_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("crashes.crash_record_id", onupdate="CASCADE", ondelete="CASCADE")
    )

    unit_no: Mapped[int | None] = mapped_column(Integer)
    unit_type: Mapped[str | None] = mapped_column(String(30))
    num_passengers: Mapped[int | None] = mapped_column(Integer)
    vehicle_year: Mapped[int | None] = mapped_column(Integer)
    make: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    vehicle_type: Mapped[str | None] = mapped_column(String(200))


    crash = relationship("Crash", back_populates="vehicles")

    models = relationship("VehicleModels", back_populates="vehicle", cascade="all, delete-orphan")
    maneuvers = relationship("VehicleManeuvers", back_populates="vehicle", cascade="all, delete-orphan")
    violations = relationship("VehicleViolations", back_populates="vehicle", uselist=False, cascade="all, delete-orphan")

    people = relationship("People", back_populates="vehicle")
