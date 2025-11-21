from flask import Blueprint, render_template
from flask_login import login_required
from app.decorators import check_settings
from app.models.event import Event

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
@login_required
@check_settings
def index():
    events = Event.query.order_by(Event.timestamp.desc()).all()

    return render_template('logs.html', events=events)