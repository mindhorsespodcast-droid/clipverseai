import type { Metadata } from "next";
import { AuthForm } from "../AuthForm";
import { login } from "../actions";

export const metadata: Metadata = { title: "Log in · ClipVerse AI" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { error } = await searchParams;
  return (
    <>
      <h1 className="mb-1 text-2xl">Welcome back</h1>
      <p className="mb-6 text-sm text-muted">Log in to see your clips.</p>
      {error === "link" && (
        <p role="alert" className="mb-5 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          That confirmation link didn&apos;t work. It may have expired, or been opened in a different
          browser. Try logging in, or sign up again for a new link.
        </p>
      )}
      <AuthForm mode="login" action={login} />
    </>
  );
}
