from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, login_required, logout_user, current_user
from app.models.settings import Settings
from app.utils import log_event
from flask_mail import Message
from app.utils import generate_code, get_client_info
from app.db import db


auth_bp = Blueprint('auth', __name__, template_folder='templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ip, ua = get_client_info()

        user = Settings.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash("Nieprawidłowa nazwa użytkownika lub hasło", "danger")
            log_event(
                f"Nieudana próba logowania dla '{username}' z adresu IP `{ip}`, Aplikacja kliencka: `{ua}`",
                type="błąd",
            )
            return render_template('login.html')

        if not user.is_2fa_enabled:
            login_user(user)
            flash("Zalogowano pomyślnie", "success")
            log_event(
                f"Użytkownik '{username}' zalogował się z adresu IP `{ip}`, Aplikacja kliencka: `{ua}`",
                type="logowanie"
            )
            return redirect(url_for('dashboard.index'))

        code = generate_code()
        session['2fa_user_id'] = user.id
        session['2fa_code'] = code
        try:
            subject="Kod weryfikacji dwuetapowej"
            body=f"Twój kod weryfikacji dwuetapowej: {code}"
            from app.tasks_celery import send_email
            send_email.delay(subject, body)
            flash("Kod weryfikacyjny został wysłany na Twój adres e-mail.", "info")
        except Exception as e:
            flash(f"Błąd wysyłki e-mail: {e}", "danger")
            session.pop('2fa_user_id', None)
            session.pop('2fa_code', None)
            return render_template('login.html')

        return redirect(url_for('auth.two_factor'))

    return render_template('login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    username = current_user.username
    logout_user()
    flash("Wylogowano pomyślnie", "info")
    log_event(f"Użytkownik '{username}' wylogował się", type="logowanie")
    return redirect(url_for('auth.login'))



@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    user = Settings.query.first()
    if not user or not user.email_address:
        flash("Brak skonfigurowanego adresu e-mail, reset hasła niemożliwy.", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        stored_code = session.get('reset_code')

        if not stored_code:
            flash("Brak kodu resetu, odśwież stronę aby wysłać nowy kod.", "warning")
            return redirect(url_for('auth.reset_password'))

        if code != stored_code:
            flash("Niepoprawny kod resetu.", "danger")
            return redirect(url_for('auth.reset_password'))

        if new_password != confirm_password:
            flash("Hasła nie są zgodne.", "danger")
            return redirect(url_for('auth.reset_password'))

        if len(new_password) < 8:
            flash("Nowe hasło musi mieć co najmniej 8 znaków.", "warning")
            return redirect(url_for('auth.reset_password'))

        user.set_password(new_password)
        db.session.commit()
        session.pop('reset_code', None)
        flash("Hasło zostało zmienione. Zaloguj się ponownie.", "success")
        return redirect(url_for('auth.login'))

    if 'reset_code' not in session:
        try:
            code = generate_code()
            session['reset_code'] = code
            subject="Kod resetu hasła"
            body=f"Twój kod resetu hasła: {code}"
            from app.tasks_celery import send_email
            send_email.delay(subject, body)
            flash(f"Kod resetu został wysłany. Sprawdź skrzynkę.", "info")
        except Exception as e:
            flash(f"Błąd wysyłki e-mail: {e}", "danger")
            session.pop('reset_code', None)


    return render_template('reset_password.html')



@auth_bp.route('/two-factor', methods=['GET', 'POST'])
def two_factor():
    if '2fa_user_id' not in session or '2fa_code' not in session:
        flash("Brak oczekującej weryfikacji dwuetapowej. Zaloguj się ponownie.", "warning")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        user_id = session['2fa_user_id']
        user = Settings.query.get(user_id)
        if not user:
            flash("Nieprawidłowy użytkownik.", "danger")
            session.pop('2fa_user_id', None)
            session.pop('2fa_code', None)
            return redirect(url_for('auth.login'))

        if code != session['2fa_code']:
            flash("Niepoprawny kod weryfikacyjny.", "danger")
            return render_template('two_factor.html')

        login_user(user)
        flash("Zalogowano pomyślnie", "success")
        log_event(f"Użytkownik '{user.username}' zalogował się z użyciem weryfikacji dwuetapowej.", type="logowanie")
        session.pop('2fa_user_id', None)
        session.pop('2fa_code', None)
        return redirect(url_for('dashboard.index'))

    return render_template('two_factor.html')