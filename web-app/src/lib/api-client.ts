const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type SimulateReply = {
  to: string;
  body: string;
  septets: number;
  bytes_used: number;
  segments: number;
  intent: string;
  tier: "template" | "small" | "claude";
  escalated: boolean;
  lang: string;
  reason: string;
  english_query: string | null;
  confidence: number | null;
  model: string | null;
};

export async function simulateSms(phone: string, message: string): Promise<SimulateReply> {
  const res = await fetch(`${BASE}/api/sms/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, message }),
  });
  if (!res.ok) {
    throw new Error(
      res.status === 429 ? "Too many messages. Wait a minute and try again." : `Backend returned ${res.status}`,
    );
  }
  return res.json();
}