from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def check_settings(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_default_password or not current_user.has_gpg_key():
            flash("Musisz zmienić domyślne hasło oraz ustawić klucz GPG, aby kontynuować.", "warning")
            return redirect(url_for('settings.index'))
        return f(*args, **kwargs)
    return decorated_function
