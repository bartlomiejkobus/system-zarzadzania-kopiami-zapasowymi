from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.decorators import check_settings
from app.db import db
from app.models.backup_task import BackupTask
from app.models.server import Server

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

    servers = Server.query.filter_by(deleted=False).all()
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

    task = BackupTask(
        name=name,
        server_id=server_id,
        schedule=schedule,
        retention=retention,
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

    task.schedule = request.form.get("schedule")
    task.retention = request.form.get("retention")

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
        t.mark_deleted()

    db.session.commit()
    flash(f"Usunięto {len(tasks)} zadań.", "success")
    return redirect(url_for("tasks.index"))
