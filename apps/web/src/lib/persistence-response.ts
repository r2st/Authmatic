/**
 * Map a PersistenceError to a 503 response (ticket 0016). Routes wrap their
 * persistence calls with `to503(err)` so a DB outage surfaces as a clear
 * "service unavailable" instead of a silent in-memory write or a generic 500.
 */
import { NextResponse } from "next/server";
import { PersistenceError } from "./submissions";

/** Returns a 503 NextResponse if `err` is a PersistenceError; otherwise rethrows. */
export function to503(err: unknown): NextResponse {
  if (err instanceof PersistenceError) {
    return NextResponse.json(
      { error: "service_unavailable", message: "Storage is temporarily unavailable. Please retry." },
      { status: 503 }
    );
  }
  throw err;
}
