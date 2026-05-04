# Spike: Hub Invite-Link Hardening

> Spike issue: [#457](https://github.com/xenophobed/Demi_Creative/issues/457) — under Epic [#437](https://github.com/xenophobed/Demi_Creative/issues/437) (Content Hub).

## What ships in v1 (#447)

`hub_groups.invite_token` is set when a private group is created, via:

```python
invite_token = secrets.token_urlsafe(16) if visibility == "private" else None
```

Properties of the v1 token:

- 16 url-safe random bytes (~22 base64 characters; entropy is ~128 bits — un-guessable in any practical attack).
- **Multi-use** — the same token works for every join attempt until the group is deleted.
- **No expiry** — never times out.
- **Stored in plaintext** on the row.
- **Validated by direct comparison** against `hub_groups.invite_token` in `GroupRepository.join_group`.
- The token is exposed once via the API response when the group is created. There is no separate `GET /groups/{id}/invite` endpoint in v1.

This is the simplest correct implementation: a child can paste a link to a friend, and the friend (with their parent) can join.

## Risks the v1 model accepts

| # | Risk | Severity (v1 audience) | Notes |
|---|---|---|---|
| R1 | A leaked link admits anyone forever | Medium | The owner has no way to rotate or revoke without recreating the group, which loses post history. |
| R2 | Brute-force enumeration | Negligible | 128 bits of entropy. Out of scope. |
| R3 | Server-side leak (DB dump, log line) | Medium | Token is plaintext on the row — anyone with DB access sees all active tokens. |
| R4 | Friend-of-friend chaining | Medium | A member can re-share the link to anyone. We have no per-member "who you invited" trail. |
| R5 | Stale links sitting in chats | Low–Medium | A token shared in a kids' chat in 2026 still works in 2027. |
| R6 | No accept-step / abuse signal | Medium | Posts arrive immediately on join — no admin review window for first-time posters. |

For v1's child-friendly, low-volume audience these are acceptable. The defining harm cases (PII leakage, unsafe content) are gated *separately* by the agent-persona snapshot (#447 / PRD §3.12.7) and the safety-check pipeline. Invite tokens only gate **who can post**, not **what reaches the public**.

## Recommendation for v2

Ship the changes below as one P1 story when the user volume crosses an internal threshold (suggest: when private groups > 1000 or when the first abuse report tied to a leaked link lands). They compose, but each is independently shippable.

### 1. Multiple tokens per group (token table) — **start here**

Move tokens out of `hub_groups` and into a new table:

```sql
CREATE TABLE hub_group_invites (
  invite_id     TEXT PRIMARY KEY,
  group_id      TEXT NOT NULL,
  token_hash    TEXT NOT NULL,        -- SHA-256, never plaintext
  created_by    TEXT NOT NULL,        -- user_id of inviter (R4 visibility)
  created_at    TEXT NOT NULL,
  expires_at    TEXT,                 -- NULL = no expiry
  max_uses      INTEGER,              -- NULL = multi-use
  use_count     INTEGER NOT NULL DEFAULT 0,
  revoked_at    TEXT,
  FOREIGN KEY(group_id) REFERENCES hub_groups(group_id) ON DELETE CASCADE
);
CREATE INDEX idx_hub_group_invites_token ON hub_group_invites(token_hash);
CREATE INDEX idx_hub_group_invites_group ON hub_group_invites(group_id);
```

This unblocks **all** of the controls below without further migrations.

### 2. Hash-at-rest

`token_hash = sha256(token).hex()` — the plaintext token is shown to the inviter once at creation time and never persisted. Eliminates R3.

Trade-off: a member who lost the link must ask the inviter (or an owner) to mint a new one. Acceptable; matches GitHub / GitLab invite UX.

### 3. Optional expiry (default 7 days for child accounts)

`expires_at` lets the owner cap how long a link survives. Default for child-owned groups: 7 days, with a UI toggle to extend. Mitigates R1, R5.

### 4. Optional one-time use

`max_uses` (NULL = multi-use; 1 = one-time). UI default for "send to a specific friend" → one-time; for "post in a class group chat" → multi-use. Mitigates R1, R4 partially.

### 5. Per-member invite trail (revoke chain)

`hub_group_memberships.invited_via_invite_id TEXT NULL` references the `hub_group_invites.invite_id` they used. Let an owner revoke an invite AND optionally cascade-remove the members who joined through it. Hardens R4.

### 6. Pending-membership review (orthogonal)

For groups where the owner wants final say (a school class), introduce a `role='pending'` state and require owner approval before the member can post. Matches existing moderation UX patterns. Tackles R6 without coupling to invite tokens.

## What NOT to do

- **HMAC tokens with no DB row.** Tempting because there's nothing to revoke against, but it makes revocation impossible without a denylist — which is a DB row anyway. Keep token rows.
- **Per-user invite codes.** A child sharing a personal code to a class chat would be a phishing surface against them. Keep invites bound to the group, not the inviter.
- **Email-based invites.** Out of scope for COPPA reasons; the platform deliberately does not surface email addresses in the social graph.

## Migration path from v1 to v2

Backfill is trivial:

```sql
INSERT INTO hub_group_invites (
  invite_id, group_id, token_hash, created_by, created_at, max_uses
)
SELECT
  hex(randomblob(16)),
  group_id,
  sha256_hex(invite_token),       -- one-time backfill helper
  created_by_user_id,
  created_at,
  NULL                            -- preserve v1 multi-use semantics
FROM hub_groups
WHERE visibility = 'private' AND invite_token IS NOT NULL;
```

Then drop `hub_groups.invite_token` in a follow-up migration after the v2 endpoints have been live for a release. **Do not** drop the column in the same PR as the table introduction — the rollback path matters.

## Decision

- **v1**: ship as-is in #447. Track the risks above explicitly here so reviewers know what we accepted.
- **v2**: file a follow-up P1 story when one of the trigger conditions lands (volume threshold, first abuse report). Suggested title: *"Move hub invite tokens to a hashed, optionally-expiring table"*. The contract test from #447 (token mismatch → PermissionError) carries forward unchanged because the public surface stays `?invite=<token>`.

## References

- v1 implementation: [`backend/src/services/database/group_repository.py`](../../backend/src/services/database/group_repository.py) (`create_group`, `join_group`)
- v1 token generation: [`secrets.token_urlsafe(16)`](https://docs.python.org/3/library/secrets.html#secrets.token_urlsafe)
- PRD: [§3.12 Content Hub](../product/PRD.md#312-content-hub--group-based-community-sharing-phase-2), specifically the "Out of Scope (Phase 2)" line *"Invite-link hardening (one-time use, expiry) — for v2"*.
