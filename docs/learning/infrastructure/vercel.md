# Vercel — Frontend Hosting

**Config**: `frontend/vercel.json` | **Build**: `frontend/vite.config.ts`

## What This File Does

**Explorer**: Vercel is like a bulletin board that shows our app to the world. It takes all our React code, turns it into a fast website, and puts copies on servers all around the globe so kids everywhere can load it quickly.

**Maker**: Vercel hosts the React SPA as static files on a global CDN. The Vite build outputs HTML/CSS/JS bundles to `dist/`, which Vercel serves with edge caching. SPA routing is handled via a `vercel.json` rewrite that sends all paths to `index.html`, letting React Router handle client-side navigation.

## How It Works

### Build and Deploy
```
1. Developer runs: vercel --prod
2. Vercel uploads source files → runs: npm run build (tsc -b && vite build)
3. Vite bundles 2335 modules → outputs to dist/ (~1 MB total)
4. Vercel distributes static files to CDN edge nodes worldwide
5. DNS: creative.demi-app.com → nearest Vercel edge node
```

### SPA Routing (`vercel.json`)
```json
{ "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
```
This is critical: without it, visiting `creative.demi-app.com/interactive` would return a 404 because there's no `interactive.html` file. The rewrite sends all paths to `index.html`, where React Router reads the URL and renders the correct page.

### Preview vs Production
- **Preview**: `vercel` (no `--prod`) → creates a unique URL like `frontend-abc123.vercel.app` for testing
- **Production**: `vercel --prod` → deploys to `creative.demi-app.com` and `frontend-tau-drab-78.vercel.app`

## Key Concepts

**SPA (Single Page Application)**: The entire app is one HTML page. When you navigate between pages, JavaScript swaps out content without reloading — much faster than traditional websites. The trade-off: the initial load downloads more code upfront.

**CDN (Content Delivery Network)**: Your website cached on servers in dozens of cities worldwide. A user in Shanghai gets files from a nearby Asian server; a user in London gets them from Europe. Reduces load time from seconds to milliseconds.

**Static Hosting**: The server just sends pre-built files — no server-side code runs. All the "thinking" happens in the user's browser (frontend) or by calling the Railway backend (API). This is why Vercel hosting is fast and cheap.

## Connections

- **Build input**: `frontend/src/` (React/TypeScript source) → `frontend/dist/` (built output)
- **API calls**: Frontend JavaScript calls `Railway backend URL/api/v1/...` for all data
- **Auth**: Frontend uses `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (build-time env vars)
- **Custom domain**: `creative.demi-app.com` points to Vercel via DNS

## Thinking Question

Our SPA bundles everything into one initial download (~1 MB). A kid on a slow mobile connection might wait 5+ seconds for the first load. How would you split the code so the homepage loads fast and other pages load on demand? Look up: "code splitting" and "lazy loading" in React/Vite.
