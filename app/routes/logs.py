from flask import Blueprint, render_template
from flask_login import login_required
from app.decorators import check_settings

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
@login_required
@check_settings
def index():
    return render_template('logs.html')
