from flask import current_app, request
from app.models.settings import Settings
import paramiko, io
from app.models.backup_task import BackupTask
from app.models.backup_file import BackupFile
from app.models.server import Server
import tempfile
import os
import subprocess
import hashlib
from datetime import datetime, timezone
from app.db import db
from app.models.event import Event
import string, secrets

def generate_code(length=6):
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def load_install_script():
    settings = Settings.query.first()

    if not settings or not settings.command_public_key_ssh or not settings.public_key_gpg:
        return "# BŁĄD: Klucz publiczny SSH i/lub GPG nie został znaleziony\n"


    script_path = current_app.root_path + "/scripts/install.sh"
    with open(script_path, "r") as f:
        script = f.read()

    script = script.replace("__COMMAND_SSH_PUB_KEY__", settings.command_public_key_ssh.strip())
    script = script.replace("__RSYNC_SSH_PUB_KEY__", settings.rsync_public_key_ssh.strip())
    script = script.replace("__GPG_PUB_KEY__", settings.public_key_gpg.strip())

    return script


def execute_ssh_command(server, cmd, username="backup_user", timeout=60):

    private_key = get_private_key_for_paramiko()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    
    try:
        ssh.connect(
            hostname=server.hostname,
            port=server.port,
            username=username,
            pkey=private_key,
            timeout=timeout
        )

        stdin, stdout, stderr = ssh.exec_command(cmd)

        output = stdout.read().decode(errors="replace").strip()
        error_output = stderr.read().decode(errors="replace").strip()
        exit_status = stdout.channel.recv_exit_status()

        ssh.close()

        return (exit_status == 0, output, error_output, exit_status)

    except Exception as e:
        return (False, str(e), "", -1)
    
    
def get_private_key_for_paramiko():

    try:
        settings = Settings.query.first()
        if settings and settings.command_private_key_ssh:
            return paramiko.Ed25519Key.from_private_key(io.StringIO(settings.command_private_key_ssh))
        else:
            return None
    except Exception as e:
        return None
    
def get_private_key_for_rsync():
    settings = Settings.query.first()
    return settings.rsync_private_key_ssh if settings else None
    
def rsync_download_file(task_id, server, remote_path, local_path, username="backup_user"):
    private_key_str = get_private_key_for_rsync()
    if not private_key_str:
        return False, "", "Brak klucza prywatnego w ustawieniach", -1

    key_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, mode="w", prefix="ssh_key_", suffix=".pem") as key_file:
            key_path = key_file.name

        os.chmod(key_path, 0o600)

        with open(key_path, "w") as key_file:
            key_file.write(private_key_str)

        remote = f"{username}@{server.hostname}:{remote_path}"
        cmd = [
            "rsync",
            "-avz",
            "--remove-source-files",
            "-e", f"ssh -T -i {key_path} -p {server.port} -o StrictHostKeyChecking=no",
            remote,
            local_path
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        success = result.returncode == 0
        stdout = result.stdout.decode(errors="replace")
        stderr = result.stderr.decode(errors="replace")

        file_path = f"{local_path}/{remote_path}"
        if success:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                creation_time = datetime.fromtimestamp(os.path.getctime(file_path),tz=timezone.utc)
                sha256_hash = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                checksum = sha256_hash.hexdigest()

                task = BackupTask.query.get(task_id)
                if task:
                    backup_file = BackupFile(
                        task_id=task.id,
                        name=os.path.basename(file_path),
                        size=size,
                        path=file_path,
                        creation_time=creation_time,
                        checksum=checksum
                    )
                    db.session.add(backup_file)
                    db.session.commit()

        return success, stdout, stderr, result.returncode

    except Exception as e:
        return False, "", f"Błąd: {e}", -1

    finally:
        if key_path and os.path.exists(key_path):
            os.remove(key_path)


def log_event(details: str, type: str = "informacja", server_id: int = None, task_id: int = None):
    timestamp = datetime.now(timezone.utc)

    event = Event(
        type=type,
        details=details,
        timestamp=timestamp,
        server_id=server_id,
        task_id=task_id
    )
    db.session.add(event)
    db.session.commit()

    if type == "błąd":
        settings = Settings.query.first()

        if settings and settings.are_notifications_enabled and settings.email_address:
            from app.tasks_celery import send_email
            server_name = Server.query.with_entities(Server.name).filter_by(id=server_id).scalar()
            task_name = BackupTask.query.with_entities(BackupTask.name).filter_by(id=task_id).scalar()
            
            subject=f"Błąd - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            body = f"""
Wystąpił błąd w systemie kopii zapasowych:

Szczegóły: {details}
Czas wystąpienia: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Serwer: {server_name}
Zadanie: {task_name}
            """
            send_email.delay(subject, body)
        
def get_client_info():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    ua = request.headers.get('User-Agent', 'unknown')
    return ip, ua