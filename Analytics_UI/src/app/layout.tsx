import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "Viper",
  description: "Post-operative compliance analysis dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen bg-[hsl(var(--background))] font-sans antialiased">
        <div className="flex min-h-screen">
          <aside className="w-64 border-r border-zinc-800/50 bg-zinc-950/80 backdrop-blur-xl p-6 flex flex-col gap-8 fixed h-full z-10">
            <div>
              <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">
                Viper
              </h1>
              <p className="text-xs text-zinc-500 mt-1">Compliance Analytics</p>
            </div>
            <nav className="flex flex-col gap-1">
              <a
                href="/"
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-zinc-300 hover:bg-white/5 hover:text-white transition-all duration-200"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                Procedures
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
