from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base

class CrashCircumstances(Base):
    """
    Tabla de circunstancias del crash.
    Almacena condiciones del entorno, tráfico y características del lugar.
    """
    __tablename__ = "crash_circumstances"

    crash_record_id: Mapped[str] = mapped_column(
        ForeignKey("crashes.crash_record_id"),
        primary_key=True
    )

    traffic_control_device: Mapped[str | None] = mapped_column(String(100))
    device_condition: Mapped[str | None] = mapped_column(String(100))
    weather_condition: Mapped[str | None] = mapped_column(String(100))
    lighting_condition: Mapped[str | None] = mapped_column(String(100))
    lane_cnt: Mapped[int | None] = mapped_column(Integer)
    roadway_surface_cond: Mapped[str | None] = mapped_column(String(100))
    road_defect: Mapped[str | None] = mapped_column(String(100))
    num_units: Mapped[int | None] = mapped_column(Integer)
    posted_speed_limit: Mapped[int | None] = mapped_column(Integer)
    intersection_related_i: Mapped[bool | None] = mapped_column(Boolean)
    not_right_of_way_i: Mapped[bool | None] = mapped_column(Boolean)

    crash = relationship("Crash", back_populates="circumstances")
