'use server';

import { revalidatePath } from 'next/cache';
import { getSession } from '../auth';
import db from '../db';

export async function deleteEvent(id: string) {
  const session = await getSession();
  if (!session) return { success: false, error: 'Brak uprawnien' };
  if (!db) return { success: false, error: 'Brak polaczenia z baza' };

  try {
    db.prepare('DELETE FROM event_snapshots WHERE event_id = ?').run(id);
    db.prepare('DELETE FROM events WHERE id = ?').run(id);
    revalidatePath('/');
    revalidatePath('/admin');
    return { success: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { success: false, error: message };
  }
}
