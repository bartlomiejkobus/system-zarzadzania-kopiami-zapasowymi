from app import create_app
from app.db import db
from app.models.settings import Settings

def seed_default_admin():
    app = create_app()

    with app.app_context():
        if "settings" in db.inspect(db.engine).get_table_names():
            if not Settings.query.filter_by(username=app.config["DEFAULT_ADMIN_USERNAME"]).first():
                default_username = app.config["DEFAULT_ADMIN_USERNAME"]
                default_password = app.config["DEFAULT_ADMIN_PASSWORD"]

                default_settings = Settings(username=default_username)
                default_settings.set_password(default_password)
                default_settings.is_default_password = True
                default_settings.generate_ssh_keys()

                db.session.add(default_settings)
                db.session.commit()
                print(f"Created default admin settings: {default_username}")
            else:
                print("Default admin already exists, skipping seed.")
        else:
            print("Settings table does not exist yet; skipping seed.")

if __name__ == "__main__":
    seed_default_admin()
