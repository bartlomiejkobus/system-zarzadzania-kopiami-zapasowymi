from flask import Blueprint, render_template
from flask_login import login_required
from app.decorators import check_settings
from app.models.server import Server
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from app.db import db

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')


@dashboard_bp.route('/')
@login_required
@check_settings
def index():
    server_count = Server.query.filter_by(deleted=False).count()
    task_count = BackupTask.query.filter_by(deleted=False).count()
    file_count = BackupFile.query.count()

    return render_template(
        'dashboard.html',
        server_count=server_count,
        task_count=task_count,
        file_count=file_count,
    )
