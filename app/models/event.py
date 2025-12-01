from app.db import db
from sqlalchemy import Enum
from datetime import datetime, timezone


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)

    server_id = db.Column(
        db.Integer,
        db.ForeignKey("servers.id", ondelete="SET NULL"),
        nullable=True
    )

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("backup_tasks.id", ondelete="SET NULL"),
        nullable=True
    )

    type = db.Column(
        Enum("informacja", "błąd", "logowanie", name="event_type"),
        nullable=False
    )

    timestamp = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    details = db.Column(db.Text, nullable=False)

    # Relacje
    server = db.relationship("Server", back_populates="events", lazy=True)
    task = db.relationship("BackupTask", back_populates="events", lazy=True)

    def __repr__(self):
        return (
            f"<Event id={self.id} type={self.type} "
            f"server_id={self.server_id} task_id={self.task_id}>"
        )
