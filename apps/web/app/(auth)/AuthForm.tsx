"use client";

import Link from "next/link";
import { useActionState } from "react";
import type { AuthState } from "./actions";
import { btnPrimary, input, label } from "@/components/ui";

type Props = {
  mode: "login" | "signup";
  action: (prev: AuthState, formData: FormData) => Promise<AuthState>;
};

export function AuthForm({ mode, action }: Props) {
  const [state, formAction, pending] = useActionState(action, {});
  const isLogin = mode === "login";

  if (state.message) {
    return (
      <div role="status" className="space-y-4 text-center">
        <p className="text-base leading-relaxed text-fg">{state.message}</p>
        <p className="text-sm text-muted">
          Didn&apos;t get it? Check your spam folder, or{" "}
          <Link href="/signup" className="text-fg underline underline-offset-4">
            try again
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <form action={formAction} className="space-y-5" noValidate>
      <div>
        <label htmlFor="email" className={label}>
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          defaultValue={state.email}
          placeholder="you@example.com"
          className={input}
        />
      </div>
      <div>
        <label htmlFor="password" className={label}>
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          required
          minLength={isLogin ? undefined : 8}
          aria-describedby={isLogin ? undefined : "password-hint"}
          className={input}
        />
        {!isLogin && (
          <p id="password-hint" className="mt-2 text-sm text-muted">
            At least 8 characters.
          </p>
        )}
      </div>

      {state.error && (
        <p
          role="alert"
          className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        >
          {state.error}
        </p>
      )}

      <button type="submit" disabled={pending} className={`${btnPrimary} w-full`}>
        {pending ? "Please wait..." : isLogin ? "Log in" : "Create free account"}
      </button>

      <p className="text-center text-sm text-muted">
        {isLogin ? "New to ClipVerse AI? " : "Already have an account? "}
        <Link
          href={isLogin ? "/signup" : "/login"}
          className="inline-block py-2 font-medium text-fg underline underline-offset-4"
        >
          {isLogin ? "Create an account" : "Log in"}
        </Link>
      </p>
    </form>
  );
}
