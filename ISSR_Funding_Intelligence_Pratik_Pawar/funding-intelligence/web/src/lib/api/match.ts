import { ApiError, baseUrl } from "@/lib/api/client";
import type { MatchStreamEvent } from "@/lib/types";

export interface MatchProfileParams {
  profileText: string;
  k?: number;
  threshold?: number;
  status?: string | null;
  explain?: boolean;
  signal?: AbortSignal;
}

/**
 * Client-side call by design (see lib/api/client.ts) -- the AI Match view is
 * a genuine user interaction with a real wait, not something a Server
 * Component should pre-render.
 *
 * Streams `POST /api/match/stream` (newline-delimited JSON, see
 * api/routes/match.py and lib/types.ts's MatchStreamEvent) rather than
 * awaiting one atomic response: explaining each candidate is a sequential
 * local-LLM call, seconds apiece, measured at 30-45s typical and up to
 * ~100s if every one times out (matching/explain.py). Streaming can't make
 * that computation faster -- verified separately that parallelising the
 * calls doesn't help, this Ollama setup processes them one at a time
 * regardless -- but it means the ranked list and each explanation reach the
 * caller the moment they're ready instead of all at once at the end.
 *
 * No default fetch timeout exists, so callers should race this against
 * their own AbortController-driven timeout rather than assume one.
 */
export async function* streamMatchProfile({
  profileText,
  k = 10,
  threshold = 0,
  status = "open",
  explain = true,
  signal,
}: MatchProfileParams): AsyncGenerator<MatchStreamEvent> {
  const res = await fetch(`${baseUrl()}/api/match/stream`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_text: profileText, k, threshold, status, explain }),
    signal,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, body || res.statusText);
  }
  if (!res.body) {
    throw new ApiError(res.status, "Response had no body to stream.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (line) yield JSON.parse(line) as MatchStreamEvent;
    }
  }

  const trailing = buffer.trim();
  if (trailing) yield JSON.parse(trailing) as MatchStreamEvent;
}
