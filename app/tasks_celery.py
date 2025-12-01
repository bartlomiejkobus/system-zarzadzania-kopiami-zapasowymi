from app.celery_app import celery, flask_app
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from croniter import croniter
from datetime import datetime, timedelta, timezone
from app.utils import execute_ssh_command, rsync_download_file, log_event
from app.db import db
import os
from app.config import Config
from flask_mail import Message
from app import mail
from app.models.settings import Settings

@celery.task
def check_scheduled_backups():
    with flask_app.app_context():
        now = datetime.now(timezone.utc)
        tasks = BackupTask.query.filter_by(deleted=False).all()

        for task in tasks:
            if not task.schedule:
                continue

            cron = croniter(task.schedule, now)
            prev_time = cron.get_prev(datetime)

            if 0 <= (now - prev_time).total_seconds() < 60:
                run_backup_task_celery.delay(task.id)


@celery.task(bind=True, max_retries=3)
def run_backup_task_celery(self, task_id):
    with flask_app.app_context():

        task = BackupTask.query.get(task_id)
        if not task:
            log_event(
                "Nie znaleziono zadania.",
                type="błąd",
                task_id=task_id
            )
            return {"success": False, "message": "Nie znaleziono zadania."}

        server = task.server
        task_name = task.name

        def schedule_retry(error_message):

            current_retry = self.request.retries
            max_retry = self.max_retries

            log_event(
                f"Próba {current_retry + 1} z {max_retry + 1}: {error_message}",
                type="informacja",
                task_id=task.id,
                server_id=server.id
            )

            if current_retry >= max_retry:
                task.last_status = "błąd"
                db.session.commit()

                log_event(
                    f"Błąd po 3 próbach ponowienia: {error_message}",
                    type="błąd",
                    task_id=task.id,
                    server_id=server.id
                )

                return {"success": False, "message": error_message}


            retry_intervals = [60, 300, 600]
            delay = retry_intervals[current_retry]

            raise self.retry(
                exc=Exception(error_message),
                countdown=delay
            )


        success, output, error_output, exit_status = execute_ssh_command(
            server,
            f"run_backup {task_name}",
            timeout=900
        )

        if not success:
            return schedule_retry(
                f"Błąd wykonania backupu."
            )

        if not output:
            return schedule_retry(
                "Nie znaleziono pliku backupu."
            )


        local_path = Config.BACKUP_FOLDER

        success, out, err, code = rsync_download_file(
            task_id=task.id,
            server=server,
            remote_path=output,
            local_path=local_path
        )

        if success:
            log_event(
                f"Pomyślnie pobrano plik backupu: {output}.",
                type="informacja",
                task_id=task.id,
                server_id=server.id
            )


        if not success:
            return schedule_retry(
                f"Błąd pobierania pliku: {output}"
            )


        task.last_status = "sukces"
        db.session.commit()

        log_event(
            "Kopia zapasowa wykonana poprawnie",
            type="informacja",
            task_id=task.id,
            server_id=server.id
        )

        return {
            "success": True,
            "message": f"Pobrano plik backupu: {output}",
            "remote_path": output
        }


@celery.task
def cleanup_old_backups():
    now = datetime.now(timezone.utc)

    files = BackupFile.query.filter_by(deleted=False).all()

    for file in files:
        retention_days = file.task.retention
        if file.creation_time + timedelta(days=retention_days) < now:
            if os.path.exists(file.path):
                try:
                    os.remove(file.path)
                    print(f"Usunięto plik backupu: {file.path}")
                except Exception as e:
                    print(f"Błąd przy usuwaniu pliku {file.path}.")
            else:
                print(f"Plik {file.path} nie istnieje, pomijam.")

            file.mark_deleted()
            db.session.add(file)

    db.session.commit()
    

@celery.task(bind=True)
def send_email(self, subject: str, body: str, recipient: str = None):
    with flask_app.app_context():
        if not recipient:
            settings = Settings.query.first()
            if not settings or not settings.email_address:
                flask_app.logger.warning("No email recipient set.")
                return False
            recipient = settings.email_address


        try:
            msg = Message(
                subject=subject,
                sender=("System kopii zapasowych", flask_app.config["MAIL_USERNAME"]),
                recipients=[recipient],
                body=body
            )
            mail.send(msg)
            return True
        except Exception as e:
            
            
            return False