/**
 * Supabase client singleton.
 *
 * Reads VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY from env.
 * When env vars are missing (local dev without Supabase), the client
 * is null and auth falls back to the legacy custom-token flow.
 *
 * Issue: #318 | Parent Epic: #313
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

let supabase: SupabaseClient | null = null

if (supabaseUrl && supabaseAnonKey) {
  supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      // Disable automatic URL detection on init so the AuthProvider
      // can set up onAuthStateChange BEFORE the session is exchanged.
      // AuthProvider calls getSession() + detectSessionFromURL manually.
      detectSessionInUrl: false,
    },
  })
}

export default supabase

/**
 * Returns true when Supabase Auth is configured.
 * The app uses this to decide between Supabase and legacy auth flows.
 */
export function isSupabaseEnabled(): boolean {
  return supabase !== null
}
