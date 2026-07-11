import { NextResponse } from 'next/server';
import db from '../../db';

export const dynamic = 'force-dynamic';

export function GET() {
  if (!db) {
    return NextResponse.json({ ok: false, error: 'database_unavailable' }, { status: 503 });
  }

  try {
    const integrity = db.prepare('PRAGMA quick_check').get() as { quick_check: string } | undefined;
    const migration = db.prepare('SELECT max(version) as version FROM schema_migrations').get() as { version: number | null };
    const ready = integrity?.quick_check === 'ok' && Number(migration.version ?? 0) >= 4;
    return NextResponse.json(
      {
        ok: ready,
        integrity_check: integrity?.quick_check ?? 'unknown',
        schema_version: migration.version ?? 0,
      },
      { status: ready ? 200 : 503 },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message.slice(0, 300) }, { status: 503 });
  }
}
