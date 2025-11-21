from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user, current_user
from app.models.settings import Settings
from app.utils import log_event

auth_bp = Blueprint('auth', __name__, template_folder='templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = Settings.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Zalogowano pomyślnie", "success")
            log_event(f"Użytkownik '{username}' zalogował się pomyślnie", type="logowanie")
            return redirect(url_for('dashboard.index'))
        else:
            flash("Nieprawidłowa nazwa użytkownika lub hasło", "danger")
            log_event(f"Nieudana próba logowania dla użytkownika '{username}'", type="błąd")
            
    return render_template('login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    flash("Wylogowano pomyślnie", "info")
    log_event(f"Użytkownik '{username}' wylogował się", type="logowanie")
    return redirect(url_for('auth.login'))
