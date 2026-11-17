import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { isSupabaseConfigured, supabaseKey, supabaseUrl } from "@/lib/env";

// Pages that need you to be logged in.
const PROTECTED = ["/dashboard"];
// Pages that make no sense once you ARE logged in.
const AUTH_PAGES = ["/login", "/signup"];

// Runs before every page: keeps your login fresh and sends you to the right place.
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  if (!isSupabaseConfigured) return response;

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // Don't put any code between createServerClient and getClaims():
  // this call is what refreshes an expiring login.
  let loggedIn = false;
  try {
    const { data } = await supabase.auth.getClaims();
    loggedIn = Boolean(data?.claims?.sub);
  } catch {
    // Supabase unreachable - let the page itself show a friendly error.
    return response;
  }

  const path = request.nextUrl.pathname;
  const redirectTo = (to: string) => {
    const url = request.nextUrl.clone();
    url.pathname = to;
    url.search = "";
    const redirect = NextResponse.redirect(url);
    response.cookies.getAll().forEach((c) => redirect.cookies.set(c));
    return redirect;
  };

  if (!loggedIn && PROTECTED.some((p) => path === p || path.startsWith(`${p}/`))) {
    return redirectTo("/login");
  }
  if (loggedIn && AUTH_PAGES.includes(path)) {
    return redirectTo("/dashboard");
  }
  return response;
}
