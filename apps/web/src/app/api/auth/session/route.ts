import { NextResponse } from "next/server";
import { getServerSession } from "@/lib/auth/server";

/** GET /api/auth/session — current user, or 401. Used by the client AuthProvider. */
export async function GET() {
  const session = await getServerSession();
  if (!session) return NextResponse.json({ user: null }, { status: 401 });
  return NextResponse.json({
    user: {
      email: session.email,
      name: session.name,
      role: session.role,
      clinic: session.clinic,
    },
  });
}
