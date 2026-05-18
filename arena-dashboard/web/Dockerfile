FROM node:20-alpine AS base

# Wymagane narzędzia kompilacji do instalacji pakietu z natywnym SQLite (better-sqlite3)
RUN apk add --no-cache python3 make g++ sqlite

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm i

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Next.js build w trybie standalone
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Kopiowanie skompilowanego serwera standalone i plików statycznych Next.js
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]