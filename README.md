# System Zarzadzania Kopiami Zapasowymi


## Opis
System jest częścią projektu inżynierskiego pod tytułem "Webowy system zdalnego zarządzania kopiami zapasowymi".

Aplikacja stanowi webowy system umożliwiający centralne i bezpieczne zarządzanie kopiami zapasowymi danych z serwerów w sieci lokalnej.
Umożliwia tworzenie oraz pobieranie kopii zapasowych plików, folderów i baz danych, automatyzując proces.

Dzięki centralnemu interfejsowi administrator może zdalnie:
- definiować serwery źródłowe,
- konfigurować zadania i harmonogramy backupów,
- uruchamiać kopie ręcznie lub automatycznie,
- zarządzać retencją,
- przeglądać historię operacji,
- otrzymywać powiadomienia o błędach.

System zapewnia bezpieczne przechowywanie danych po ich pobraniu na serwer centralny, a intuicyjny interfejs prowadzi użytkownika przez proces konfiguracji i zarządzania kopiami zapasowymi.

Składa się on z sześciu kontenerów uruchamianych za pomocą `docker-compose`:
- traefik – reverse proxy zapewniający obsługę HTTPS,
- mysql – baza danych przechowująca konfiguracje, informacje o serwerach, zadaniach backupów, metadane kopii oraz zdarzenia,
- web – aplikacja webowa (Flask) stanowiąca interfejs użytkownika,
- celery_worker – wykonuje zadania asynchroniczne (np. tworzenie kopii zapasowych),
- celery_beat – cyklicznie dodaje zadania dla workera,
- redis – broker i backend dla Celery, odpowiada za kolejkowanie i przetwarzanie zadań.


## Uruchomienie:

Najpierw należy utworzyć i uzupełnić plik konfiguracyjny `.env`:
``` bash
cp .env.example .env
```
Następnie uruchomić kontenery:
``` bash
docker-compose up -d --build
```

Po poprawnym uruchomieniu interfejs użytkownika jest dostępny pod adresami:
- `127.0.0.1`,
- `backup-manager.local`.

Adresy te można zmienić w pliku `docker-compose.yml`.