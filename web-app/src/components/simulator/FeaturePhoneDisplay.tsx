"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";

export type Bubble = { from: "user" | "bot"; text: string };

type Props = {
  thread: Bubble[];
  draft: string;
  busy: boolean;
  onDraft: (value: string) => void;
  onSend: () => void;
};

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];

export default function FeaturePhoneDisplay({ thread, draft, busy, onDraft, onSend }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [thread, busy]);

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="mx-auto w-[300px] rounded-[2.5rem] border border-neutral-400 bg-neutral-200 p-5 shadow-md">
      <p className="mb-2 text-center text-xs text-neutral-500">TravelAI SMS</p>

      <div className="h-[260px] overflow-y-auto rounded-md border border-emerald-700/40 bg-emerald-100 p-2 font-mono text-[13px] leading-snug text-emerald-950">
        {thread.length === 0 && <p className="opacity-60">Text a question to start.</p>}
        {thread.map((m, i) => (
          <p key={i} className="mb-2">
            <span className="opacity-60">{m.from === "user" ? "You: " : "Bot: "}</span>
            {m.text}
          </p>
        ))}
        {busy && <p className="animate-pulse opacity-70">Bot is typing...</p>}
        <div ref={endRef} />
      </div>

      <div className="mt-2 flex items-center gap-2">
        <input
          value={draft}
          maxLength={160}
          onChange={(e) => onDraft(e.target.value)}
          onKeyDown={onKey}
          placeholder="Type an SMS"
          className="min-w-0 flex-1 rounded-md border border-emerald-700/40 bg-emerald-100 px-2 py-1 font-mono text-[13px] text-emerald-950 outline-none placeholder:text-emerald-900/50"
        />
        <button
          onClick={onSend}
          disabled={busy || !draft.trim()}
          className="rounded-md bg-neutral-700 px-3 py-1 text-xs text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
      <p className="mt-1 text-right text-[11px] text-neutral-500">{draft.length}/160</p>

      <div className="mt-3 grid grid-cols-3 gap-2" aria-hidden="true">
        {KEYS.map((k) => (
          <div key={k} className="rounded-md border border-neutral-400 bg-neutral-100 py-1.5 text-center text-sm text-neutral-600">
            {k}
          </div>
        ))}
      </div>
    </div>
  );
}

