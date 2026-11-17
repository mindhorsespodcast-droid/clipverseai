import Link from "next/link";
import { Logo } from "@/components/Logo";
import { btnSecondary } from "@/components/ui";
import { logout } from "@/app/(auth)/actions";

export function AppHeader({ email }: { email?: string | null }) {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/dashboard" aria-label="Your projects" className="inline-flex min-h-11 items-center">
          <Logo size={26} />
        </Link>
        <div className="flex items-center gap-3">
          {email && (
            <span className="hidden max-w-[220px] truncate text-sm text-muted sm:inline" title={email}>
              {email}
            </span>
          )}
          <form action={logout}>
            <button type="submit" className={btnSecondary}>
              Log out
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
