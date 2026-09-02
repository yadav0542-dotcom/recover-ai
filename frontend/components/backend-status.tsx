"use client";

import { useEffect, useState } from "react";

import { getBackendHealth } from "@/lib/api";

type ConnectionState = "checking" | "connected" | "unavailable";

export function BackendStatus() {
  const [state, setState] = useState<ConnectionState>("checking");

  useEffect(() => {
    getBackendHealth().then(
      () => setState("connected"),
      () => setState("unavailable"),
    );
  }, []);

  const content = {
    checking: { label: "Checking backend…", tone: "bg-amber-50 text-amber-700 ring-amber-200" },
    connected: { label: "Backend Connected", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
    unavailable: { label: "Backend Unavailable", tone: "bg-rose-50 text-rose-700 ring-rose-200" },
  }[state];

  return (
    <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium ring-1 ${content.tone}`}>
      <span className="h-2 w-2 rounded-full bg-current" />
      {content.label}
    </div>
  );
}
