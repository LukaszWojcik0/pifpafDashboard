import crypto from 'crypto';
import { promisify } from 'util';

const pbkdf2 = promisify(crypto.pbkdf2);

export function randomSalt(): string {
  return crypto.randomBytes(16).toString('hex');
}

export async function hashPassword(password: string, salt: string): Promise<string> {
  const derivedKey = await pbkdf2(password, salt, 310000, 64, 'sha512');
  return derivedKey.toString('hex');
}

export function safeCompareHex(value: string, expected: string): boolean {
  const valueBuffer = Buffer.from(value, 'hex');
  const expectedBuffer = Buffer.from(expected, 'hex');
  return valueBuffer.length === expectedBuffer.length && crypto.timingSafeEqual(valueBuffer, expectedBuffer);
}
