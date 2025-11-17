from flask_login import UserMixin
from app.db import db
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


ph = PasswordHasher(
    time_cost=4,
    memory_cost=32 * 1024,
    parallelism=2,
    hash_len=32,
    type=Type.ID
)


class Settings(db.Model, UserMixin):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_default_password = db.Column(db.Boolean, default=True)
    email_address = db.Column(db.String(255), nullable=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    are_notifications_enabled = db.Column(db.Boolean, default=False)
    public_key_gpg = db.Column(db.Text, nullable=True)
    public_key_ssh = db.Column(db.Text, nullable=True)
    private_key_ssh = db.Column(db.Text, nullable=True)

    def set_password(self, password: str, default_password: str = None):
        self.password_hash = ph.hash(password)

        if default_password:
            try:
                ph.verify(self.password_hash, default_password)
                self.is_default_password = True
            except VerifyMismatchError:
                self.is_default_password = False
        else:
            self.is_default_password = False

    def check_password(self, password: str) -> bool:
        try:
            return ph.verify(self.password_hash, password)
        except VerifyMismatchError:
            return False

    def has_gpg_key(self) -> bool:
        return bool(self.public_key_gpg and self.public_key_gpg.strip())
    
    def generate_ssh_keys(self):
        private_key = ed25519.Ed25519PrivateKey.generate()
        self.private_key_ssh = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        self.public_key_ssh = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode()

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.username
