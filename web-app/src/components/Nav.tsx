"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/feature-phone", label: "Feature phone" },
  { href: "/judge-demo", label: "Two-user demo" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="flex items-center gap-1 border-b border-slate-200 px-4 py-2 md:px-8" aria-label="Preview screens">
      <span className="mr-4 font-semibold text-slate-900">WaveCellAI SMS</span>
      {TABS.map((t) => {
        const active = path === t.href;
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-full px-3 py-1 text-sm ${active ? "bg-teal-700 text-white" : "text-slate-700 hover:bg-slate-100"}`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
