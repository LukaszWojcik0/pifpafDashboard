# Portainer Production Runbook

Ten runbook opisuje utrzymanie produkcji `pifpafDashboard` w obecnym modelu hostingu z `docker-compose.yml`.

## Kontrakt produkcyjny

Nie zmieniaj przypadkowo:

- usług: `vpn`, `scraper`, `web`, `cloudflared`
- kontenerów: `gluetun`, `arena-scraper`, `arena-web`, `cloudflare-tunnel`
- wolumenów Compose: `pifpaf-data`, `gluetun-data`
- montowania bazy: `pifpaf-data:/data`
- ścieżki bazy: `/data/app.db`
- zmiennej `DATABASE_PATH=/data/app.db`
- `network_mode: "service:vpn"` dla `scraper` i `web`
- portu hosta `${WEB_PORT:-8088}:3000/tcp` publikowanego przez `vpn`
- Cloudflare Tunnel: usługa `cloudflared`, `command: tunnel run`, `TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}`

## Lokalizacja zmiennych środowiskowych

W Portainerze:

1. `Environments`
2. wybierz środowisko produkcyjne
3. `Stacks`
4. otwórz stack aplikacji
5. sprawdź `Editor` albo `Environment variables`, zależnie od sposobu wdrożenia stacka

Zmienne używane przez stack:

- `WEB_PORT`
- `VPN_USER`
- `VPN_PASSWORD`
- `SCRAPE_INTERVAL_MINUTES`
- `NTFY_URL`
- `ALERT_ON_FIRST_RUN`
- `CLOUDFLARE_TUNNEL_TOKEN`
- `ADMIN_SETUP_TOKEN`

DO WERYFIKACJI W PORTAINERZE: czy stack jest wdrażany z Git, Web editor, czy uploadu Compose.

## Pierwsze wdrożenie

1. Przygotuj wartości zmiennych środowiskowych w Portainerze.
2. Upewnij się, że Compose zawiera wolumeny `pifpaf-data` i `gluetun-data`.
3. W Portainerze utwórz stack z `docker-compose.yml`.
4. Uruchom deployment z buildem obrazów `scraper` i `web`.
5. Poczekaj na start `vpn` / `gluetun`.
6. Sprawdź `arena-web`.
7. Sprawdź `arena-scraper`.
8. Otwórz dashboard przez adres Cloudflare albo port `${WEB_PORT:-8088}`.
9. Wejdź na `/api/health`.
10. Wejdź na `/api/ready`.

Pozytywne wyniki:

- `/api/health` zwraca `ok: true`
- `/api/ready` zwraca HTTP 200 po poprawnej migracji/inicjalizacji bazy
- dashboard ładuje stronę
- `arena-scraper` startuje scheduler

## Standardowa aktualizacja

1. Przeczytaj changelog albo listę zmian.
2. Jeżeli zmiany obejmują bazę, wykonaj backup według sekcji `Backup`.
3. W Portainerze otwórz stack.
4. Wykonaj redeploy/rebuild zgodnie z obecnym sposobem wdrażania.
5. Nie zmieniaj nazw usług, wolumenów, portów ani sieci.
6. Sprawdź logi.
7. Sprawdź `/api/health`.
8. Sprawdź `/api/ready`.
9. Otwórz dashboard.

## Aktualizacja bez zmian Compose

Jeżeli zmienia się tylko kod aplikacji:

1. Nie edytuj `docker-compose.yml`.
2. W Portainerze wykonaj rebuild/redeploy istniejącego stacka.
3. Sprawdź, czy `arena-web` i `arena-scraper` używają nowych obrazów.
4. Sprawdź health/readiness i logi.

PORTAINER: brak zmian konfiguracji. Wystarczy standardowy rebuild i redeploy istniejącego stacka.

## Aktualizacja ze zmianą Compose

Jeżeli zmiana Compose jest konieczna:

1. Przygotuj minimalny diff.
2. Nie zmieniaj nazw istniejących usług i wolumenów.
3. Zachowaj poprzednią wersję Compose.
4. Wykonaj backup bazy, jeżeli zmiana może dotknąć `web`, `scraper` albo wolumenu `pifpaf-data`.
5. W Portainerze zaktualizuj stack.
6. Sprawdź `docker compose config` poza produkcją lub w CI.
7. Wdróż.
8. Sprawdź health/readiness i logi.

Rollback Compose:

1. Wróć do poprzedniej wersji Compose.
2. Redeploy stacka.
3. Sprawdź `arena-web`, `arena-scraper`, `vpn`, `cloudflared`.

## Rebuild bez cache

W Portainerze:

1. Otwórz stack.
2. Wybierz opcję redeploy/update.
3. Jeżeli UI Portainera udostępnia opcję `Re-pull image and redeploy` albo `No cache`, zaznacz ją tylko dla wymuszonego czystego buildu.
4. Nie zmieniaj Compose.

DO WERYFIKACJI W PORTAINERZE: dokładna nazwa opcji zależy od wersji Portainera i sposobu wdrożenia stacka.

## Backup

Zatrzymaj usługi zapisujące do SQLite:

1. `scraper` / `arena-scraper`
2. `web` / `arena-web`

Użyj kontenera pomocniczego z aktualnego obrazu `scraper`, tym samym wolumenem zamontowanym jako `/data`, i komendą startową `sleep 3600`.

Komenda backupu:

```bash
python /app/backup_db.py --source /data/app.db --dest-dir /data/backups
```

Pozytywny wynik:

```text
Backup created: /data/backups/app-YYYYMMDD-HHMMSS.db
integrity_check: ok
```

Nie kopiuj aktywnego `app.db` zwykłym `cp`.

## Migracja

Pełna procedura jest w `PORTAINER_DATABASE_MIGRATION.md`.

Minimalna sekwencja:

```bash
python /app/check_db.py --database /data/backups/NAZWA_BACKUPU.db
python /app/migrate_db.py --database /data/app.db --dry-run
python /app/migrate_db.py --database /data/app.db
python /app/check_db.py --database /data/app.db --expect-schema-version 4
```

Nie uruchamiaj migracji bez backupu.

## Sprawdzenie logów

W Portainerze:

1. `Containers`
2. otwórz `arena-web`
3. `Logs`
4. otwórz `arena-scraper`
5. `Logs`
6. w razie problemów sprawdź też `gluetun` i `cloudflare-tunnel`

Szukaj:

- `schema version`
- `no such table`
- `foreign key constraint failed`
- `database is locked`
- `Database schema requires a controlled migration`
- `Scrape run completed`

## Sprawdzenie healthchecków

Web:

```text
http://localhost:3000/api/health
http://localhost:3000/api/ready
```

W obecnym hostingu `web` działa w przestrzeni sieciowej `vpn`, więc z zewnątrz sprawdzaj przez port publikowany przez `vpn` albo przez Cloudflare Tunnel.

Pozytywne wyniki:

- `/api/health`: HTTP 200
- `/api/ready`: HTTP 200, `integrity_check: ok`, `schema_version: 4`

## Test po wdrożeniu

1. Otwórz dashboard.
2. Sprawdź, czy nie ma banera o nieaktualnych danych.
3. Jeżeli baner jest widoczny, sprawdź ostatni sukces scrapera i logi `arena-scraper`.
4. Otwórz szczegóły wydarzenia.
5. Sprawdź wykres historii.
6. Zaloguj się jako administrator.
7. Otwórz panel admina.
8. Nie wykonuj zmian produkcyjnych, jeśli nie są potrzebne.

## Rollback obrazu

1. Nie zmieniaj wolumenów.
2. Nie usuwaj `pifpaf-data`.
3. W Portainerze wróć do poprzedniego commita/tagu albo poprzedniej wersji stacka.
4. Wykonaj redeploy.
5. Sprawdź logi i health/readiness.

DO WERYFIKACJI W PORTAINERZE: czy Portainer przechowuje poprzedni commit/tag albo historię konfiguracji stacka.

## Rollback bazy

Zatrzymaj:

1. `scraper` / `arena-scraper`
2. `web` / `arena-web`

Sprawdź backup:

```bash
python /app/check_db.py --database /data/backups/NAZWA_BACKUPU.db
```

Odtwórz:

```bash
python /app/restore_db.py --backup /data/backups/NAZWA_BACKUPU.db --database /data/app.db --emergency-dir /data/backups
```

Uruchom:

1. `web`
2. `scraper`

## Odzyskanie po uszkodzeniu stacka

1. Nie usuwaj wolumenu `pifpaf-data`.
2. Zachowaj aktualny Compose i zmienne środowiskowe z Portainera.
3. Utwórz awaryjny backup `/data/app.db`, jeżeli baza jest dostępna.
4. Przywróć poprzednią wersję Compose albo poprzedni commit.
5. Redeploy stacka.
6. Jeżeli baza jest uszkodzona, wykonaj rollback bazy z backupu.
7. Sprawdź `/api/ready`.

## Elementy, których nie wolno zmieniać

- `pifpaf-data:/data`
- `/data/app.db`
- `network_mode: "service:vpn"`
- publikowania portu przez `vpn`
- nazw usług i kontenerów
- `TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}`
- konfiguracji Gluetun bez osobnego planu
- Cloudflare Tunnel bez osobnego planu

## Opcjonalne usprawnienia Portainera

Nie są wymagane do poprawnego działania:

- zmiana healthchecka `web` z `/` na `/api/ready`
- osobny ręczny stack testowy używający `docker-compose.test.yml`
- harmonogram okresowego backupu przez kontener pomocniczy

Te zmiany są opcjonalne, bo obecny model hostingu działa bez nich.
