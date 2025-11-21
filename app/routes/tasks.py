from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required
from app.decorators import check_settings
from app.db import db
from app.models.backup_task import BackupTask
from app.models.server import Server
from app.utils import execute_ssh_command, rsync_download_file
import re
from croniter import croniter
from datetime import datetime



tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')


@tasks_bp.route('/')
@login_required
@check_settings
def index():
    tasks = (
        BackupTask.query
        .filter_by(deleted=False)
        .join(Server)
        .add_entity(Server)
        .all()
    )

    servers = Server.query.filter(
    Server.deleted == False,
    Server.status == "aktywny"
    ).all()
    return render_template('tasks.html', tasks=tasks, servers=servers)


@tasks_bp.route('/add', methods=['POST'])
@login_required
@check_settings
def add():
    name = request.form.get("name")
    server_id = request.form.get("server_id")
    schedule = request.form.get("schedule")
    retention = request.form.get("retention")

    if not name or not server_id or not schedule or not retention:
        flash("Wszystkie pola są wymagane.", "danger")
        return redirect(url_for("tasks.index"))

    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        flash("Nazwa zadania może zawierać tylko litery, cyfry, '-' i '_', bez spacji.", "danger")
        return redirect(url_for("tasks.index"))

    try:
        croniter(schedule)
    except (ValueError, KeyError):
        flash("Niepoprawny format harmonogramu. Użyj składni crona, np. '0 3 * * *'.", "danger")
        return redirect(url_for("tasks.index"))

    existing_task = BackupTask.query.filter_by(server_id=server_id, name=name, deleted=False).first()
    if existing_task:
        flash(f"Zadanie o nazwie '{name}' już istnieje na tym serwerze.", "danger")
        return redirect(url_for("tasks.index"))

    server = Server.query.get_or_404(server_id)

    success, output, error_output, exit_status = execute_ssh_command(
        server, f"add_task {name}"
    )
    if not success:
        flash(f"Nie udało się dodać zadania na serwerze {server.hostname}: {error_output}", "danger")
        return redirect(url_for("tasks.index"))

    task = BackupTask(
        name=name,
        server_id=server_id,
        schedule=schedule,
        retention=int(retention),
        last_status=None
    )

    db.session.add(task)
    db.session.commit()
    flash("Zadanie zostało dodane.", "success")
    return redirect(url_for("tasks.index"))


@tasks_bp.route('/edit/<int:task_id>', methods=['POST'])
@login_required
@check_settings
def edit(task_id):
    task = BackupTask.query.filter_by(id=task_id, deleted=False).first_or_404()

    new_schedule = request.form.get("schedule")
    new_retention = request.form.get("retention")

    if not new_schedule or not new_retention:
        flash("Harmonogram i retencja są wymagane.", "danger")
        return redirect(url_for("tasks.index"))

    try:
        croniter(new_schedule)
    except (ValueError, KeyError):
        flash("Niepoprawny format harmonogramu. Użyj składni crona, np. '0 3 * * *'.", "danger")
        return redirect(url_for("tasks.index"))

    task.schedule = new_schedule
    task.retention = int(new_retention)

    db.session.commit()
    flash("Zadanie zostało zaktualizowane.", "success")
    return redirect(url_for("tasks.index"))


@tasks_bp.route("/delete", methods=["POST"])
@login_required
@check_settings
def delete():
    ids = request.form.getlist("task_ids[]")

    if not ids:
        flash("Nie wybrano żadnego zadania.", "warning")
        return redirect(url_for("tasks.index"))

    tasks = BackupTask.query.filter(
        BackupTask.id.in_(ids),
        BackupTask.deleted == False
    ).all()

    for t in tasks:
        server = t.server

        if server.status == "aktywny":
            success, output, error_output, exit_status = execute_ssh_command(
                server, f"delete_task {t.name}"
            )
            
            if not success:
                print(f"Błąd usuwania zadania {t.name} na serwerze {server.hostname}: {error_output}")
            else:
                print(f"Zadanie {t.name} zostało usunięte na serwerze {server.hostname}")

        t.mark_deleted()

    db.session.commit()
    flash(f"Usunięto {len(tasks)} zadań.", "success")
    return redirect(url_for("tasks.index"))


@tasks_bp.route("/run_backup", methods=["POST"])
@login_required
@check_settings
def run_backup():
    from app.tasks_celery import run_backup_task_celery

    task_id = request.form.get("task_id")
    if not task_id:
        flash("Nie wybrano zadania.", "danger")
        return redirect(url_for("tasks.index"))

    run_backup_task_celery.delay(task_id)

    flash("Backup został uruchomiony w tle.", "info")
    return redirect(url_for("tasks.index"))