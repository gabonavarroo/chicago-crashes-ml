from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.entities.base import Base

class CrashInjuries(Base):
    __tablename__ = "crash_injuries"

    crash_record_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("crashes.crash_record_id"),
        primary_key=True
    )
    injuries_fatal: Mapped[int | None] = mapped_column(Integer)
    injuries_incapacitating: Mapped[int | None] = mapped_column(Integer)
    injuries_other: Mapped[int | None] = mapped_column(Integer)

    crash = relationship("Crash", back_populates="injuries")
