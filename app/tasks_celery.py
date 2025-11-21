from app.celery_app import celery, flask_app
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from croniter import croniter
from datetime import datetime, timedelta
from app.utils import execute_ssh_command, rsync_download_file, log_event
from app.db import db
import os
from app.config import Config

@celery.task
def check_scheduled_backups():
    with flask_app.app_context():
        now = datetime.now()
        tasks = BackupTask.query.filter_by(deleted=False).all()

        for task in tasks:
            if not task.schedule:
                continue

            cron = croniter(task.schedule, now)
            prev_time = cron.get_prev(datetime)

            if 0 <= (now - prev_time).total_seconds() < 60:
                run_backup_task_celery.delay(task.id)


@celery.task(bind=True)
def run_backup_task_celery(self, task_id):
    with flask_app.app_context():
        task = BackupTask.query.get(task_id)
        if not task:
            log_event(f"Nie znaleziono zadania.", type="błąd", task_id=task.id, server_id=task.server.id)
            return {"success": False, "message": "Nie znaleziono zadania."}

        task_name = task.name
        server = task.server

        success, output, error_output, exit_status = execute_ssh_command(
            server, f"run_backup {task_name}", timeout=120
        )

        if not success:
            task.last_status = "błąd"
            db.session.commit()
            log_event(f"Błąd wykonania kopii zapasowej: {error_output}", type="błąd", task_id=task.id, server_id=task.server.id)
            return {"success": False, "message": f"Błąd wykonania kopii zapasowej: {error_output}"}

        if not output:
            task.last_status = "błąd"
            db.session.commit()
            log_event(f"Nie znaleziono pliku kopii zapasowej.", type="błąd", task_id=task.id, server_id=task.server.id)
            return {"success": False, "message": "Nie znaleziono pliku kopii zapasowej."}

        local_path = Config.BACKUP_FOLDER

        success, out, err, code = rsync_download_file(
            task_id=task.id,
            server=server,
            remote_path=output,
            local_path=local_path
        )

        if not success:
            task.last_status = "błąd"
            db.session.commit()
            log_event(f"Błąd pobierania pliku: {err}", type="błąd", task_id=task.id, server_id=task.server.id)
            return {"success": False, "message": f"Błąd pobierania pliku: {err}"}

        task.last_status = "sukces"
        db.session.commit()
        log_event(f"Kopia zapasowa wykonana poprawnie", type="informacja", task_id=task.id, server_id=task.server.id)

        return {
            "success": True,
            "message": f"Pobrano plik backupu: {output}",
            "remote_path": output
        }


@celery.task
def cleanup_old_backups():
    now = datetime.now()

    now = datetime.now()
    files = BackupFile.query.filter_by(deleted=False).all()

    for file in files:
        retention_days = file.task.retention
        if file.creation_time + timedelta(days=retention_days) < now:
            if os.path.exists(file.path):
                try:
                    os.remove(file.path)
                    print(f"Usunięto plik backupu: {file.path}")
                except Exception as e:
                    print(f"Błąd przy usuwaniu pliku {file.path}: {e}")
            else:
                print(f"Plik {file.path} nie istnieje, pomijam.")

            file.mark_deleted()
            db.session.add(file)

    db.session.commit()