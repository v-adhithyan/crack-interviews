"use client";

import { LogOut } from "lucide-react";
import { FormEvent, ReactNode, useEffect, useState } from "react";
import { getAuthToken, getCurrentAdmin, loginAdmin, logoutAdmin, type AuthUser } from "@/lib/api";

type Props = {
  children: (user: AuthUser, logout: () => Promise<void>) => ReactNode;
};

export function AuthGate({ children }: Props) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;
    async function loadUser() {
      if (!getAuthToken()) {
        setIsLoading(false);
        return;
      }
      try {
        const currentUser = await getCurrentAdmin();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch {
        if (isMounted) {
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }
    loadUser();
    return () => {
      isMounted = false;
    };
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      const session = await loginAdmin(String(form.get("username") ?? ""), String(form.get("password") ?? ""));
      setUser(session.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to log in.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    await logoutAdmin();
    setUser(null);
  }

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center bg-paper px-6 text-ink">
        <div className="rounded-lg border border-line bg-white/90 px-5 py-4 text-sm font-bold shadow-product">Checking admin access...</div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="grid min-h-screen place-items-center bg-paper px-6 text-ink">
        <section className="w-full max-w-md rounded-lg border border-[rgba(15,23,42,0.08)] bg-white/90 p-8 shadow-product">
          <div className="mb-7">
            <div className="mb-4 grid size-11 place-items-center rounded-[10px] bg-gradient-to-br from-[#ffe66b] to-gold-strong font-black shadow-[inset_8px_0_0_rgba(247,184,1,0.52)]">HL</div>
            <h1 className="text-2xl font-[850]">Admin Login</h1>
            <p className="mt-2 text-sm leading-6 text-muted">Use your HackerLeap admin account to access coding practice.</p>
          </div>
          <form className="grid gap-4" onSubmit={handleLogin}>
            <label className="grid gap-2 text-sm font-bold">
              Email or username
              <input className="h-12 rounded-[7px] border border-line px-3 outline-none focus:border-gold focus:ring-4 focus:ring-[rgba(247,184,1,0.18)]" name="username" autoComplete="username" required />
            </label>
            <label className="grid gap-2 text-sm font-bold">
              Password
              <input className="h-12 rounded-[7px] border border-line px-3 outline-none focus:border-gold focus:ring-4 focus:ring-[rgba(247,184,1,0.18)]" name="password" type="password" autoComplete="current-password" required />
            </label>
            {error ? <p className="rounded-[7px] bg-orange-50 px-3 py-2 text-sm font-bold text-orange-700">{error}</p> : null}
            <button className="mt-2 inline-flex h-12 items-center justify-center rounded-[7px] border border-[rgba(247,184,1,0.72)] bg-gradient-to-br from-[#ffd400] to-gold px-4 font-[850] text-black disabled:opacity-60" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Logging in..." : "Log in"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <>
      <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-[7px] border border-line bg-white px-3 py-2 text-xs font-bold text-muted shadow-product">
        <span>{user.email || user.username}</span>
        <button className="grid size-7 place-items-center rounded-[6px] hover:bg-[#fffaf0]" type="button" onClick={handleLogout} aria-label="Log out" title="Log out">
          <LogOut size={14} />
        </button>
      </div>
      {children(user, handleLogout)}
    </>
  );
}
