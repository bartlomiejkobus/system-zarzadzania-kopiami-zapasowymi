from flask import current_app
from app.models.settings import Settings
import paramiko, socket, io


def load_install_script():
    settings = Settings.query.first()

    if not settings or not settings.public_key_ssh or not settings.public_key_gpg:
        return "# BŁĄD: Klucz publiczny SSH i/lub GPG nie został znaleziony\n"


    script_path = current_app.root_path + "/scripts/install.sh"
    with open(script_path, "r") as f:
        script = f.read()

    script = script.replace("__SSH_PUB_KEY__", settings.public_key_ssh.strip())
    script = script.replace("__GPG_PUB_KEY__", settings.public_key_gpg.strip())

    return script


def uninstall_from_server(server, private_key):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=server.hostname,
            port=server.port,
            username="backup_user",
            pkey=private_key,
            timeout=5
        )

        cmd = "uninstall"
        stdin, stdout, stderr = ssh.exec_command(cmd)

        exit_status = stdout.channel.recv_exit_status()
        ssh.close()

        return exit_status == 0

    except Exception:
        return False