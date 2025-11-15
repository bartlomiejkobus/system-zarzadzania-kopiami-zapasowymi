from app.db import db
from sqlalchemy import Enum


class BackupTask(db.Model):
    __tablename__ = "backup_tasks"

    id = db.Column(db.Integer, primary_key=True)

    server_id = db.Column(
        db.Integer,
        db.ForeignKey("servers.id", ondelete="RESTRICT"),
        nullable=False
    )

    name = db.Column(db.Text, nullable=False)
    schedule = db.Column(db.Text, nullable=False)
    retention = db.Column(db.Integer, nullable=False)

    deleted = db.Column(db.Boolean, default=False, nullable=False)

    last_status = db.Column(
        Enum("sukces", "błąd", name="backup_status"),
        nullable=True
    )

    server = db.relationship("Server", back_populates="backup_tasks")

    files = db.relationship(
        "BackupFile",
        back_populates="task",
        lazy=True
        )

    events = db.relationship(
        "Event",
        back_populates="task",
        lazy=True
    )

    def mark_deleted(self):
        self.deleted = True

    def restore(self):
        self.deleted = False

    def __repr__(self):
        return f"<BackupTask id={self.id} name={self.name} server_id={self.server_id}>"
