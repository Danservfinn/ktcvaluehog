"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { supabase, UserTier, getCurrentUser, signIn, signOut as supabaseSignOut } from "@/lib/supabase";

// Admin credentials for bypass mode (when Supabase not configured)
const ADMIN_PASSWORD = "thoth2025elite";

interface User {
  id: string;
  email: string;
  tier: UserTier;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isElite: boolean;
  isPro: boolean;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signInAsAdmin: (password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check for existing session on mount
  useEffect(() => {
    async function initAuth() {
      try {
        // First check localStorage for admin bypass
        if (typeof window !== "undefined") {
          const adminSession = localStorage.getItem("thoth_admin_session");
          if (adminSession) {
            const parsed = JSON.parse(adminSession);
            if (parsed.expires > Date.now()) {
              setUser({
                id: "admin",
                email: "admin@thoth.local",
                tier: "elite",
              });
              setLoading(false);
              return;
            } else {
              localStorage.removeItem("thoth_admin_session");
            }
          }
        }

        // Then check Supabase if configured
        if (supabase) {
          const currentUser = await getCurrentUser();
          if (currentUser) {
            setUser({
              id: currentUser.id,
              email: currentUser.email,
              tier: currentUser.tier,
            });
          }
        }
      } catch (err) {
        console.error("Auth init error:", err);
      } finally {
        setLoading(false);
      }
    }

    initAuth();

    // Listen for Supabase auth changes
    if (supabase) {
      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        async (event, session) => {
          if (event === "SIGNED_IN" && session?.user) {
            const tier = (session.user.app_metadata?.tier as UserTier) || "free";
            setUser({
              id: session.user.id,
              email: session.user.email || "",
              tier,
            });
          } else if (event === "SIGNED_OUT") {
            setUser(null);
          }
        }
      );

      return () => subscription.unsubscribe();
    }
  }, []);

  // Sign in with email/password via Supabase
  const signInWithEmail = useCallback(async (email: string, password: string) => {
    setError(null);
    setLoading(true);
    try {
      if (!supabase) {
        throw new Error("Supabase not configured. Use admin login instead.");
      }
      await signIn(email, password);
    } catch (err: any) {
      setError(err.message || "Sign in failed");
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Admin bypass login (for testing without Supabase)
  const signInAsAdmin = useCallback(async (password: string): Promise<boolean> => {
    setError(null);
    if (password === ADMIN_PASSWORD) {
      const session = {
        expires: Date.now() + 24 * 60 * 60 * 1000, // 24 hours
      };
      localStorage.setItem("thoth_admin_session", JSON.stringify(session));
      setUser({
        id: "admin",
        email: "admin@thoth.local",
        tier: "elite",
      });
      return true;
    } else {
      setError("Invalid admin password");
      return false;
    }
  }, []);

  // Logout
  const logout = useCallback(async () => {
    setLoading(true);
    try {
      // Clear admin session
      if (typeof window !== "undefined") {
        localStorage.removeItem("thoth_admin_session");
      }
      // Sign out from Supabase if applicable
      if (supabase) {
        await supabaseSignOut();
      }
      setUser(null);
    } catch (err: any) {
      setError(err.message || "Logout failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const isElite = user?.tier === "elite";
  const isPro = user?.tier === "pro" || user?.tier === "elite";

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isElite,
        isPro,
        signInWithEmail,
        signInAsAdmin,
        logout,
        error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
