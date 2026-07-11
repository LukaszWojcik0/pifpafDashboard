'use server';

import { revalidatePath } from 'next/cache';
import { getSession } from '../../auth';
import db from '../../db';

export async function updateMaxAvailable(formData: FormData) {
  const session = await getSession();
  if (!session) {
    throw new Error('Odmowa dostępu. Proszę się zalogować.');
  }

  const id = formData.get('id');
  const newMaxValue = formData.get('max');
  const newMax = typeof newMaxValue === 'string' ? Number.parseInt(newMaxValue, 10) : Number.NaN;

  if (typeof id !== 'string' || !id || Number.isNaN(newMax) || newMax < 0 || newMax > 100000) {
    console.error('Nieprawidłowa wartość podana przez formularz.');
    return;
  }

  if (db) {
    db.prepare('UPDATE events SET max_available = ? WHERE id = ?').run(newMax, id);
    revalidatePath(`/events/${id}`);
    revalidatePath('/');
  }
}
