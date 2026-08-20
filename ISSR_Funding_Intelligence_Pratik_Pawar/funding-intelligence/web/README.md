# ISSR Funding Intelligence — Web Frontend

Next.js (App Router) frontend for the ISSR Funding Intelligence project. Layout follows [simpler.grants.gov](https://simpler.grants.gov) (dense results table, faceted sidebar filters); theme follows [issr.ua.edu](https://issr.ua.edu) (University of Alabama crimson `#9E1B32`).

Runs as its own server, separate from the FastAPI backend (`../src/foa_pipeline/`) — see the root `README.md`'s "Run the Web Frontend" section for the full setup, and the repo's frontend-rewrite plan for the phased build-out (`/opportunities` table + facets → detail view → AI Match → Tags dashboard).

## Development

```bash
npm install
cp .env.example .env.local   # first time only; defaults assume the API is on :8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Requires the API server running (`make serve` from the repo root) to have data to show.

## Stack

- **Next.js** (App Router, TypeScript) — Server Components fetch the API server-to-server (`API_BASE_URL`); the one genuinely client-side view (AI Match) uses `NEXT_PUBLIC_API_BASE_URL` — see `src/lib/api/client.ts` for why there are two.
- **Tailwind CSS v4** + **shadcn/ui** (Radix primitives) — ISSR theme tokens in `src/app/globals.css`.
- **lucide-react** for icons, **next-themes** for dark mode, **next/font/google** (Montserrat + Inter) for typography — a free equivalent to ISSR's actual (paid, Adobe Typekit) Proxima Nova.

## Build / Docker

```bash
npm run build   # requires output: 'standalone' in next.config.ts, already set
```

`Dockerfile` is a multi-stage build feeding `docker-compose.yml`'s `web` service at the repo root — `docker compose up --build` runs both the API and this frontend together.
