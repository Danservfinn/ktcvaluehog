/**
 * Supabase client for authentication
 * Uses @supabase/supabase-js client-side
 */

import { createClient } from '@supabase/supabase-js'

// Environment variables (set in .env.local or Cloudflare Pages env)
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

// Create Supabase client lazily to avoid build errors
let _supabase: ReturnType<typeof createClient> | null = null

function getSupabaseClient() {
  if (!_supabase) {
    if (!supabaseUrl || !supabaseAnonKey) {
      // Return a mock client during build or when env vars are missing
      return null
    }
    _supabase = createClient(supabaseUrl, supabaseAnonKey)
  }
  return _supabase
}

// Export for direct usage (may be null during build)
export const supabase = getSupabaseClient()

// User tier type
export type UserTier = 'free' | 'pro' | 'elite'

// User profile with tier
export interface UserProfile {
  id: string
  email: string
  tier: UserTier
  created_at: string
}

/**
 * Get current session
 */
export async function getSession() {
  if (!supabase) return null
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error) throw error
  return session
}

/**
 * Get current user with tier info
 */
export async function getCurrentUser(): Promise<UserProfile | null> {
  if (!supabase) return null
  const { data: { user }, error } = await supabase.auth.getUser()
  if (error || !user) return null

  // Get tier from app_metadata (set via Supabase dashboard)
  const tier = (user.app_metadata?.tier as UserTier) || 'free'

  return {
    id: user.id,
    email: user.email || '',
    tier,
    created_at: user.created_at,
  }
}

/**
 * Sign in with email/password
 */
export async function signIn(email: string, password: string) {
  if (!supabase) throw new Error('Supabase not configured')
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })
  if (error) throw error
  return data
}

/**
 * Sign up with email/password
 */
export async function signUp(email: string, password: string) {
  if (!supabase) throw new Error('Supabase not configured')
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  })
  if (error) throw error
  return data
}

/**
 * Sign out
 */
export async function signOut() {
  if (!supabase) return
  const { error } = await supabase.auth.signOut()
  if (error) throw error
}

/**
 * Get auth token for API requests
 */
export async function getAuthToken(): Promise<string | null> {
  const session = await getSession()
  return session?.access_token || null
}

/**
 * Check if user has required tier
 */
export function hasTier(userTier: UserTier, requiredTier: UserTier): boolean {
  const tierOrder: UserTier[] = ['free', 'pro', 'elite']
  return tierOrder.indexOf(userTier) >= tierOrder.indexOf(requiredTier)
}
