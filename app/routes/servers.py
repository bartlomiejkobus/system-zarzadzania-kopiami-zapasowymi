from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.decorators import check_settings
from app.db import db
from app.models.server import Server
from app.utils import load_install_script, execute_ssh_command

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

    exists = Server.query.filter(
        Server.deleted == False,
        (Server.name == name) | (Server.hostname == hostname)
    ).first()
    if exists:
        flash("Serwer o tej nazwie lub hostie już istnieje.", "danger")
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

    exists = Server.query.filter(
        Server.deleted == False,
        Server.id != server.id,
        Server.name == new_name
    ).first()
    if exists:
        flash("Serwer o tej nazwie już istnieje.", "danger")
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

    for s in servers:
        if s.status == "aktywny":
            try:
                success, output, error_output, exit_status = execute_ssh_command(
                    s, "uninstall"
                )
                if not success:
                    flash(f"Błąd deinstalacji na serwerze {s.hostname}.", "warning")
            except Exception as e:
                flash(f"Błąd deinstalacji na serwerze {s.hostname}.", "warning")


        s.mark_deleted()

    db.session.commit()

    flash(f"Usunięto {len(servers)} serwer/y oraz powiązane zadania.", "success")
    return redirect(url_for("servers.index"))


@servers_bp.route("/test-connection/<int:server_id>", methods=["POST"])
@login_required
@check_settings
def test_server_connection(server_id):
    server = Server.query.get_or_404(server_id)

    success, output, error_output, exit_status = execute_ssh_command(
        server, "check", timeout=5
    )

    server.status = "aktywny" if success else "nieaktywny"
    db.session.commit()

    return {
        "success": success,
        "output": output,
        "error": error_output,
        "exit_code": exit_status
    }, (200 if success else 400)