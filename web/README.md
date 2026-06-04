# Anchor web — the AI solutions consultant front-end

A Next.js (App Router) + Tailwind front-end for the landing-page consultant. It
calls the FastAPI backend **directly from the browser over CORS** (no proxy), so
per-IP rate limiting on the backend keeps working and SSE streams cleanly.

## Run it

```bash
# 1. Start the backend (from anchor/), keyless is fine:
#    LLM_PROVIDER=fake make run            # FastAPI on :8000

# 2. Start the front-end:
cd web
cp .env.example .env.local                 # NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm install
npm run dev                                # http://localhost:3000
```

Submit a problem in the central prompt → watch the staged reasoning (SSE) →
read the matched services, solution sketch, timeline, proof, and lead-capture CTA.

## Test / build

```bash
npm run test     # Vitest component tests (keyless, no backend needed)
npm run build    # production build
```

## Deploy

Front-end on Vercel, backend on Railway/Fly/Render. Set:

- Front-end: `NEXT_PUBLIC_API_BASE` → your backend origin.
- Backend: `CORS_ALLOW_ORIGINS` → your Vercel origin (not `*`).

The existing vanilla-JS portfolio + Nimbus widget stay served by FastAPI and are
linked from this page as a "deployed example."
