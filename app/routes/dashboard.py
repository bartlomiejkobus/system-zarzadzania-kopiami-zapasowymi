from flask import Blueprint, render_template
from flask_login import login_required
from app.decorators import check_settings
from app.models.server import Server
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from app.models.event import Event

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')


@dashboard_bp.route('/')
@login_required
@check_settings
def index():
    server_count = Server.query.filter_by(deleted=False).count()
    tasks = BackupTask.query.filter_by(deleted=False)
    task_count = tasks.count()
    fails_count = tasks.filter_by(last_status="błąd").count()
    file_count = BackupFile.query.filter_by(deleted=False).count()

    # Ostatnie 5 błędów
    last_errors = Event.query.filter_by(type="błąd").order_by(Event.timestamp.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        server_count=server_count,
        task_count=task_count,
        fails_count=fails_count,
        file_count=file_count,
        last_errors=last_errors
    )