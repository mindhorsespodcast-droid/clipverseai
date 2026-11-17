"use server";

import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { createClient } from "@/lib/supabase/server";
import { isSupabaseConfigured } from "@/lib/env";

export type AuthState = { error?: string; message?: string; email?: string };

const NOT_SET_UP =
  "Login isn't set up yet. Add your Supabase keys to the .env file (see README, step 3), then restart the app.";

// Turn Supabase's technical errors into plain English.
function friendly(error: { code?: string; message?: string; status?: number }): string {
  switch (error.code) {
    case "invalid_credentials":
      return "That email and password don't match. Try again, or create an account.";
    case "email_not_confirmed":
      return "Please confirm your email first. Open the link we sent to your inbox.";
    case "user_already_exists":
    case "email_exists":
      return "An account with this email already exists. Try logging in instead.";
    case "weak_password":
      return "Please choose a stronger password (at least 8 characters, mixing letters and numbers).";
    case "over_email_send_rate_limit":
      return "We've sent too many emails in a short time. Please wait a few minutes and try again.";
    case "over_request_rate_limit":
      return "Too many attempts. Please wait a minute and try again.";
    case "email_address_invalid":
      return "That email address doesn't look right. Please check it.";
    case "signup_disabled":
      return "New sign-ups are switched off right now.";
  }
  if (error.message?.toLowerCase().includes("fetch")) {
    return "We couldn't reach the login service. Check your internet connection and the Supabase URL in .env.";
  }
  return "Something went wrong. Please try again in a moment.";
}

function readForm(formData: FormData) {
  return {
    email: String(formData.get("email") ?? "").trim().toLowerCase(),
    password: String(formData.get("password") ?? ""),
  };
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function login(_prev: AuthState, formData: FormData): Promise<AuthState> {
  const { email, password } = readForm(formData);
  if (!isSupabaseConfigured) return { error: NOT_SET_UP, email };
  if (!EMAIL_RE.test(email)) return { error: "Please enter a valid email address.", email };
  if (!password) return { error: "Please enter your password.", email };

  const supabase = await createClient();
  try {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) return { error: friendly(error), email };
  } catch (e) {
    return { error: friendly(e as Error), email };
  }
  redirect("/dashboard");
}

export async function signup(_prev: AuthState, formData: FormData): Promise<AuthState> {
  const { email, password } = readForm(formData);
  if (!isSupabaseConfigured) return { error: NOT_SET_UP, email };
  if (!EMAIL_RE.test(email)) return { error: "Please enter a valid email address.", email };
  if (password.length < 8) {
    return { error: "Your password needs at least 8 characters.", email };
  }

  const h = await headers();
  const origin =
    process.env.NEXT_PUBLIC_SITE_URL ||
    `${h.get("x-forwarded-proto") ?? "http"}://${h.get("host") ?? "localhost:3000"}`;

  const supabase = await createClient();
  let hasSession = false;
  try {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${origin}/auth/callback` },
    });
    if (error) return { error: friendly(error), email };
    hasSession = Boolean(data.session);
  } catch (e) {
    return { error: friendly(e as Error), email };
  }

  // If email confirmation is switched off in Supabase, you're logged in straight away.
  if (hasSession) redirect("/dashboard");

  return {
    message: `Almost there! We've sent a confirmation link to ${email}. Open it on this device to finish signing up.`,
  };
}

export async function logout() {
  if (isSupabaseConfigured) {
    const supabase = await createClient();
    await supabase.auth.signOut();
  }
  redirect("/login");
}
