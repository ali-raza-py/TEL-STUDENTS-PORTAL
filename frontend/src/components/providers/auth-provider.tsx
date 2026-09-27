"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { ApiError, primeCsrfCookie } from "@/lib/api-client";
import { endpoints } from "@/lib/endpoints";
import { useMutation } from "@/lib/hooks/use-resource";
import type { Capability, MeResponse_, SessionUser } from "@/lib/session-types";

/**
 * Session state.
 *
 * The access and refresh tokens live in `HttpOnly` cookies, so the browser
 * never holds a credential in JavaScript. This provider holds only the
 * non-sensitive profile that the UI needs to render, plus the capability list
 * the backend issued — and capabilities are treated as a UI hint only; the API
 * re-checks every request.
 */

interface AuthContextValue {
  user: SessionUser | null;
  status: "loading" | "authenticated" | "anonymous";
  error: ApiError | null;
  can: (capability: Capability) => boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  isRepresentative: boolean;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = React.useState<SessionUser | null>(null);
  const [status, setStatus] = React.useState<AuthContextValue["status"]>("loading");
  const [error, setError] = React.useState<ApiError | null>(null);

  const load = React.useCallback(async () => {
    try {
      await primeCsrfCookie();
      const data = await endpoints.auth.me();
      setUser(toSessionUser(data));
      setStatus("authenticated");
      setError(null);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        setUser(null);
        setStatus("anonymous");
        return;
      }
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError(0, "unknown", "We could not verify your session."),
      );
      setStatus("anonymous");
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const login = React.useCallback(async (email: string, password: string) => {
    try {
      const data: MeResponse_ = await endpoints.auth.login({ email: email.trim(), password });
      setUser(toSessionUser(data));
      setStatus("authenticated");
      setError(null);
    } catch (cause) {
      const apiError =
        cause instanceof ApiError
          ? cause
          : new ApiError(0, "unknown", "Sign-in failed. Please try again.");
      setError(apiError);
      throw apiError;
    }
  }, []);

  const logoutMutation = useMutation(async () => {
    try {
      await endpoints.auth.logout();
    } finally {
      setUser(null);
      setStatus("anonymous");
      router.replace("/login");
    }
  });

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      error,
      can: (capability) => Boolean(user?.capabilities.includes(capability)),
      login,
      logout: async () => {
        await logoutMutation.run();
      },
      refresh: load,
      isRepresentative: user?.role === "CLASS_REPRESENTATIVE",
    }),
    [user, status, error, login, logoutMutation, load],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function toSessionUser(data: MeResponse_): SessionUser {
  return {
    id: data.user.id,
    email: data.user.email,
    fullName: data.user.full_name,
    initials: data.user.initials,
    role: data.user.role,
    phone: data.user.phone,
    capabilities: data.user.capabilities,
    profile: data.user.student_profile,
  };
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

/** Throws a helpful error if a component is rendered without a session. */
export function useRequiredUser(): SessionUser {
  const { user, status } = useAuth();
  if (status === "loading") {
    return {
      id: 0,
      email: "",
      fullName: "",
      initials: "",
      role: "STUDENT",
      phone: "",
      capabilities: [],
      profile: null,
    };
  }
  if (!user) throw new Error("This view requires an authenticated session.");
  return user;
}
