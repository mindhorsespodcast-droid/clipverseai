import Link from "next/link";
import { Logo } from "@/components/Logo";
import { btnPrimary, btnSecondary } from "@/components/ui";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-4">
        <Logo size={26} />
        <Link href="/login" className={btnSecondary}>
          Log in
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-16 text-center">
        <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
          Built for Indian creators · any long video
        </p>
        <h1 className="text-[2.6rem] leading-[1.05] sm:text-6xl">
          Long videos in.
          <br />
          Clips that go <em className="font-serif font-normal italic text-accent">viral</em> out.
        </h1>
        <p className="mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
          Podcasts, streams, vlogs, classes, webinars. ClipVerse AI finds the moments your audience
          shares and adds captions that actually get Hinglish right.
        </p>
        <div className="mt-10 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
          <Link href="/signup" className={btnPrimary}>
            Get free clips →
          </Link>
          <Link href="/login" className={btnSecondary}>
            I have an account
          </Link>
        </div>
        <p className="mt-4 text-sm text-muted">60 free minutes · No card needed</p>
      </main>

      <footer className="mx-auto w-full max-w-5xl px-4 py-6 text-sm text-muted">
        © {new Date().getFullYear()} ClipVerse AI · Made in India
      </footer>
    </div>
  );
}
