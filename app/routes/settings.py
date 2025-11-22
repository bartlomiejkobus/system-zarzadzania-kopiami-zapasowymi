from flask import Blueprint, render_template, request, session, current_app, url_for, flash, redirect
from flask_login import login_required, current_user, logout_user
from flask_mail import Message
from app.db import db
import os
from app.utils import generate_code

settings_bp = Blueprint('settings', __name__, template_folder='templates')


@settings_bp.route('/settings')
@login_required
def index():
    script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'generate_gpg_keys.sh')
    gpg_script_content = ""
    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            gpg_script_content = f.read()

    show_modal = session.pop('show_verification_modal', False)
    return render_template('settings.html', gpg_script_content=gpg_script_content, show_modal=show_modal)


@settings_bp.route('/settings/email', methods=['POST'])
@login_required
def send_verification_code():
    new_email = request.form.get('email', '').strip()

    if not new_email or '@' not in new_email:
        flash('Nieprawidłowy adres e-mail.', 'danger')
        return redirect(url_for('settings.index'))

    verification_code = generate_code()
    session['pending_email'] = new_email
    session['verification_code'] = verification_code
    session['show_verification_modal'] = True
    try:
        subject="Kod weryfikacyjny"
        body=f"Twój kod weryfikacyjny: {verification_code}"
        from app.tasks_celery import send_email
        send_email.delay(subject, body, recipient=new_email)
        flash(f'Kod weryfikacyjny został wysłany na adres: {new_email}', 'info')
    except Exception as e:
        flash(f'Błąd wysyłki e-maila: {e}', 'danger')

    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/verify-email', methods=['POST'])
@login_required
def verify_email_code():
    """Weryfikuje kod i zapisuje nowy adres e-mail użytkownika."""
    code = request.form.get('code', '').strip()
    stored_code = session.get('verification_code')
    pending_email = session.get('pending_email')

    if not stored_code or not pending_email:
        flash('Brak oczekującej weryfikacji e-maila.', 'warning')
        return redirect(url_for('settings.index'))

    if code == stored_code:
        current_user.email_address = pending_email
        db.session.commit()
        session.pop('pending_email', None)
        session.pop('verification_code', None)
        flash('Adres e-mail został potwierdzony i zapisany!', 'success')
    else:
        flash('Niepoprawny kod weryfikacyjny.', 'danger')

    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/email-notifications', methods=['POST'])
@login_required
def update_email_notifications():
    """Włącza lub wyłącza powiadomienia e-mail."""
    enabled = 'email_notifications' in request.form
    current_user.are_notifications_enabled = enabled
    db.session.commit()
    flash('Powiadomienia e-mail zostały ' + ('włączone.' if enabled else 'wyłączone.'), 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/2fa', methods=['POST'])
@login_required
def update_2fa():
    """Włącza lub wyłącza uwierzytelnienie dwuskładnikowe."""
    enabled = 'enable_2fa' in request.form
    current_user.is_2fa_enabled = enabled
    db.session.commit()
    flash('Uwierzytelnienie dwuskładnikowe zostało ' + ('włączone.' if enabled else 'wyłączone.'), 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/gpg-key', methods=['POST'])
@login_required
def update_gpg_key():
    """Zapisuje lub aktualizuje klucz publiczny GPG użytkownika."""
    gpg_key = request.form.get('gpg_key', '').strip()

    if not gpg_key:
        flash('Pole klucza GPG nie może być puste.', 'warning')
        return redirect(url_for('settings.index'))

    if not gpg_key.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"):
        flash('Wygląda na to, że to nie jest poprawny klucz GPG.', 'danger')
        return redirect(url_for('settings.index'))

    current_user.public_key_gpg = gpg_key
    db.session.commit()
    flash('Klucz publiczny GPG został zapisany.', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    """Zmiana hasła użytkownika z walidacją aktualności i siły."""
    current_password = request.form.get('current_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    default_password = current_app.config.get('DEFAULT_ADMIN_PASSWORD')
    if default_password and new_password == default_password:
        flash('Nie możesz ustawić hasła identycznego z domyślnym hasłem systemowym.', 'danger')
        return redirect(url_for('settings.index'))

    if not current_password or not new_password or not confirm_password:
        flash('Wszystkie pola są wymagane.', 'warning')
        return redirect(url_for('settings.index'))

    if not current_user.check_password(current_password):
        flash('Niepoprawne aktualne hasło.', 'danger')
        return redirect(url_for('settings.index'))

    if current_password == new_password:
        flash('Nowe hasło nie może być takie samo jak obecne.', 'warning')
        return redirect(url_for('settings.index'))

    if new_password != confirm_password:
        flash('Nowe hasła nie są zgodne.', 'danger')
        return redirect(url_for('settings.index'))

    if len(new_password) < 8:
        flash('Nowe hasło musi mieć co najmniej 8 znaków.', 'warning')
        return redirect(url_for('settings.index'))

    current_user.set_password(new_password)
    db.session.commit()

    logout_user()
    flash('Hasło zostało pomyślnie zmienione. Zaloguj się ponownie.', 'success')
    return redirect(url_for('auth.login'))


@settings_bp.route('/settings/change-username', methods=['POST'])
@login_required
def change_username():
    """Zmiana nazwy użytkownika z walidacją podstawową."""
    new_username = request.form.get('username', '').strip()

    if not new_username:
        flash('Pole nazwy użytkownika nie może być puste.', 'warning')
        return redirect(url_for('settings.index'))

    if new_username == current_user.username:
        flash('Nowa nazwa użytkownika musi różnić się od obecnej.', 'warning')
        return redirect(url_for('settings.index'))

    if not new_username.isalnum() and "_" not in new_username:
        flash('Nazwa użytkownika może zawierać tylko litery, cyfry i znak _.', 'danger')
        return redirect(url_for('settings.index'))

    if len(new_username) < 4 or len(new_username) > 20:
        flash('Nazwa użytkownika musi mieć od 4 do 20 znaków.', 'warning')
        return redirect(url_for('settings.index'))

    current_user.username = new_username
    db.session.commit()
    flash('Nazwa użytkownika została zmieniona. Zaloguj się ponownie.', 'success')
    logout_user()
    return redirect(url_for('auth.login'))