# Supabase — Authentication and Database

**Config**: `supabase/config.toml` | **Auth**: `backend/src/services/supabase_auth.py` | **Client**: `frontend/src/lib/supabase.ts`

## What This File Does

**Explorer**: Supabase is like the school office — it keeps track of who everyone is (authentication), stores all the stories and drawings in filing cabinets (database), and sends permission slips via email (confirmation emails).

**Maker**: Supabase provides three services: PostgreSQL database (replacing SQLite in production), JWT-based authentication (replacing our legacy custom tokens), and SMTP email delivery via Resend. The backend validates Supabase JWTs using JWKS (ES256) with HS256 fallback.

## How Authentication Works

### Registration Flow
```
1. User fills form → frontend calls supabase.auth.signUp()
2. Supabase creates user → sends confirmation email via Resend SMTP
3. User clicks email link → browser loads app with ?code=xxx
4. Supabase SDK exchanges code → INITIAL_SESSION event fires
5. AuthProvider catches event → calls GET /users/me with JWT
6. Backend validates JWT → auto-creates local user row → returns profile
7. Frontend stores token in Zustand → redirects to home
```

### JWT Validation (Backend)
The backend tries two methods in order:
1. **ES256 (JWKS)** — Fetches public keys from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, matches `kid` from JWT header, verifies with elliptic curve cryptography
2. **HS256 fallback** — Uses `SUPABASE_JWT_SECRET` for symmetric verification (older Supabase projects)

### Email Configuration
- **SMTP**: `smtp.resend.com` on port 465
- **Sender**: `noreply@demi-app.com` ("Kids Creative Workshop")
- **Template**: Custom branded HTML at `supabase/templates/confirmation.html`
- **Confirmations required**: Yes (`enable_confirmations = true`)

## Key Concepts

**JWT (JSON Web Token)**: A digitally signed token that proves "I am user X." The frontend sends it with every API request. The backend verifies the signature without calling Supabase — the math alone proves it's genuine.

**JWKS (JSON Web Key Set)**: A public endpoint that serves the cryptographic keys needed to verify JWTs. Like a locksmith publishing their key templates — anyone can verify a lock was made by them, but only they can make new keys.

**ES256 vs HS256**: Two ways to sign tokens. ES256 uses a public/private key pair (asymmetric — more secure, keys fetched via JWKS). HS256 uses a shared secret (symmetric — simpler but the secret must be distributed).

**Dual-Mode Auth**: The system supports both Supabase auth and legacy custom tokens simultaneously. If Supabase JWT validation fails, it falls back to the old token system. This enabled a zero-downtime migration.

## Connections

- **Backend**: `supabase_auth.py` validates JWTs → `api/deps.py` uses it in `get_current_user`
- **Frontend**: `lib/supabase.ts` creates the client → `AuthProvider.tsx` listens for auth events → `authService.ts` coordinates login/register
- **Config**: `supabase/config.toml` controls auth settings, email templates, redirect URLs
- **SMTP**: Resend API key stored as `RESEND_API_KEY` env var on Supabase

## Thinking Question

We validate JWTs locally using JWKS public keys — we never call Supabase to check "is this token still valid?" What happens if a user is banned or deletes their account? Their existing JWT is still cryptographically valid until it expires (1 hour). How would you handle immediate token revocation? Think about: token blacklists, short expiry times, and the trade-off between security and performance.
