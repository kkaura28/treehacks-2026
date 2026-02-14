"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    const isAuthed = localStorage.getItem("viper_auth") === "1";
    if (!isAuthed && pathname !== "/login") {
      router.replace("/login");
    } else {
      setAuthed(isAuthed || pathname === "/login");
    }
  }, [pathname, router]);

  if (authed === null) {
    return (
      <div className="min-h-screen bg-[hsl(220,20%,3%)] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}

