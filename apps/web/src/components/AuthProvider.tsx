"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  fetchSession,
  loginRequest,
  logoutRequest,
  type ClinicUser,
} from "@/lib/auth";

type AuthContextValue = {
  user: ClinicUser | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const PUBLIC_PATHS = ["/login", "/portal"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<ClinicUser | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let active = true;
    fetchSession().then((u) => {
      if (!active) return;
      setUser(u);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    const isPublic =
      PUBLIC_PATHS.some((p) => pathname.startsWith(p)) || pathname.startsWith("/portal/");
    if (!user && !isPublic && pathname !== "/login") {
      router.replace("/login");
    }
    if (user && pathname === "/login") {
      router.replace("/dashboard");
    }
  }, [user, ready, pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    const u = await loginRequest(email, password);
    if (u) {
      setUser(u);
      return true;
    }
    return false;
  }, []);

  const logout = useCallback(() => {
    void logoutRequest();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, ready, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
