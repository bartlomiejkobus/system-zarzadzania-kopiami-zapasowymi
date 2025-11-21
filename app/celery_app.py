from celery import Celery
from app import create_app
from app.db import db
import os
from celery.schedules import crontab
from app.models.backup_task import BackupTask
from app.config import Config
from app.utils import execute_ssh_command, rsync_download_file


flask_app = create_app()


celery = Celery(
    'backup_tasks',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

class ContextTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask


celery.conf.beat_schedule = {
    "check-scheduled-backups-every-minute": {
        "task": "app.tasks_celery.check_scheduled_backups",
        "schedule": crontab(),
    },
}

celery.conf.beat_schedule.update({
    'cleanup-old-backups-daily': {
        'task': 'app.tasks_celery.cleanup_old_backups',
        'schedule': crontab(hour=3, minute=0),
    },
})

celery.conf.timezone = 'Europe/Warsaw'

import app.tasks_celery
