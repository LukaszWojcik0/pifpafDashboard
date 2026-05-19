# Etap 1: Builder - budowanie aplikacji Next.js
FROM node:20-alpine AS builder

# Zainstaluj narzędzia deweloperskie potrzebne do kompilacji natywnych modułów (np. better-sqlite3)
RUN apk add --no-cache libc6-compat python3 make g++

# Ustaw katalog roboczy
WORKDIR /app

# Skopiuj pliki package.json i plik lock
COPY package*.json ./

# Zainstaluj zależności (w tym kroku skompiluje się better-sqlite3)
RUN npm install

# Skopiuj resztę kodu źródłowego aplikacji
COPY . .

# Uruchom skrypt budujący aplikację (stworzy folder .next/standalone)
RUN npm run build

# Etap 2: Runner - tworzenie finalnego, lekkiego obrazu produkcyjnego
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Skopiuj tylko niezbędne pliki z etapu buildera
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

# Uruchom serwer produkcyjny Next.js
CMD ["node", "server.js"]