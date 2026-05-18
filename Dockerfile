# Używamy lekkiego obrazu Python 3.12
FROM python:3.12-slim

# Ustawiamy zmienne środowiskowe, aby zapobiec tworzeniu plików .pyc i buforowaniu logów
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Domyślna ścieżka do bazy danych (wewnątrz wolumenu /data)
ENV DATABASE_PATH=/data/app.db

# Ustawiamy katalog roboczy
WORKDIR /app

# Kopiujemy plik z wymaganiami i instalujemy zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy resztę aplikacji
COPY . .

# Tworzymy katalog na bazę danych
RUN mkdir -p /data

# Polecenie startowe
CMD ["python", "main.py"]
