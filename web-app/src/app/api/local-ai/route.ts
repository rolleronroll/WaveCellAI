// DISABLED: kept for future use. Needs a model host you run yourself (see
// backend/src/router/local_llm.py). Uncomment this file and the LOCAL_AI_* env vars
// to enable the Vercel proxy.
//
// import { NextRequest, NextResponse } from "next/server";
//
// export const runtime = "nodejs";
// export const maxDuration = 60;
//
// const SYSTEM =
//   "You are a travel assistant replying by SMS. Answer in under 150 characters, plain GSM-7 text, no emojis.";
//
// export async function POST(req: NextRequest) {
//   const base = process.env.LOCAL_AI_URL;
//   if (!base) {
//     return NextResponse.json({ error: "LOCAL_AI_URL not configured" }, { status: 500 });
//   }
//
//   let body: { prompt?: string; max_tokens?: number };
//   try {
//     body = await req.json();
//   } catch {
//     return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
//   }
//   const prompt = body.prompt?.trim();
//   if (!prompt) {
//     return NextResponse.json({ error: "prompt is required" }, { status: 400 });
//   }
//
//   const headers: Record<string, string> = { "Content-Type": "application/json" };
//   if (process.env.LOCAL_AI_TOKEN) {
//     headers.Authorization = `Bearer ${process.env.LOCAL_AI_TOKEN}`;
//   }
//
//   try {
//     const upstream = await fetch(`${base.replace(/\/$/, "")}/v1/chat/completions`, {
//       method: "POST",
//       headers,
//       signal: AbortSignal.timeout(55_000),
//       body: JSON.stringify({
//         model: process.env.LOCAL_AI_MODEL ?? "Ministral-8B-Instruct-2410-Q4_K_M.gguf",
//         messages: [
//           { role: "system", content: SYSTEM },
//           { role: "user", content: prompt },
//         ],
//         max_tokens: Math.min(body.max_tokens ?? 80, 200),
//         temperature: 0.2,
//       }),
//     });
//     if (!upstream.ok) {
//       return NextResponse.json({ error: `Model host returned ${upstream.status}` }, { status: 502 });
//     }
//     const data = await upstream.json();
//     const text: string = data.choices?.[0]?.message?.content?.trim() ?? "";
//     return NextResponse.json({ text, model: "ministral-8b-q4_k_m" });
//   } catch {
//     return NextResponse.json({ error: "Model host unreachable" }, { status: 504 });
//   }
// }

export {};