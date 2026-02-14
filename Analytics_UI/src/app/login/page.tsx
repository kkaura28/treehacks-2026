"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    // Demo: accept any credentials
    setTimeout(() => {
      localStorage.setItem("viper_auth", "1");
      router.push("/");
    }, 800);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[hsl(220,20%,3%)] relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(45,212,191,0.06),transparent_70%)]" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-teal-500/[0.07] to-transparent rounded-full blur-3xl" />
      <div className="absolute bottom-0 right-0 w-[600px] h-[300px] bg-gradient-to-t from-cyan-500/[0.04] to-transparent rounded-full blur-3xl" />

      <div className="relative w-full max-w-md px-4 animate-scale-in">
        <div className="gradient-border p-8 glow-teal">
          {/* Logo */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-teal-400 to-cyan-400 bg-clip-text text-transparent">
              Viper
            </h1>
            <p className="text-sm text-zinc-500 mt-2">Surgical Compliance Analytics</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider font-medium block mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="surgeon@hospital.org"
                className="w-full px-4 py-2.5 bg-white/[0.03] border border-zinc-800/50 rounded-xl text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 transition-all duration-200"
                required
              />
            </div>
            <div>
              <label className="text-xs text-zinc-500 uppercase tracking-wider font-medium block mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-2.5 bg-white/[0.03] border border-zinc-800/50 rounded-xl text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 transition-all duration-200"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-white text-sm font-medium rounded-xl transition-all duration-200 disabled:opacity-50 mt-2 shadow-lg shadow-teal-500/20"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-zinc-800/30">
            <p className="text-xs text-zinc-600 text-center">
              Hospital-specific access &middot; HIPAA compliant
            </p>
          </div>
        </div>

        <p className="text-xs text-zinc-700 text-center mt-6">
          TreeHacks 2026 &middot; Demo Mode
        </p>
      </div>
    </div>
  );
}

