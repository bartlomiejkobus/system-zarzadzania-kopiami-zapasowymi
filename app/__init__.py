from flask import Flask
from flask_migrate import Migrate
from app.db import db
from flask_login import LoginManager
from flask_mail import Mail

mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    db.init_app(app)
    Migrate(app, db)
    mail.init_app(app)

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
    login_manager.login_message = 'Aby uzyskać dostęp, musisz się zalogować.'

    from app.models.settings import Settings

    @login_manager.user_loader
    def load_user(username):
        return Settings.query.filter_by(username=username).first()

    return app
