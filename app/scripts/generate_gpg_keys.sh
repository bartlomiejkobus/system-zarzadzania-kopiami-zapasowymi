#!/bin/bash
set -euo pipefail

export GNUPGHOME="./tmp_gnupg"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

cat > key.cfg <<EOF
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: Backup System Key
Name-Email: backup@local
Expire-Date: 0
%commit
EOF

echo "[*] Generowanie pary kluczy GPG dla systemu zarządzania kopiami zapasowymi"
gpg --batch --gen-key key.cfg
rm key.cfg

KEYID=$(gpg --list-keys --with-colons backup@local | awk -F: '/^pub/ {print $5}')

mkdir -p keys
chmod 700 keys

gpg --armor --export "$KEYID" > keys/public.key
gpg --armor --export-secret-keys "$KEYID" > keys/private.key
chmod 600 keys/*

rm -rf "$GNUPGHOME"


echo "[+] Klucze wygenerowane:"
echo "    keys/public.key  -> wklej ten klucz do aplikacji"
echo "    keys/private.key -> ZACHOWAJ TYLKO DLA ADMINISTRATORA"
