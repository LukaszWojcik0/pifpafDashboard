# Dashboard Wydarzeń Arena Walki

Projekt służy do zautomatyzowanego monitorowania otwartych gier i wydarzeń na stronie [arenawalki.pl](https://arenawalki.pl/gry-otwarte/). Składa się ze scrapera w Pythonie, który cyklicznie pobiera i analizuje dostępność biletów, oraz z nowoczesnego dashboardu w Next.js pozwalającego śledzić historię sprzedaży. Dodatkowo, system potrafi wysyłać powiadomienia Push za pomocą usługi ntfy.

## Opis działania systemu

1. **Scraper (Python)** używa `requests` i `BeautifulSoup` do wyciągania informacji o biletach z witryny. Uruchamia się cyklicznie za pomocą `APScheduler`.
2. Odkryte wydarzenia, statusy oraz liczba biletów zapisywane są (oraz aktualizowane) w lokalnej bazie **SQLite**.
3. Przy każdej zmianie puli biletów, zmianie statusu (np. na "Wyprzedane") lub wykryciu nowego wydarzenia, wysyłane jest powiadomienie do kanału **ntfy**.
4. **Dashboard (Next.js)** pozwala w przejrzysty sposób weryfikować dostępne informacje. Frontend komunikuje się z tą samą bazą SQLite, by odczytywać najświeższe dane i rysować wykresy dostępności biletów z użyciem `Recharts`.

## Architektura projektu

- **Backend / Scraper**: Python 3.12, BeautifulSoup4, APScheduler, sqlite3.
- **Frontend / Web**: Next.js (App Router), TypeScript, Tailwind CSS, Recharts.
- **Baza danych**: Plikowa baza SQLite, w trybie Server Components bez oddzielnego API (Next.js bezpośrednio czyta dane).
- **Infrastruktura**: Pełna konteneryzacja za pomocą Docker Compose z udostępnianiem wspólnego wolumenu bazy danych między usługami.

## Struktura katalogów

```text
/
├── main.py                # Główny skrypt scrapera Python
├── requirements.txt       # Zależności scrapera
├── Dockerfile             # Konfiguracja obrazu Docker dla scrapera
├── docker-compose.yml     # Orkiestracja całego systemu
├── data/                  # Katalog współdzielony na bazę SQLite (montowany do /data)
└── web/                   # Aplikacja frontendowa (Dashboard Next.js)
    ├── src/app/           # Routing i widoki (/, /events/[id])
    ├── src/components/    # Reużywalne komponenty (np. EventChart.tsx)
    ├── src/lib/           # Logika bazy danych (db.ts)
    ├── Dockerfile         # Konfiguracja obrazu Docker dla frontendu
    └── package.json       # Zależności Next.js
```

## Konfiguracja zmiennych środowiskowych

Projekt konfiguruje się przy pomocy zmiennych środowiskowych przekazywanych w pliku `docker-compose.yml` (lub ustawianych w systemie).

- `DATABASE_PATH` - ścieżka do pliku bazy, domyślnie `/data/app.db` dla Dockera lub `events.db` lokalnie.
- `SCRAPE_INTERVAL_MINUTES` - częstotliwość uruchamiania scrapera (w minutach, domyślnie `10`).
- `NTFY_URL` - URL kanału ntfy, na który wysyłane są alerty (np. `https://ntfy.sh/moj-tajny-kanal-123`).
- `ALERT_ON_FIRST_RUN` - Ustaw na `true`, by otrzymać masowe powiadomienia o wszystkich wykrytych wydarzeniach podczas pierwszego generowania bazy danych. Domyślnie `false` (cichy import).

## Uruchomienie lokalne

Bez użycia środowiska Docker, aplikacje należy uruchomić w dwóch osobnych oknach terminala. Baza domyślnie utworzy się jako `events.db` w głównym katalogu.

**1. Scraper (Python)**
```bash
pip install -r requirements.txt
# Ustawienie opcjonalnych zmiennych, np. (Linux/macOS):
export NTFY_URL="https://ntfy.sh/kanal" 
python main.py
```

**2. Dashboard (Next.js)**
```bash
cd web
npm install
npm run dev
# Dashboard będzie dostępny na http://localhost:3000
```

## Uruchomienie Docker Compose

Najprostsza i najbardziej zalecana metoda na serwerach produkcyjnych (Raspberry Pi, VPS).

```bash
# Sbuduj i uruchom w tle
docker-compose up -d --build

# Aby zobaczyć logi scrapera:
docker logs -f arena-scraper

# Zatrzymywanie:
docker-compose down
```
Dashboard będzie dostępny na porcie hosta `8088`: `http://localhost:8088`.

## Build Next.js production

Aby wybudować aplikację Next.js lokalnie i wystartować jej produkcyjną zoptymalizowaną wersję:

```bash
cd web
npm run build
npm start
```

*W środowisku Docker ten proces odbywa się automatycznie w tzw. multi-stage build w `web/Dockerfile`.*

## Backup SQLite

Aby wykonać backup, wystarczy skopiować plik bazy. Z uwagi na system wal-journal SQLite, kopiowanie w locie na produkcji jest generalnie bezpieczne, lecz dla 100% pewności można to zrobić zatrzymując system:

```bash
# 1. (Opcjonalnie) Zatrzymanie zapisu:
docker stop arena-scraper
# 2. Skopiowanie bazy do bezpiecznego folderu
cp data/app.db /sciezka/do/backupu/app_$(date +%Y%m%d).db
# 3. Ponowne uruchomienie
docker start arena-scraper
```

## Aktualizacja kontenerów

Gdy wprowadzisz modyfikacje do kodu w repozytorium (lub ściągniesz najnowsze z Git):

```bash
git pull origin main
docker-compose up -d --build
```
Polecenie to wymusi przebudowę zmienionych obrazów i podniesie na nowo kontenery, bez przerywania dostępu do bazy (wolumen `data/` pozostanie).

---

## Troubleshooting

### Scraper nie pobiera danych
1. Sprawdź logi kontenera: `docker logs arena-scraper`.
2. Upewnij się, że masz połączenie z siecią i strona `arenawalki.pl` jest online.
3. W logach może pojawić się `Błąd HTTP podczas pobierania szczegółów`. Jeśli to kod z rodziny 403, 429 - strona może blokować zapytania botów.

### Zmienił się HTML strony
Jeśli strona główna ulegnie przebudowie, scraper pobierze zero wydarzeń. W logach pojawi się ostrzeżenie. Trzeba zmodyfikować selektory używane przez aplikację w pliku `main.py`:
- `get_event_urls()` dla pobierania linków
- `scrape_event_details()` dla znajdowania daty, czasu oraz liczby dostępnych biletów.

### Next.js nie widzi bazy
Gdy na stronie widnieje napis "Brak danych w bazie lub wystąpił błąd", a logi Next.js rzucają komunikatem o pliku `ENOENT`, problemem są ścieżki.
- Sprawdź, czy `DATABASE_PATH` jest przekazane poprawnie.
- Sprawdź konfigurację wolumenów w `docker-compose.yml`. Serwis `web` oraz `scraper` muszą wskazywać na dokładnie to samo podmontowane terytorium.

### SQLite locked (Baza zablokowana)
Może się wydarzyć tylko, gdy baza nie wyrabia z zapisem, a dashboard dokonuje odczytu, aczkolwiek w SQLite współbieżne czytanie jest bezpieczne. W razie notorycznego pojawiania się błędu "database is locked":
1. Przeprowadź Vacuum.
2. Zwiększ parametr `timeout` (lub dodaj moduł WAL-mode podczas inicjalizacji DB, zmieniając pragma `journal_mode=WAL`).
Błąd rzadki z powodu małego ruchu na bazie.

### ntfy nie działa
1. Sprawdź poprawność URL (musi to być kanał na serwerze, do którego masz dostęp - bez autoryzacji z reguły publiczny serwer `https://ntfy.sh/...`).
2. Scraper wypluje w logach szczegóły zapytania, jeśli `requests.post()` rzuci błędem połączenia. Upewnij się czy firewall nie blokuje portów wychodzących HTTPS.

### Dashboard pusty (wszędzie braki lub myślniki)
Zazwyczaj to rezultat pierwszego uruchomienia aplikacji webowej, **przed** momentem, w którym cykliczny scraper ukończył swoje pierwsze pełne wejście w wydarzenia (może to potrwać parę sekund). Odśwież stronę po minucie. Jeśli widok nadal jest uszkodzony, prześledź zrzuty danych poprzez wejście w szczegóły wydarzenia - brak logów na wykresie oznacza problem po stronie bazy/scrapera.