/**
 * Reference IDs for prior-auth submissions.
 *
 * Format: `PA-` + 16 uppercase hex chars (64 bits of CSPRNG entropy).
 * Unguessable and non-enumerable — replaces the old sequential
 * `PA-2026-NNNNN` scheme (ticket 0007), which let anyone iterate the whole
 * table. Hex (not base32) is chosen so the exact same value can be
 * generated in SQL during the rotation migration
 * (`'PA-' || upper(encode(gen_random_bytes(8), 'hex'))`), keeping app and
 * DB formats identical.
 */

/** Matches a canonical reference id. Case-insensitive; used to parse Rtrvr output. */
export const REFERENCE_ID_RE = /PA-[0-9A-F]{16}/i;

/** Generate a new unguessable reference id. */
export function newReferenceId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `PA-${hex.toUpperCase()}`;
}

/** True if `value` is a syntactically valid reference id (exact match). */
export function isValidReferenceId(value: string): boolean {
  return new RegExp(`^${REFERENCE_ID_RE.source}$`, "i").test(value);
}
