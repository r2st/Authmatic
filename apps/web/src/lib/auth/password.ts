/**
 * Password hashing — scrypt (Node built-in, memory-hard KDF).
 *
 * Ticket 0005 asks for argon2id/bcrypt. We use scrypt instead: it is a
 * memory-hard KDF in the standard library, so there is no native-module
 * build risk (argon2/bcrypt ship platform binaries that break CI/containers).
 * Hash format is self-describing (`scrypt$N$r$p$salt$hash`, base64), so a
 * future migration to argon2 can detect-and-rehash on next login.
 *
 * Server-only. Never import into a client component.
 */
import {
  scrypt as _scrypt,
  randomBytes,
  timingSafeEqual,
  type ScryptOptions,
} from "crypto";

// promisify(scrypt) mistypes the options form: @types/node resolves the
// no-options overload, so the promisified call is typed 3-arg and rejects
// our { N, r, p, maxmem } options object. Wrap manually for a correct
// (password, salt, keylen, options) => Promise<Buffer> signature.
function scrypt(
  password: string,
  salt: Buffer,
  keylen: number,
  options: ScryptOptions
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    _scrypt(password, salt, keylen, options, (err, derivedKey) => {
      if (err) reject(err);
      else resolve(derivedKey);
    });
  });
}

// OWASP-aligned scrypt parameters (N=2^16, r=8, p=1).
const N = 1 << 16;
const R = 8;
const P = 1;
const KEYLEN = 32;
const SALT_BYTES = 16;

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(SALT_BYTES);
  const derived = (await scrypt(password, salt, KEYLEN, { N, r: R, p: P, maxmem: 256 * 1024 * 1024 })) as Buffer;
  return `scrypt$${N}$${R}$${P}$${salt.toString("base64")}$${derived.toString("base64")}`;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt") return false;
  const [, nStr, rStr, pStr, saltB64, hashB64] = parts;
  const salt = Buffer.from(saltB64, "base64");
  const expected = Buffer.from(hashB64, "base64");
  const derived = (await scrypt(password, salt, expected.length, {
    N: Number(nStr),
    r: Number(rStr),
    p: Number(pStr),
    maxmem: 256 * 1024 * 1024,
  })) as Buffer;
  // Constant-time compare.
  return derived.length === expected.length && timingSafeEqual(derived, expected);
}
