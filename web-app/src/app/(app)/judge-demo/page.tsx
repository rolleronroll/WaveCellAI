"use client";

import { useState } from "react";
import { simulateSms } from "@/lib/api-client";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const PHONE1 = "+8801712345678";
const LANGS = { en: "English", bn: "Bengali (Banglish)", hi: "Hindi (Hinglish)" } as const;
type Lang = keyof typeof LANGS;
type Msg = { from: "you" | "ai" | "guide" | "system"; text: string; meta?: string };
type Sms = { dir: "in" | "out"; text: string; meta?: string };
type Relay = { text: string; translated: boolean; note: string; septets?: number; bytes_used?: number; segments?: number; encoding?: string };

async function relay(text: string, target_lang: Lang, as_sms: boolean, footer = ""): Promise<Relay> {
  const res = await fetch(`${BASE}/api/demo/relay`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_lang, as_sms, footer }),
  });
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

const STEPS = [
  "Ask the AI a question. The answer stays on the website; no SMS is sent.",
  "Ask for a human guide. The message reaches User 1's phone as an SMS with a From: footer.",
  "Reply as User 1 on the phone. The reply appears in the web chat.",
  "Change a language. Messages are translated to each person's choice.",
];
const AI_Q = "Is there a beach in Cox's Bazar?";
const HUMAN_Q = "I need a human guide. My boat engine stopped near the island.";
const GUIDE_A = "Shanto thakun. Ami 20 minute-er moddhe nouka pathacchi.";

export default function JudgeDemo() {
  const [phone, setPhone] = useState("+14155550123");
  const [pass, setPass] = useState("demo1234");
  const [user, setUser] = useState<string | null>(null);
  const [lang2, setLang2] = useState<Lang>("en");
  const [lang1, setLang1] = useState<Lang>("bn");
  const [chat, setChat] = useState<Msg[]>([]);
  const [sms, setSms] = useState<Sms[]>([]);
  const [human, setHuman] = useState(false);
  const [input, setInput] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<number[]>([]);
  const mark = (n: number) => setDone((d) => (d.includes(n) ? d : [...d, n]));
  const say = (m: Msg) => setChat((c) => [...c, m]);

  async function send(text: string) {
    const t = text.trim();
    if (!t || busy) return;
    const me = user ?? phone;
    setUser(me);
    setInput("");
    say({ from: "you", text: t });
    setBusy(true);
    try {
      if (human || /human|local guide|real person/i.test(t)) {
        if (!human) {
          setHuman(true);
          say({ from: "system", text: "Connecting you to a local guide (User 1) by SMS." });
        }
        const r = await relay(t, lang1, true, me);
        setSms((s) => [...s, { dir: "in", text: r.text, meta: `${r.septets} chars, ${r.bytes_used} bytes, ${r.segments} SMS, ${r.encoding}` }]);
        say({ from: "system", text: `Delivered to User 1's feature phone as one SMS${r.note ? ` (${r.note})` : ""}.` });
        mark(2);
        if (r.translated) mark(4);
      } else {
        const r = await simulateSms(me, t);
        say({ from: "ai", text: r.body, meta: `answered by ${r.tier}, language ${r.lang}, no SMS sent` });
        mark(1);
      }
    } catch (e) {
      say({ from: "system", text: `Error: ${(e as Error).message}. Check that the backend is running.` });
    } finally {
      setBusy(false);
    }
  }

  async function guideSend(text: string) {
    const t = text.trim();
    if (!t || busy || !human) return;
    setReply("");
    setSms((s) => [...s, { dir: "out", text: t }]);
    setBusy(true);
    try {
      const r = await relay(t, lang2, false);
      say({ from: "guide", text: r.text, meta: r.translated ? `translated from ${LANGS[lang1]}, sent by SMS` : r.note });
      mark(3);
      if (r.translated) mark(4);
    } catch (e) {
      say({ from: "system", text: `Error: ${(e as Error).message}.` });
    } finally {
      setBusy(false);
    }
  }

  const act = [() => send(AI_Q), () => send(HUMAN_Q), () => guideSend(GUIDE_A), () => setLang2((l) => (l === "en" ? "hi" : "en"))];
  const pill = "rounded-full border border-slate-300 px-3 py-1 text-sm";
  const select = "rounded border border-slate-300 bg-white px-2 py-1 text-sm";

  return (
    <main className="mx-auto max-w-6xl p-4 text-slate-900 md:p-8">
      <h1 className="text-2xl font-semibold">Remote travel help, with a human in the loop</h1>
      <p className="mt-1 max-w-prose text-slate-600">
        A tourist on the website (User 2) asks an AI. When the AI is not enough, a local guide on a feature phone (User 1) answers by SMS. Logins here are mock; nothing is stored.
      </p>

      <ol className="mt-6 grid gap-2 md:grid-cols-2">
        {STEPS.map((s, i) => (
          <li key={i} className="flex items-start gap-3 rounded-lg border border-slate-200 p-3">
            <button
              onClick={act[i]}
              disabled={busy || (i === 2 && !human)}
              className="shrink-0 rounded bg-teal-700 px-3 py-1 text-sm text-white disabled:bg-slate-300"
            >
              {i === 3 ? "Switch" : "Try it"}
            </button>
            <span className="text-sm">
              {s} {done.includes(i + 1) && <b className="text-teal-700">Done.</b>}
              {i === 2 && !human && <span className="text-slate-500"> Do step 2 first.</span>}
            </span>
          </li>
        ))}
      </ol>

      <div className="mt-6 grid gap-6 md:grid-cols-[1fr_320px]">
        <section className="flex min-h-[420px] flex-col rounded-xl border border-slate-300">
          <header className="flex flex-wrap items-center gap-2 border-b border-slate-200 p-3">
            <b>User 2, website chat</b>
            {user ? (
              <>
                <span className="text-sm text-slate-600">{user}</span>
                <label className="ml-auto text-sm">My language <select className={select} value={lang2} onChange={(e) => setLang2(e.target.value as Lang)}>{Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                <button className={pill} onClick={() => { setUser(null); setChat([]); setSms([]); setHuman(false); setDone([]); }}>Log out</button>
              </>
            ) : (
              <span className="text-sm text-slate-500">Not logged in</span>
            )}
          </header>
          {!user ? (
            <div className="m-auto grid w-64 gap-2 p-6">
              <input className={select} value={phone} onChange={(e) => setPhone(e.target.value)} aria-label="Phone number" />
              <input className={select} type="password" value={pass} onChange={(e) => setPass(e.target.value)} aria-label="Password" />
              <button className="rounded bg-teal-700 py-1.5 text-white disabled:bg-slate-300" disabled={!phone || !pass} onClick={() => setUser(phone)}>Log in</button>
              <p className="text-xs text-slate-500">Prefilled mock login. Press Log in, or just use a step above.</p>
            </div>
          ) : (
            <>
              <div className="flex-1 space-y-2 overflow-y-auto p-3">
                {chat.length === 0 && <p className="text-sm text-slate-500">Ask anything, or press Try it in step 1.</p>}
                {chat.map((m, i) => (
                  <div key={i} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.from === "you" ? "ml-auto bg-teal-700 text-white" : m.from === "system" ? "bg-slate-100 text-slate-600" : m.from === "guide" ? "bg-amber-100" : "bg-slate-200"}`}>
                    {m.from === "guide" && <div className="font-medium">Local guide (User 1)</div>}
                    {m.text}
                    {m.meta && <div className="mt-1 text-xs opacity-70">{m.meta}</div>}
                  </div>
                ))}
              </div>
              <div className="flex gap-2 border-t border-slate-200 p-3">
                <input className={`${select} flex-1`} value={input} placeholder="Type a message" onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)} />
                <button className="rounded bg-teal-700 px-3 text-white disabled:bg-slate-300" disabled={busy} onClick={() => send(input)}>Send</button>
                <button className={pill} disabled={busy} onClick={() => send(HUMAN_Q)}>Ask a human guide</button>
              </div>
            </>
          )}
        </section>

        <aside className="rounded-[2rem] border-4 border-slate-800 bg-slate-900 p-3 text-slate-100">
          <div className="mb-2 text-center text-sm">User 1, feature phone <span className="text-slate-400">{PHONE1}</span></div>
          <label className="mb-2 block text-xs">Phone language <select className={`${select} text-slate-900`} value={lang1} onChange={(e) => setLang1(e.target.value as Lang)}>{Object.entries(LANGS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <div className="h-56 space-y-2 overflow-y-auto rounded bg-lime-100 p-2 text-sm text-slate-900">
            {sms.length === 0 && <p className="text-slate-500">No messages yet.</p>}
            {sms.map((m, i) => (
              <div key={i} className={m.dir === "out" ? "text-right" : ""}>
                <div className="inline-block whitespace-pre-wrap rounded bg-white/70 px-2 py-1 text-left">{m.text}</div>
                {m.meta && <div className="text-[11px] text-slate-600">{m.meta}</div>}
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-1">
            <input className={`${select} min-w-0 flex-1 text-slate-900`} disabled={!human} value={reply} placeholder={human ? "Type a reply" : "Waiting for a request"} onChange={(e) => setReply(e.target.value)} onKeyDown={(e) => e.key === "Enter" && guideSend(reply)} />
            <button className="rounded bg-teal-600 px-3 text-sm disabled:bg-slate-600" disabled={!human || busy} onClick={() => guideSend(reply)}>Send</button>
          </div>
        </aside>
      </div>
    </main>
  );
}
