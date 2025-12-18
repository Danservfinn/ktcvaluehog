'use client'

/**
 * Auth context provider for managing user authentication state
 */

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { supabase, UserProfile, getCurrentUser, signIn, signUp, signOut, getAuthToken } from './supabase'

interface AuthContextType {
  user: UserProfile | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  getToken: () => Promise<string | null>
  isPro: boolean
  isElite: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check for existing session on mount
    getCurrentUser().then(setUser).finally(() => setLoading(false))

    // Listen for auth changes (only if supabase is configured)
    if (!supabase) {
      return
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
        const profile = await getCurrentUser()
        setUser(profile)
      } else if (event === 'SIGNED_OUT') {
        setUser(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  const handleSignIn = async (email: string, password: string) => {
    await signIn(email, password)
    const profile = await getCurrentUser()
    setUser(profile)
  }

  const handleSignUp = async (email: string, password: string) => {
    await signUp(email, password)
    // User may need to confirm email before being fully signed in
  }

  const handleSignOut = async () => {
    await signOut()
    setUser(null)
  }

  const value: AuthContextType = {
    user,
    loading,
    signIn: handleSignIn,
    signUp: handleSignUp,
    signOut: handleSignOut,
    getToken: getAuthToken,
    isPro: user?.tier === 'pro' || user?.tier === 'elite',
    isElite: user?.tier === 'elite',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
