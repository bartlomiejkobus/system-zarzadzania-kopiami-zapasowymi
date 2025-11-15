from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.decorators import check_settings
from app.db import db
from app.models.server import Server

servers_bp = Blueprint('servers', __name__, url_prefix='/servers')


@servers_bp.route('/')
@login_required
@check_settings
def index():
    servers = Server.query.filter_by(deleted=False).all()
    return render_template('servers.html', servers=servers)


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

    for s in servers:
        s.mark_deleted()

    db.session.commit()

    flash(f"Usunięto {len(servers)} serwer/y.", "success")
    return redirect(url_for("servers.index"))
