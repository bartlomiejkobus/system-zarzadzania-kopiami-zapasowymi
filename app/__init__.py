from flask import Flask
from flask_migrate import Migrate
from sqlalchemy import inspect
from app.db import db
from app.models.settings import Settings
from app.models.server import Server
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from app.models.event import Event
from flask_login import LoginManager
from flask_mail import Mail

mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    db.init_app(app)
    Migrate(app, db)
    
    mail.init_app(app)
        
    with app.app_context():
        inspector = inspect(db.engine)
        if "settings" in inspector.get_table_names():
            if not Settings.query.first():
                default_username = app.config["DEFAULT_ADMIN_USERNAME"]
                default_password = app.config["DEFAULT_ADMIN_PASSWORD"]

                default_settings = Settings(username=default_username)
                default_settings.set_password(default_password, default_password=default_password)
                default_settings.generate_ssh_keys()

                db.session.add(default_settings)
                db.session.commit()
                app.logger.info(f"Created default admin settings: {default_username}")
            else:
                app.logger.info("Settings record already exists - no seed needed.")
        else:
            app.logger.warning("Settings table does not exist yet; skipping default admin seed.")


    from app.routes.dashboard import dashboard_bp
    from app.routes.servers import servers_bp
    from app.routes.tasks import tasks_bp
    from app.routes.files import files_bp
    from app.routes.logs import logs_bp
    from app.routes.settings import settings_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auth_bp)


    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    
    login_manager.login_message = app.config["LOGIN_MESSAGE"]
    
    @login_manager.user_loader
    def load_user(username):
        return Settings.query.filter_by(username=username).first()
    
    return app
