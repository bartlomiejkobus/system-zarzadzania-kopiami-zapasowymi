from app.db import db


class BackupFile(db.Model):
    __tablename__ = "backup_files"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(
        db.Integer,
        db.ForeignKey("backup_tasks.id", ondelete="RESTRICT"),
        nullable=False
    )

    name = db.Column(db.Text, nullable=False)
    size = db.Column(db.Integer, nullable=False)
    path = db.Column(db.Text, nullable=False)

    creation_time = db.Column(db.DateTime, nullable=False)

    checksum = db.Column(db.String(128), nullable=False)

    deleted = db.Column(db.Boolean, default=False, nullable=False)

    task = db.relationship("BackupTask", back_populates="files", lazy=True)

    def mark_deleted(self):
        self.deleted = True

    def restore(self):
        self.deleted = False

    def __repr__(self):
        return f"<BackupFile id={self.id} task_id={self.task_id} name={self.name}>"
