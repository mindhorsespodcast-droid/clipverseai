import "server-only";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { supabaseKey, supabaseUrl } from "@/lib/env";

// A Supabase connection for server code (pages, server actions).
// It acts as the logged-in user, so database privacy rules (RLS) apply.
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options),
          );
        } catch {
          // Called from a page (read-only cookies). Safe to ignore: proxy.ts
          // refreshes the login session on every request.
        }
      },
    },
  });
}
