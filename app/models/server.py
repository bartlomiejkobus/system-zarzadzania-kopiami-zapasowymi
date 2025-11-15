from app.db import db


class Server(db.Model):
    __tablename__ = "servers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    hostname = db.Column(db.Text, nullable=False)
    port = db.Column(db.Integer, nullable=False)
    deleted = db.Column(db.Boolean, default=False)

    def mark_deleted(self):
        self.deleted = True

    def restore(self):
        self.deleted = False

    backup_tasks = db.relationship("BackupTask", back_populates="server", lazy=True)
    
    events = db.relationship(
        "Event",
        back_populates="server",
        lazy=True
    )

    def __repr__(self):
        return f"<Server id={self.id} name={self.name} host={self.hostname}:{self.port}>"
