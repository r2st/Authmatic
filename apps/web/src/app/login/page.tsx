"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    const ok = await login(email, password);
    setPending(false);
    if (!ok) {
      setError("Invalid email or password.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#fafaf7] px-6">
      <div className="w-full max-w-md">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#b8410e]">
          Authmatic
        </p>
        <h1 className="mt-2 font-serif text-4xl font-semibold text-[#0f1419]">
          Clinic sign in
        </h1>
        <p className="mt-2 text-sm text-[#5b6470]">
          HIPAA-scoped access for prior authorization workflows.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-8 space-y-4 rounded-xl border border-[#e4e7eb] bg-white p-6 shadow-sm"
        >
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-[#5b6470]">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e4e7eb] px-3 py-2 text-sm focus:border-[#b8410e] focus:outline-none focus:ring-1 focus:ring-[#b8410e]"
              autoComplete="username"
            />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-[#5b6470]">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e4e7eb] px-3 py-2 text-sm focus:border-[#b8410e] focus:outline-none focus:ring-1 focus:ring-[#b8410e]"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
          )}

          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-lg bg-[#0f1419] py-3 text-sm font-semibold text-white hover:bg-[#b8410e] disabled:opacity-60"
          >
            {pending ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
