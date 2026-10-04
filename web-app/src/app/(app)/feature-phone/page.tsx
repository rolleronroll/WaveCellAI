// Retro Feature Phone Dual-View Simulator Page

"use client";

import { useState } from "react";
import FeaturePhoneDisplay, { type Bubble } from "@/components/simulator/FeaturePhoneDisplay";
import { simulateSms, type SimulateReply } from "@/lib/api-client";

const DEMO_PHONE = "+8801712345678";

const SAMPLES = [
  { label: "Banglish", text: "cox bazar e beach ache?" },
  { label: "Hinglish", text: "dhaka se cox bazar bus kab hai, 8 baje ke baad" },
  { label: "SOS", text: "SOS bachao amar boat dube jacche" },
  { label: "English", text: "where can I exchange money" },
];

const LANG_NAME: Record<string, string> = { en: "English", bn: "Bengali / Banglish", hi: "Hindi / Hinglish" };
const TIER_NAME: Record<string, string> = {
  template: "Template (no model call)",
  small: "Small model (Gemini)",
  claude: "Claude fallback",
};

export default function MockPhonePage() {
  const [thread, setThread] = useState<Bubble[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<SimulateReply | null>(null);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    setError(null);
    setBusy(true);
    setDraft("");
    setThread((t) => [...t, { from: "user", text }]);
    try {
      const r = await simulateSms(DEMO_PHONE, text);
      setThread((t) => [...t, { from: "bot", text: r.body }]);
      setLast(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const rows: [string, string][] = last
    ? [
        ["Language", LANG_NAME[last.lang] ?? last.lang],
        ["Intent", last.intent],
        ["Answered by", TIER_NAME[last.tier] ?? last.tier],
        ["Model", last.model ?? "none"],
        ["Confidence", last.confidence === null ? "n/a" : last.confidence.toFixed(2)],
        ["English query", last.english_query ?? "same as input"],
        ["Routing note", last.reason],
      ]
    : [];

  return (
    <main className="mx-auto grid max-w-5xl gap-8 p-6 md:grid-cols-[320px_1fr]">
      <FeaturePhoneDisplay thread={thread} draft={draft} busy={busy} onDraft={setDraft} onSend={send} />

      <section className="space-y-4">
        <div>
          <h1 className="text-xl font-medium">Feature phone simulator</h1>
          <p className="text-sm text-neutral-500">
            Every reply is plain GSM-7 text that fits one 160-character SMS.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <button
              key={s.label}
              onClick={() => setDraft(s.text)}
              className="rounded-md border border-neutral-300 px-3 py-1 text-sm hover:bg-neutral-100"
            >
              {s.label}
            </button>
          ))}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        {last ? (
          <>
            <div className="grid grid-cols-3 gap-3">
              {[
                ["Septets", `${last.septets} / 160`],
                ["Bytes sent", String(last.bytes_used)],
                ["Segments", String(last.segments)],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-neutral-100 p-3">
                  <p className="text-xs text-neutral-500">{label}</p>
                  <p className="text-2xl font-medium">{value}</p>
                </div>
              ))}
            </div>
            <dl className="divide-y divide-neutral-200 rounded-lg border border-neutral-200 text-sm">
              {rows.map(([k, v]) => (
                <div key={k} className="flex gap-4 px-3 py-2">
                  <dt className="w-32 shrink-0 text-neutral-500">{k}</dt>
                  <dd className="min-w-0 break-words">{v}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : (
          <p className="text-sm text-neutral-500">Send a message to see how the backend handled it.</p>
        )}
      </section>
    </main>
  );
}