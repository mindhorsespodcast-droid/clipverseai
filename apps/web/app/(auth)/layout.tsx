import Link from "next/link";
import { Logo } from "@/components/Logo";
import { card } from "@/components/ui";
import { isSupabaseConfigured } from "@/lib/env";
import { SetupNotice } from "@/components/SetupNotice";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-10">
      <Link href="/" aria-label="ClipVerse AI home" className="mb-8 inline-flex min-h-11 items-center">
        <Logo size={30} />
      </Link>
      <div className="w-full max-w-sm space-y-4">
        {!isSupabaseConfigured && <SetupNotice />}
        <div className={`${card} p-6 sm:p-8`}>{children}</div>
      </div>
    </main>
  );
}
