/**
 * Base fetch wrapper. Two separate base-URL env vars on purpose:
 *
 * - API_BASE_URL: server-only, never reaches the client bundle. Used by
 *   Server Component fetches, which talk to the API container directly over
 *   the Docker network (e.g. http://api:8000) -- no CORS involved, since
 *   it's not a browser request.
 * - NEXT_PUBLIC_API_BASE_URL: inlined into the client bundle at build time.
 *   Used by the few genuinely client-side calls (the AI Match view's submit
 *   action) -- these DO cross origins in the browser, so the API's
 *   API_CORS_ORIGINS must include this app's origin.
 *
 * Conflating the two is the standard Next.js footgun this avoids: using the
 * Docker-internal URL from the browser would simply fail to resolve.
 */
export function baseUrl(): string {
  if (typeof window === "undefined") {
    return (
      process.env.API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8000"
    );
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl()}${path}`, {
    // The corpus changes as ingestion runs; every route here is
    // database-backed, not content that benefits from build-time caching.
    // Without this, Next tries to statically prerender Server Component
    // fetches and serves one build-time snapshot to every visitor forever.
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, body || res.statusText);
  }

  return res.json() as Promise<T>;
}
