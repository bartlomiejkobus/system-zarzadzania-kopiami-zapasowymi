from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for
from datetime import datetime
from flask_login import login_required
from app.decorators import check_settings
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from app.db import db
import os

files_bp = Blueprint('files', __name__, url_prefix='/files')


@files_bp.route('/')
@login_required
@check_settings
def index():
    tasks_query = BackupTask.query.filter_by().all()

    tasks = []
    for task in tasks_query:
        task_data = {
            'id': task.id,
            'name': task.name,
            'server': task.server,
            'files': []
        }
        for file in task.files:
            if not file.deleted:
                task_data['files'].append({
                    'id': file.id,
                    'name': file.name,
                    'size': f"{file.size / (1024*1024):.2f} MB",
                    'checksum': file.checksum,
                    'created': file.creation_time
                })

        tasks.append(task_data)

    return render_template('files.html', tasks=tasks)




@files_bp.route('/download', methods=['POST'])
@login_required
def download_files():
    file_ids = request.form.getlist('file_ids')
    if not file_ids:
        flash("Nie zaznaczono żadnych plików!", "warning")
        return redirect(url_for('files.index'))

    import os, io, zipfile
    files_to_send = []

    for file_id in file_ids:
        file = BackupFile.query.get(file_id)
        if file and not file.deleted and os.path.exists(file.path):
            files_to_send.append(file.path)

    if not files_to_send:
        flash("Nie znaleziono plików do pobrania.", "danger")
        return redirect(url_for('files.index'))

    if len(files_to_send) == 1:
        return send_file(files_to_send[0], as_attachment=True)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for path in files_to_send:
            zf.write(path, os.path.basename(path))
    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip',
                     as_attachment=True, download_name='backup_files.zip')