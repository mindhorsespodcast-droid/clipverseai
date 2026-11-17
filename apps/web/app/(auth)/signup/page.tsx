import type { Metadata } from "next";
import { AuthForm } from "../AuthForm";
import { signup } from "../actions";

export const metadata: Metadata = { title: "Create account · ClipVerse AI" };

export default function SignupPage() {
  return (
    <>
      <h1 className="mb-1 text-2xl">Create your account</h1>
      <p className="mb-6 text-sm text-muted">60 free minutes every month. No card needed.</p>
      <AuthForm mode="signup" action={signup} />
    </>
  );
}
