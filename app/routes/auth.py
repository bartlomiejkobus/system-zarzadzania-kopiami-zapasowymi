from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user
from app.models.settings import Settings

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
            return redirect(url_for('dashboard.index'))
        else:
            flash("Nieprawidłowa nazwa użytkownika lub hasło", "danger")
            
    return render_template('login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash("Wylogowano pomyślnie", "info")
    return redirect(url_for('auth.login'))
