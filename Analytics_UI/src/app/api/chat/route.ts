import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { messages, patientContext } = await req.json();

  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: "GEMINI_API_KEY not set" }, { status: 500 });
  }

  const systemPrompt = `You are a rapid pre-op briefing assistant. A surgeon needs fast answers before scrubbing in.

Patient:
${patientContext}

Rules:
- MAX 2-3 sentences per response. Be terse. No filler.
- Lead with the most critical info. Bullet points over paragraphs.
- Use standard medical shorthand (y/o, PMHx, Hx, NKDA, etc.)
- First message: one-liner on who they are, then the top 2-3 things to watch out for.
- Only elaborate if explicitly asked.`;

  const geminiMessages = messages.map((m: { role: string; content: string }) => ({
    role: m.role === "user" ? "user" : "model",
    parts: [{ text: m.content }],
  }));

  try {
    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: systemPrompt }] },
          contents: geminiMessages,
        }),
      }
    );

    if (!res.ok) {
      const err = await res.text();
      console.error("Gemini API error:", err);
      return NextResponse.json({ error: "Gemini API error" }, { status: 502 });
    }

    const data = await res.json();
    const text =
      data.candidates?.[0]?.content?.parts?.[0]?.text ||
      "I wasn't able to generate a response. Please try again.";

    return NextResponse.json({ content: text });
  } catch (e) {
    console.error("Chat API error:", e);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}

