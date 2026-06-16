/**
 * Idempotency keys for unsafe POSTs (ticket 0017). Stripe-style:
 * `Idempotency-Key` header → first request executes and its response is
 * cached for 24h; a repeat with the same key + same body returns the cached
 * response without re-executing; the same key + a different body is a 422
 * conflict.
 *
 * Storage: in-process Map with TTL — per-instance (a double-click on one
 * instance is deduped; cross-instance needs Redis/InsForge-KV behind the
 * same interface). Documented upgrade path. Keys are scoped by clinic/IP so
 * one tenant cannot probe another's keys.
 *
 * Server-only (uses node crypto).
 */
import { createHash } from "crypto";

const TTL_MS = 24 * 60 * 60 * 1000;

interface StoredResponse {
  requestHash: string;
  status: number;
  body: unknown;
  expires: number;
}

const store = new Map<string, StoredResponse>();

/** Stable hash of the request body so a reused key with a changed body conflicts. */
export function hashBody(body: unknown): string {
  return createHash("sha256").update(JSON.stringify(body ?? null)).digest("hex");
}

function bucket(key: string, scope: string): string {
  return `${scope}:${key}`;
}

function sweep(now: number): void {
  for (const [k, v] of store) if (v.expires <= now) store.delete(k);
}

export type IdempotencyOutcome =
  | { kind: "new" }
  | { kind: "replay"; status: number; body: unknown }
  | { kind: "conflict" };

/** Look up a prior response for (key, scope), validating the body matches. */
export function lookupIdempotency(
  key: string,
  scope: string,
  requestHash: string,
  now: number = Date.now()
): IdempotencyOutcome {
  sweep(now);
  const prior = store.get(bucket(key, scope));
  if (!prior) return { kind: "new" };
  if (prior.requestHash !== requestHash) return { kind: "conflict" };
  return { kind: "replay", status: prior.status, body: prior.body };
}

/** Record a response so a repeat of (key, scope, body) replays it. */
export function saveIdempotency(
  key: string,
  scope: string,
  requestHash: string,
  status: number,
  body: unknown,
  now: number = Date.now()
): void {
  store.set(bucket(key, scope), { requestHash, status, body, expires: now + TTL_MS });
}

/** Test helper. */
export function _resetIdempotency(): void {
  store.clear();
}
