from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from app.decorators import check_settings
from app.db import db
from app.models.server import Server
from app.utils import load_install_script, uninstall_from_server
import paramiko, socket, io
from app.models.settings import Settings


servers_bp = Blueprint('servers', __name__, url_prefix='/servers')


@servers_bp.route('/')
@login_required
@check_settings
def index():
    servers = Server.query.filter_by(deleted=False).all()
    install_script = load_install_script()
    return render_template("servers.html", servers=servers, install_script=install_script)


@servers_bp.route('/add', methods=['POST'])
@login_required
@check_settings
def add():
    name = request.form.get("name")
    hostname = request.form.get("hostname")
    port = request.form.get("port")

    if not name or not hostname or not port:
        flash("Wszystkie pola są wymagane.", "danger")
        return redirect(url_for("servers.index"))

    try:
        port = int(port)
    except ValueError:
        flash("Port musi być liczbą.", "danger")
        return redirect(url_for("servers.index"))

    server = Server(name=name, hostname=hostname, port=port)
    db.session.add(server)
    db.session.commit()

    flash("Serwer został dodany.", "success")
    return redirect(url_for("servers.index"))


@servers_bp.route('/edit/<int:server_id>', methods=['POST'])
@login_required
@check_settings
def edit(server_id):
    server = Server.query.get_or_404(server_id)

    new_name = request.form.get("name")
    if not new_name:
        flash("Nazwa nie może być pusta.", "danger")
        return redirect(url_for("servers.index"))

    server.name = new_name
    db.session.commit()

    flash("Nazwa serwera została zaktualizowana.", "success")
    return redirect(url_for("servers.index"))


@servers_bp.route('/delete', methods=['POST'])
@login_required
@check_settings
def delete():
    ids = request.form.getlist("server_ids")

    if not ids:
        flash("Nie wybrano żadnych serwerów.", "danger")
        return redirect(url_for("servers.index"))

    servers = Server.query.filter(Server.id.in_(ids)).all()

    settings = Settings.query.first()
    private_key = paramiko.Ed25519Key.from_private_key(io.StringIO(settings.private_key_ssh))

    for s in servers:
        if s.status == "aktywny":
            try:
                ok = uninstall_from_server(s, private_key)
                if not ok:
                    print(f"Uninstall nieudany na serwerze {s.hostname}")
            except Exception as e:
                print(f"Błąd uninstall na {s.hostname}: {e}")
        else:
            print(f"Serwer {s.hostname} nieaktywny - pomijam uninstall po SSH")

        s.mark_deleted()

    db.session.commit()

    flash(f"Usunięto {len(servers)} serwer/y.", "success")
    return redirect(url_for("servers.index"))


@servers_bp.route("/test-connection/<int:server_id>", methods=["POST"])
@login_required
@check_settings
def test_server_connection(server_id):
    server = Server.query.get_or_404(server_id)
    settings = Settings.query.first()

    key = paramiko.Ed25519Key.from_private_key(io.StringIO(settings.private_key_ssh))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:

        ssh.connect(
            hostname=server.hostname,
            port=server.port,
            username="backup_user",
            pkey=key,
            timeout=5
        )

        cmd = "check"

        stdin, stdout, stderr = ssh.exec_command(cmd)

        output = stdout.read().decode(errors="replace").strip()
        error_output = stderr.read().decode(errors="replace").strip()
        exit_status = stdout.channel.recv_exit_status()

        ssh.close()

        server.status = "aktywny" if exit_status == 0 else "nieaktywny"
        db.session.commit()


        return {
            "success": exit_status == 0,
            "output": output,
            "error": error_output,
            "exit_code": exit_status
        }, (200 if exit_status == 0 else 400)

    except Exception as e:
        return {"success": False, "error": str(e)}, 400