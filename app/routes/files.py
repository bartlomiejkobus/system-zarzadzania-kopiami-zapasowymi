from flask import Blueprint, render_template
from datetime import datetime
from flask_login import login_required
from app.decorators import check_settings


files_bp = Blueprint('files', __name__, url_prefix='/files')


@files_bp.route('/')
@login_required
@check_settings
def index():
    tasks = [
        {
            'id': 1,
            'name': 'Backup serwera A',
            'files': [
                {'name': 'plik1.tar.gz', 'size': '10 MB', 'checksum': 'abcd1234', 'created': datetime(2025, 11, 11, 10, 30)},
                {'name': 'plik2.tar.gz', 'size': '20 MB', 'checksum': 'efgh5678', 'created': datetime(2025, 11, 11, 12, 15)}
            ]
        },
        {
            'id': 2,
            'name': 'Backup serwera B',
            'files': [
                {'name': 'plik3.tar.gz', 'size': '15 MB', 'checksum': 'ijkl9101', 'created': datetime(2025, 11, 10, 9, 0)}
            ]
        }
    ]
    return render_template('files.html', tasks=tasks)
