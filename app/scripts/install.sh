#!/usr/bin/env bash

set -euo pipefail

# Rejestracja do systemowego dziennika zdarzeń
log() {
    local level="$1"           # INFO, WARN, ERROR
    local msg="$2"             # wiadomość do dziennika zdarzeń
    local src="${3:-unknown}"  # opcjonalny identyfikator źródła, np. trigger, installer, helper

    logger -t backup_system "[$level][$src] $msg"
}

# Informacja dla użytkownika (polski)
echo "=== Rozpoczęcie instalacji: $(date -u +'%F %T UTC') ==="

# Rejestr techniczny (angielski)
log "INFO" "Installer started at $(date -u +'%F %T UTC')" "install"

# ---------------------------
# ZMIENNE MIEJSCOWE (zamieniane przez aplikację)
# ---------------------------
COMMAND_SSH_PUB_KEY='__COMMAND_SSH_PUB_KEY__'   # klucz publiczny SSH centralnego serwera do komend
RSYNC_SSH_PUB_KEY='__RSYNC_SSH_PUB_KEY__'   # klucz publiczny SSH centralnego serwera do rsync
ADMIN_GPG_PUB='__GPG_PUB_KEY__'         # klucz publiczny GPG administratora
# ---------------------------

BACKUP_USER="backup_user"
BACKUP_HOME="/home/${BACKUP_USER}"
SSH_DIR="${BACKUP_HOME}/.ssh"
AUTHORIZED_KEYS="${SSH_DIR}/authorized_keys"

SCRIPTS_DIR="/srv/backup_scripts"
FILES_DIR="/srv/backup_files"

EXECUTOR="/usr/local/sbin/run_backup.sh"
ADD_TASK_HELPER="/usr/local/sbin/add_task.sh"
DEL_TASK_HELPER="/usr/local/sbin/delete_task.sh"
UNINSTALL_HELPER="/usr/local/sbin/uninstall.sh"
TRIGGER="/usr/local/bin/trigger.sh"
CHECK_HELPER="/usr/local/sbin/check_install.sh"
INSTALL_MARKER="/etc/backup_installed"


SUDOERS_FILE="/etc/sudoers.d/backup_system"


# Sprawdzenie, czy skrypt uruchomiono jako root
if [[ $EUID -ne 0 ]]; then
    echo "[BŁĄD] Instalator musi być uruchomiony jako root"
    log "ERROR" "installer must be run as root (EUID=$EUID)" "install"
    exit 1
fi

# Wykrycie menedżera pakietów i instalacja GnuPG, jeśli nie jest zainstalowane
install_gnupg_if_needed() {
  if command -v gpg >/dev/null 2>&1; then
    echo "[INFO] gpg jest już zainstalowany"
    log "INFO" "gpg already installed" "install"
    return 0
  fi

  echo "[INFO] gpg nie znaleziony, próba instalacji..."
  log "INFO" "gpg not found, attempting install" "install"

  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y >/dev/null 2>&1 || true
    apt-get install -y gnupg >/dev/null 2>&1
  elif command -v yum >/dev/null 2>&1; then
    yum install -y gnupg >/dev/null 2>&1
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y gnupg >/dev/null 2>&1
  else
    echo "[BŁĄD] Nie znaleziono obsługiwanego menedżera pakietów. Zainstaluj gpg ręcznie."
    log "ERROR" "no supported package manager to install gpg" "install"
    exit 1
  fi

  echo "[INFO] gpg został zainstalowany"
  log "INFO" "gpg installed" "install"
}


# Tworzenie użytkownika kopii zapasowej, jeśli nie istnieje
if ! id -u "$BACKUP_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$BACKUP_USER"
  echo "[INFO] użytkownik $BACKUP_USER został utworzony"
  log "INFO" "user $BACKUP_USER created" "install"
else
  echo "[INFO] użytkownik $BACKUP_USER już istnieje"
  log "INFO" "user $BACKUP_USER exists - skipping useradd" "install"
fi


# Tworzenie katalogów i ustawienie bezpiecznych uprawnień
mkdir -p "$SSH_DIR" "$SCRIPTS_DIR" "$FILES_DIR"

chown root:root "$SCRIPTS_DIR" "$FILES_DIR"
chmod 750 "$SCRIPTS_DIR" "$FILES_DIR"

chown "$BACKUP_USER:$BACKUP_USER" "$SSH_DIR"
chmod 700 "$SSH_DIR"

touch "$AUTHORIZED_KEYS"
chown "$BACKUP_USER:$BACKUP_USER" "$AUTHORIZED_KEYS"
chmod 600 "$AUTHORIZED_KEYS"

echo "[INFO] utworzono katalogi i ustawiono uprawnienia"
log "INFO" "created directories and set permissions" "install"


# Instalacja wyzwalacza – plik wykonywany podczas połączenia SSH w celu wymuszenia określonego polecenia

cat > "$TRIGGER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Trigger dla SSH - wymuszony plik wykonywany zdalnie, obsługuje dozwolone komendy


# Rejestracja do systemowego dziennika zdarzeń
log() {
    local level="$1"           # INFO, WARN, ERROR
    local msg="$2"             # wiadomość do dziennika zdarzeń
    local src="${3:-unknown}"  # opcjonalny identyfikator źródła, np. trigger, installer, helper

    logger -t backup_system "[$level][$src] $msg"
}

# Funkcja blokująca dostęp do niedozwolonych operacji
deny() {
  echo "Dostęp zabroniony"
  log "DENIED" "Attempted command: ${SSH_ORIGINAL_COMMAND:-}" "trigger"
  exit 1
}

# Przypisanie wszystkich argumentów do zmiennej CMD (jeśli są dostępne)
if [ -z "${SSH_ORIGINAL_COMMAND:-}" ] && [ $# -gt 0 ]; then
    CMD="$*" 
fi

# Usuwanie zbędnych znaków białych z początku i końca
CMD="$(echo "${SSH_ORIGINAL_COMMAND:-$CMD}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

# Blokowanie niebezpiecznych znaków (np. ; & | < >)
if [[ "$CMD" =~ [\;\&\|\<\>] ]]; then
  deny
fi

# Dozwolone komendy:

# check - sprawdzenie stanu instalacji
if [[ "$CMD" == "check" ]]; then
  log "INFO" "Allowed: check" "trigger"
  echo "Sprawdzanie stanu instalacji..."
  exec /usr/bin/sudo /usr/local/sbin/check_install.sh
fi

# run_backup <task> - uruchamianie zadania kopii zapasowej
if [[ "$CMD" =~ ^run_backup[[:space:]]+([A-Za-z0-9][A-Za-z0-9_-]*)$ ]]; then
  TASK="${BASH_REMATCH[1]}"
  log "INFO" "Allowed: run_backup task=$TASK" "trigger"
  exec /usr/bin/sudo /usr/local/sbin/run_backup.sh "$TASK"
fi

# add_task <task> - dodawanie zadania kopii zapasowej
if [[ "$CMD" =~ ^add_task[[:space:]]+([A-Za-z0-9][A-Za-z0-9_-]*)$ ]]; then
  TASK="${BASH_REMATCH[1]}"
  log "INFO" "Allowed: add_task task=$TASK" "trigger"
  echo "Dodawanie zadania: $TASK"
  exec /usr/bin/sudo /usr/local/sbin/add_task.sh "$TASK"
fi

# delete_task <task> - usuwanie zadania kopii zapasowej
if [[ "$CMD" =~ ^delete_task[[:space:]]+([A-Za-z0-9][A-Za-z0-9_-]*)$ ]]; then
  TASK="${BASH_REMATCH[1]}"
  log "INFO" "Allowed: delete_task task=$TASK" "trigger"
  echo "Usuwanie zadania: $TASK"
  exec /usr/bin/sudo /usr/local/sbin/delete_task.sh "$TASK"
fi

# uninstall - odinstalowywanie systemu kopii zapasowych
if [[ "$CMD" == "uninstall" ]]; then
  log "INFO" "Allowed: uninstall" "trigger"
  echo "Odinstalowywanie systemu kopii zapasowych..."
  /usr/bin/sudo /usr/local/sbin/uninstall.sh < /dev/null 2>&1 &
  exit 0
fi

# Wszystko inne
log "ERROR" "Unauthorized command: $CMD" "trigger"
deny
EOF

chmod 755 "$TRIGGER"
chown root:root "$TRIGGER"
echo "[INFO] wyzwalacz zainstalowany: $TRIGGER"
log "INFO" "installed trigger $TRIGGER" "install"

#  Utworzenie wpisu w authorized_keys z wymuszonym użyciem wyzwalacza
echo "command=\"$TRIGGER\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $COMMAND_SSH_PUB_KEY" > "$AUTHORIZED_KEYS"
echo "command=\"/usr/bin/rrsync /srv/backup_files\",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding $RSYNC_SSH_PUB_KEY" >> "$AUTHORIZED_KEYS"

chown "$BACKUP_USER:$BACKUP_USER" "$AUTHORIZED_KEYS"
chmod 600 "$AUTHORIZED_KEYS"

echo "[INFO] zapisano authorized_keys z wymuszonym poleceniem"
log "INFO" "wrote authorized_keys with forced command for trigger $TRIGGER" "install"

# Instalacja skryptu run_backup.sh (wykonawca skryptu kopii zapasowej danego zadania)
cat > "$EXECUTOR" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Rejestracja do systemowego dziennika zdarzeń
log() {
    local level="$1"           # INFO, WARN, ERROR
    local msg="$2"             # wiadomość do dziennika zdarzeń
    local src="${3:-unknown}"  # opcjonalny identyfikator źródła, np. trigger, installer, helper

    logger -t backup_system "[$level][$src] $msg"
}

log "INFO" "run_backup invoked TASK=${1:-}" "run_backup"

if [ $# -ne 1 ]; then
    echo "Użycie: $0 <task>" >&2
    log "ERROR" "invalid arguments" "run_backup"
    exit 2
fi

TASK="$1"

# Walidacja nazwy zadania
if ! [[ "$TASK" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
    log "ERROR" "invalid task name '$TASK'" "run_backup"
    echo "Niepoprawna nazwa zadania: $TASK" >&2
    exit 3
fi

SCRIPTS_DIR="/srv/backup_scripts"
FILES_DIR="/srv/backup_files"
WORK_BASE="/srv/backup_tmp"
TASK_DIR="${WORK_BASE}/${TASK}"
OUT_DIR="${TASK_DIR}/output"
SCRIPT="${SCRIPTS_DIR}/${TASK}.sh"

if [ ! -x "$SCRIPT" ]; then
    echo "Skrypt zadania nie istnieje lub nie jest wykonywalny: $SCRIPT" >&2
    log "ERROR" "script not found or not executable: $SCRIPT" "run_backup"
    exit 4
fi

# Czyszczenie starego katalogu roboczego
rm -rf "$TASK_DIR"
mkdir -p "$OUT_DIR"

log "INFO" "Executing task script: $SCRIPT (output=$OUT_DIR)" "run_backup"

# Uruchomienie zadania — bez argumentów i bez zmiennych środowiskowych
"$SCRIPT"

# Sprawdzenie, czy skrypt wygenerował dane wyjściowe
if ! find "$OUT_DIR" -mindepth 1 | read -r; then
    log "ERROR" "no output from task $TASK" "run_backup"
    echo "Brak danych wyjściowych z zadania: $TASK" >&2
    rm -rf "$TASK_DIR"
    exit 5
fi

# Tworzenie archiwum tar
timestamp=$(date +"%Y%m%d%H%M%S")
TAR_PATH="${TASK_DIR}/${TASK}_${timestamp}.tar.gz"
tar -czf "$TAR_PATH" -C "$OUT_DIR" .

# Ustawienie odbiorca GPG
RECIPIENT=$(gpg --with-colons --list-keys 2>/dev/null | awk -F: '/^pub:/ {print $5; exit}')
if [ -z "$RECIPIENT" ]; then
    log "ERROR" "no GPG recipient found" "run_backup"
    echo "Nie znaleziono odbiorcy GPG" >&2
    rm -rf "$TASK_DIR"
    exit 7
fi

ENC="${TAR_PATH}.gpg"
log "INFO" "Encrypting -> $ENC (recipient $RECIPIENT)" "run_backup"
gpg --batch --yes --trust-model always --recipient "$RECIPIENT" --output "$ENC" --encrypt "$TAR_PATH"

# Przeniesienie plików do katalogu docelowego
FINAL="${FILES_DIR}/$(basename "$ENC")"
mv -f "$ENC" "$FINAL"
chmod 600 "$FINAL"
chown -R backup_user:backup_user "$FILES_DIR"

# Czyszczenie katalogu roboczego
rm -rf "$TASK_DIR"

log "INFO" "Encrypted archive ready: $FINAL" "run_backup"
echo $(basename "$ENC")
exit 0
EOF

chmod 700 "$EXECUTOR"
chown root:root "$EXECUTOR"

echo "[INFO] Zainstalowano wykonawcę: $EXECUTOR"
log "INFO" "installed executor $EXECUTOR" "install"

# instalacja skryptu pomocniczego add_task.sh - tworzy bezpieczny szablon zadania
cat > "$ADD_TASK_HELPER" <<'EOF'
#!/usr/bin/env bash
# add_task.sh <task>

# Tworzy bezpieczny szablon skryptu zadania kopii zapasowej dla run_backup.sh
set -euo pipefail

# Rejestracja do systemowego dziennika zdarzeń
log() {
    local level="$1"           # INFO, WARN, ERROR
    local msg="$2"             # wiadomość do dziennika zdarzeń
    local src="${3:-unknown}"  # opcjonalny identyfikator źródła, np. trigger, installer, helper

    logger -t backup_system "[$level][$src] $msg"
}

SCRIPTS_DIR="/srv/backup_scripts"

if [[ $# -ne 1 ]]; then
    echo "Użycie: $0 <task>" >&2
    log "ERROR" "invalid arguments" "add_task"
    exit 1
fi

TASK="$1"
log "INFO" "add_task invoked for task=$TASK" "add_task"

# Walidacja nazwy zadania
if ! [[ "$TASK" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
    echo "Nieprawidłowa nazwa zadania" >&2
    log "ERROR" "invalid task name '$TASK'" "add_task"
    exit 2
fi

# Tworzenie katalogu ze skryptami jeśli nie istnieje
mkdir -p "$SCRIPTS_DIR"
chmod 750 "$SCRIPTS_DIR"
chown root:root "$SCRIPTS_DIR"

OUT="${SCRIPTS_DIR}/${TASK}.sh"

if [[ -e "$OUT" ]]; then
    echo "Skrypt zadania już istnieje: $OUT" >&2
    log "ERROR" "task script already exists: $OUT" "add_task"
    exit 3
fi

# Tworzenie skryptu zadania z bezpiecznym szablonem
cat > "$OUT" <<TASK_EOF
#!/usr/bin/env bash
# Automatycznie wygenerowane zadanie kopii zapasowej: ${TASK}
# Edytuj tylko sekcję BACKUP COMMAND SECTION poniżej
set -euo pipefail

# Nazwa zadania:
TASK="${TASK}"

# Lokalizacja wyjściowa zadania
OUT_DIR="/srv/backup_tmp/${TASK}/output"

# Utwórz katalog wyjściowy
mkdir -p "\$OUT_DIR"

# ==================== BACKUP COMMAND SECTION ====================
# Dodaj tutaj swoje polecenia backupu, np.:
#   mysqldump mydb > "\$OUT_DIR/db.sql"
#   cp -r /var/www/html "\$OUT_DIR/www"
#
# !! WAŻNE !!
# Wszystkie pliki wyjściowe MUSZĄ być zapisywane wyłącznie w:
#   \$OUT_DIR
#
# Jeśli pozostawisz tą sekcję niezmienioną, zadanie zakończy się błędem.
echo "BŁĄD: Polecenia zadania kopii zapasowej nie zostały skonfigurowane dla zadania: $TASK" >&2
exit 99
# ================================================================
TASK_EOF

# Ustawienie właściciela i uprawnień
chmod 750 "$OUT"
chown root:root "$OUT"

log "INFO" "Created task script $OUT" "add_task"
echo "OK: task '$TASK' utworzony w $OUT"
EOF

chmod 700 "$ADD_TASK_HELPER"
chown root:root "$ADD_TASK_HELPER"

echo "[INFO] zainstalowano skrypt pomocniczy add_task: $ADD_TASK_HELPER"
log "INFO" "installed add_task helper $ADD_TASK_HELPER" "install"

# instalacja skryptu pomocniczego delete_task.sh  - usuwa istniejące zadanie backupu
cat > "$DEL_TASK_HELPER" <<'EOF'
#!/usr/bin/env bash
# delete_task.sh <task>
set -euo pipefail

# Rejestracja do systemowego dziennika zdarzeń
log() {
    local level="$1"           # INFO, WARN, ERROR
    local msg="$2"             # wiadomość do dziennika zdarzeń
    local src="${3:-unknown}"  # opcjonalny identyfikator źródła, np. trigger, installer, helper

    logger -t backup_system "[$level][$src] $msg"
}

SCRIPTS_DIR="/srv/backup_scripts"
TMP_BASE="/srv/backup_tmp"

if [[ $# -ne 1 ]]; then
    echo "Użycie: $0 <task>" >&2
    log "ERROR" "invalid arguments" "delete_task"
    exit 1
fi

TASK="$1"
FILE="${SCRIPTS_DIR}/${TASK}.sh"
TMP_PATH="${TMP_BASE}/${TASK}"

log "INFO" "delete_task invoked for task=$TASK" "delete_task"

# Walidacja nazwy zadania
if ! [[ "$TASK" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
    echo "Invalid task name" >&2
    log "ERROR" "nieprawidłowa nazwa zadania '$TASK'" "delete_task"
    exit 2
fi

# Sprawdzenie czy plik skryptu istnieje
if [[ ! -f "$FILE" ]]; then
    echo "Nie znaleziono skryptu zadania: $FILE" >&2
    log "ERROR" "script not found: $FILE" "delete_task"
    exit 3
fi

# Usuwanie skrypt zadania
rm -f "$FILE"
log "INFO" "Removed script $FILE" "delete_task"


# Usuwanie pozostałego katalogu tymczasowego (jeśli istnieje)
if [[ -d "$TMP_PATH" ]]; then
    rm -rf "$TMP_PATH"
    log "INFO" "Removed temp dir $TMP_PATH" "delete_task"
fi

log "INFO" "Deleted task $TASK (file + tmp)" "delete_task"
echo "OK"
EOF

chmod 700 "$DEL_TASK_HELPER"
chown root:root "$DEL_TASK_HELPER"

echo "[INFO] zainstalowano skrypt pomocniczy delete_task: $DEL_TASK_HELPER"
log "INFO" "installed delete_task helper $DEL_TASK_HELPER" "install"

# instalacja skryptu pomocniczego uninstall - odinstalowuje system kopii zapasowych
cat > "$UNINSTALL_HELPER" <<'EOF'
#!/usr/bin/env bash
# uninstall.sh - bezpieczne usunięcie systemu kopii zapasowych
set -euo pipefail

BACKUP_USER="backup_user"
BACKUP_HOME="/home/${BACKUP_USER}"

SCRIPTS_DIR="/srv/backup_scripts"
FILES_DIR="/srv/backup_files"
TMP_DIR="/srv/backup_tmp"

EXECUTOR="/usr/local/sbin/run_backup.sh"
ADD_TASK_HELPER="/usr/local/sbin/add_task.sh"
DEL_TASK_HELPER="/usr/local/sbin/delete_task.sh"
CHECK_HELPER="/usr/local/sbin/check_install.sh"
UNINSTALL_HELPER="/usr/local/sbin/uninstall.sh"
TRIGGER="/usr/local/bin/trigger.sh"

SUDOERS_FILE="/etc/sudoers.d/backup_system"
INSTALL_MARKER="/etc/backup_installed"


# Rejestracja do systemowego dziennika zdarzeń
log() {
    local level="$1"           # INFO, WARN, ERROR
    local msg="$2"             # wiadomość do dziennika zdarzeń
    local src="${3:-unknown}"  # opcjonalny identyfikator źródła, np. trigger, installer, helper

    logger -t backup_system "[$level][$src] $msg"
}

log "INFO" "=== UNINSTALL START ===" "uninstall"

# Usuwanie wpisu w sudoers
if rm -f "$SUDOERS_FILE" 2>/dev/null; then
    log "INFO" "Removed sudoers file $SUDOERS_FILE" "uninstall"
else
    log "WARN" "Failed to remove $SUDOERS_FILE" "uninstall"
fi

# Usuwanie skryptów pomocniczych i plików wykonywalnych
if rm -f "$EXECUTOR" "$ADD_TASK_HELPER" "$DEL_TASK_HELPER" "$CHECK_HELPER" "$UNINSTALL_HELPER" "$TRIGGER" 2>/dev/null; then
    log "INFO" "Removed helpers and executables" "uninstall"
else
    log "WARN" "Failed to remove helpers or executables" "uninstall"
fi

# Usuwanie skryptów, pliki kopii zapasowych i katalogi tymczasowe
if rm -rf "$SCRIPTS_DIR" "$FILES_DIR" "$TMP_DIR" 2>/dev/null; then
    log "INFO" "Removed scripts, backup files, and tmp directories" "uninstall"
else
    log "WARN" "Failed to remove directories" "uninstall"
fi

# Usuwanie znacznika instalacji
if rm -f "$INSTALL_MARKER" 2>/dev/null; then
    log "INFO" "Removed installation marker $INSTALL_MARKER" "uninstall"
else
    log "WARN" "Failed to remove installation marker" "uninstall"
fi

# Usuwanie użytkownika kopii zapasowych i jego katalogu domowego
if id "$BACKUP_USER" >/dev/null 2>&1; then
    if userdel -r -f "$BACKUP_USER" 2>/dev/null; then
        log "INFO" "Removed user $BACKUP_USER" "uninstall"
    else
        log "WARN" "Failed to remove user $BACKUP_USER" "uninstall"
    fi
else
    log "INFO" "User $BACKUP_USER does not exist" "uninstall"
fi

# Sprawdzenie, że katalog .ssh został usunięty
if rm -rf "${BACKUP_HOME}/.ssh" 2>/dev/null; then
    log "INFO" "Removed SSH directory ${BACKUP_HOME}/.ssh" "uninstall"
else
    log "WARN" "Failed to remove SSH directory ${BACKUP_HOME}/.ssh" "uninstall"
fi

log "INFO" "=== UNINSTALL COMPLETE ===" "uninstall"

exit 0
EOF

chmod 700 "$UNINSTALL_HELPER"
chown root:root "$UNINSTALL_HELPER"

echo "[INFO] zainstalowano skrypt pomocniczy deinstalacji: $UNINSTALL_HELPER"
log "INFO" "installed uninstall helper $UNINSTALL_HELPER" "install"

# skrypt pomocniczy tworzący znacznik instalacji
cat > "$CHECK_HELPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INSTALL_MARKER="/etc/backup_installed"

if [[ -f "$INSTALL_MARKER" ]]; then
    echo "OK"
    exit 0
else
    echo "NOT_INSTALLED"
    exit 1
fi
EOF

chmod 700 "$CHECK_HELPER"
chown root:root "$CHECK_HELPER"

echo "[INFO] zainstalowano skrypt pomocniczy sprawdzający instalację: $CHECK_HELPER"
log "INFO" "installed check helper $CHECK_HELPER" "install"

# Sprawdzenie, czy sudo jest zainstalowane
if ! command -v sudo >/dev/null 2>&1; then
    echo "[INFO] sudo nie jest zainstalowane — instalowanie..."
    log "INFO" "sudo not installed — installing" "install"

    if command -v apt >/dev/null 2>&1; then
        apt update && apt install -y sudo
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y sudo
    elif command -v yum >/dev/null 2>&1; then
        yum install -y sudo
    elif command -v apk >/dev/null 2>&1; then
        apk add --no-cache sudo
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Sy --noconfirm sudo
    else
        echo "[ERROR] Nie udało się zainstalować sudo — nieobsługiwany menedżer pakietów." >&2
        log "ERROR" "Unable to install sudo — unsupported package manager" "install"
        exit 1
    fi

    echo "[INFO] sudo zainstalowane."
    log "INFO" "sudo installed" "install"

fi

# Sprawdzenie czy /etc/sudoers.d istnieje
if [ ! -d /etc/sudoers.d ]; then
    echo "[INFO] Tworzenie katalogu /etc/sudoers.d"
    log "INFO" "Creating /etc/sudoers.d" "install"

    mkdir -p /etc/sudoers.d
    chmod 755 /etc/sudoers.d
fi

# Zapis do sudoers: zezwolenie użytkownikowi kopii zapasowych na uruchamianie wybranych skryptów pomocnicznych jako root bez podawania hasła
cat > "$SUDOERS_FILE" <<EOF
# allow backup user to run helpers as root without password
${BACKUP_USER} ALL=(root) NOPASSWD: ${EXECUTOR}
${BACKUP_USER} ALL=(root) NOPASSWD: ${ADD_TASK_HELPER}
${BACKUP_USER} ALL=(root) NOPASSWD: ${DEL_TASK_HELPER}
${BACKUP_USER} ALL=(root) NOPASSWD: ${UNINSTALL_HELPER}
${BACKUP_USER} ALL=(root) NOPASSWD: ${CHECK_HELPER}
EOF

chmod 440 "$SUDOERS_FILE"
log "INFO" "wrote sudoers entries for $BACKUP_USER in $SUDOERS_FILE" "install"


# Walidacja wpisu do sudoers
if ! visudo -cf "$SUDOERS_FILE"; then
    echo "[ERROR] Błąd składni w pliku $SUDOERS_FILE — usuwanie nieprawidłowego pliku." >&2
    log "ERROR" "Syntax error in $SUDOERS_FILE — removing invalid file" "install"
    rm -f "$SUDOERS_FILE"
    exit 1
fi

echo "[INFO] Zapisano plik sudoers: $SUDOERS_FILE"
log "INFO" "wrote sudoers file: $SUDOERS_FILE" "install"


# Sprawdzenie, czy rsync jest zainstalowane
if ! command -v rsync >/dev/null 2>&1; then
    echo "[INFO] rsync nie jest zainstalowane — instalowanie..."
    log "INFO" "rsync not installed — installing" "install"

    if command -v apt >/dev/null 2>&1; then
        apt update && apt install -y rsync
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y rsync
    elif command -v yum >/dev/null 2>&1; then
        yum install -y rsync
    elif command -v apk >/dev/null 2>&1; then
        apk add --no-cache rsync
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Sy --noconfirm rsync
    else
        echo "[ERROR] Nie udało się zainstalować rsync — nieobsługiwany menedżer pakietów." >&2
        log "ERROR" "Unable to install rsync — unsupported package manager" "install"
        exit 1
    fi

    echo "[INFO] rsync zainstalowane."
    log "INFO" "rsync installed" "install"
fi

# Sprawdzenie, czy rrsync znajduje się w /usr/bin/rrsync
if [ ! -f /usr/bin/rrsync ]; then
    echo "[INFO] rrsync nie znajduje się w /usr/bin/rrsync — próba utworzenia..."
    log "INFO" "rrsync missing — attempting to create" "install"

    # Typowe lokalizacje rrsync (z pakietu rsync)
    POSSIBLE_RRSYNC_LOCATIONS=(
        "/usr/share/doc/rsync/support/rrsync"
        "/usr/share/rsync/support/rrsync"
        "/usr/lib/rsync/support/rrsync"
        "/usr/share/examples/rsync/rrsync"
    )

    FOUND_RRSYNC=""

    for loc in "${POSSIBLE_RRSYNC_LOCATIONS[@]}"; do
        if [ -f "$loc" ]; then
            FOUND_RRSYNC="$loc"
            break
        fi
    done

    if [ -n "$FOUND_RRSYNC" ]; then
        cp "$FOUND_RRSYNC" /usr/bin/rrsync
        chmod +x /usr/bin/rrsync
        echo "[INFO] rrsync skopiowany do /usr/bin/rrsync i oznaczony jako wykonywalny."
        log "INFO" "rrsync installed to /usr/bin/rrsync" "install"
    else
        echo "[WARN] Nie znaleziono źródła rrsync w standardowych lokalizacjach."
        echo "[WARN] Możliwe, że pakiet rsync nie zawiera rrsync w tej dystrybucji."
        log "WARN" "rrsync source not found" "install"
    fi
else
    echo "[INFO] rrsync jest już obecny w /usr/bin/rrsync."
    log "INFO" "rrsync already exists" "install"
fi


# Sprawdzenie czy gpg jest zainstalowane i import klucza publicznego administratora
install_gnupg_if_needed

if [[ -z "${ADMIN_GPG_PUB:-}" ]]; then
  echo "[WARN] Nie podano publicznego klucza GPG. System został zainstalowany, ale szyfrowanie nie będzie działać dopóki klucz nie zostanie zaimportowany."
  log "WARN" "No GPG public key provided. Encryption will not work until key is imported." "install"
else
  TMP_PUB="/tmp/admin_pub_$$.asc"
  echo "$ADMIN_GPG_PUB" > "$TMP_PUB"
  chmod 600 "$TMP_PUB"

  if gpg --import "$TMP_PUB" >/dev/null 2>&1; then
     echo "[INFO] Zaimportowano publiczny klucz GPG administratora"
    log "INFO" "imported admin GPG public key" "install"
  else
      echo "[ERROR] Nie udało się zaimportować publicznego klucza GPG administratora."
      log "ERROR" "Failed to import admin GPG public key" "install"
      rm -f "$TMP_PUB"
      exit 1
  fi

  rm -f "$TMP_PUB"
fi

echo "BACKUP_SYSTEM=1" > "$INSTALL_MARKER"
echo "INSTALL_DATE=$(date -u)" >> "$INSTALL_MARKER"
chmod 600 "$INSTALL_MARKER"

echo "[INFO] Znacznik poprawnej instalacji zapisany w $INSTALL_MARKER"
log "INFO" "installation marker written to $INSTALL_MARKER" "install"


# Podsumowanie
log "INFO" "Instalacja zakończona: $(date -u +'%F %T UTC')" "install"

echo "=== Install finished: $(date -u +'%F %T UTC') ==="
echo "PODSUMOWANIE:"

log "INFO" "Backup user: $BACKUP_USER" "install"
echo " - Użytkownik kopii zapasowych: $BACKUP_USER"

log "INFO" "Trigger wrapper: $TRIGGER" "install"
echo " - Wyzwalacz: $TRIGGER"

log "INFO" "Helpers (run as root via sudo)" "install"
echo " - Skrypty pomocnicze:"

log "INFO" "Executor: $EXECUTOR" "install"
echo "    - Wykonawca: $EXECUTOR"

log "INFO" "Add task helper: $ADD_TASK_HELPER" "install"
echo "    - Dodawanie zadania: $ADD_TASK_HELPER"

log "INFO" "Delete task helper: $DEL_TASK_HELPER" "install"
echo "    - Usuwania zadania: $DEL_TASK_HELPER"

log "INFO" "Uninstall helper: $UNINSTALL_HELPER" "install"
echo "    - Odinstalowywanie: $UNINSTALL_HELPER"

log "INFO" "Check helper: $CHECK_HELPER" "install"
echo "    - Sprawdzanie instalacji: $CHECK_HELPER"

log "INFO" "Tasks directory: $SCRIPTS_DIR" "install"
echo " - Katalog z zadaniami: $SCRIPTS_DIR"
echo "    (umieść skrypty <zadanie>.sh tutaj, właściciel: root, chmod 750)"

log "INFO" "Backup files directory: $FILES_DIR" "install"
echo " - Katalog plików kopii zapasowych: $FILES_DIR"
echo "    (zaszyfrowane archiwa są przechowywane tutaj)"


exit 0