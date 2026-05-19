'use server';

import db from '../db';
import { revalidatePath } from 'next/cache';

export async function deleteEvent(id: string) {
  if (!db) return { success: false, error: 'Brak połączenia z bazą' };
  try {
    const stmt1 = db.prepare('DELETE FROM event_snapshots WHERE event_id = ?');
    stmt1.run(id);
    const stmt2 = db.prepare('DELETE FROM events WHERE id = ?');
    stmt2.run(id);
    revalidatePath('/');
    revalidatePath('/admin');
    return { success: true };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}
