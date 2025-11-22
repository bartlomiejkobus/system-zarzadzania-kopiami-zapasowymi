from flask import Blueprint, render_template, make_response, request
from flask_login import login_required
from app.decorators import check_settings
from app.models.event import Event
import csv
from io import StringIO
from datetime import datetime

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
@login_required
@check_settings
def index():
    selected_types = request.args.getlist('type')
    all_types = ('informacja', 'błąd', 'logowanie')
    if not selected_types:
        selected_types = list(all_types)

    query = Event.query.order_by(Event.timestamp.desc()).filter(Event.type.in_(selected_types))

    start_date = request.args.get('start')
    end_date = request.args.get('end')

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Event.timestamp >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Event.timestamp <= end_dt)
        except ValueError:
            pass

    page = request.args.get('page', 1, type=int)
    per_page = 20
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    events = pagination.items

    return render_template(
        'logs.html',
        events=events,
        selected_types=selected_types,
        start_date=start_date,
        end_date=end_date,
        pagination=pagination
    )



@logs_bp.route('/export')
@login_required
@check_settings
def export_logs():
    events = Event.query.order_by(Event.timestamp.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    
    cw.writerow(['ID', 'Typ', 'Timestamp', 'Szczegóły', 'Zadanie', 'Serwer'])

    for event in events:
        cw.writerow([
            event.id,
            event.type,
            event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            event.details,
            event.task.name if event.task else '',
            event.server.name if event.server else ''
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=logs.csv"
    output.headers["Content-type"] = "text/csv"
    return output