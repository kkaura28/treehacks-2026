import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Viper",
  description: "Post-operative compliance analysis dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[hsl(var(--background))]">
        <div className="flex min-h-screen">
          <aside className="w-64 border-r border-zinc-800 bg-zinc-950 p-6 flex flex-col gap-8 fixed h-full">
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">Viper</h1>
              <p className="text-xs text-zinc-500 mt-1">Compliance Analytics</p>
            </div>
            <nav className="flex flex-col gap-1">
              <a
                href="/"
                className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7" /></svg>
                Sessions
              </a>
            </nav>
            <div className="mt-auto text-xs text-zinc-600">
              TreeHacks 2026
            </div>
          </aside>
          <main className="flex-1 ml-64 p-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

