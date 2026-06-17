# Voice Launch Prerequisites — OpenAI Realtime Cutover

> **Audience**: operator on call for the v2 voice-first launch. You are flipping `REALTIME_VOICE_PROVIDER=openai` in production. Work this document top to bottom before turning the switch. Section 8 is a single-page checklist you can print and tick off.

This document covers the six prerequisites from [PRD §3.16.8 — Launch Prerequisites](../product/PRD.md#3168-launch-prerequisites-added-in-v2-cutover) plus a decision tree for the ZDR-denial contingency. It is intentionally voice-specific; broader deployment lives in [ops.md](ops.md).

**Related issues**: #605 (epic), #647 (WebRTC transport), #648 (cost telemetry), #650 (ElevenLabs fallback spike), #655 (tool versioning), #657 (broker integration), #658 (tool-calls glue).

---

## Section 1: ZDR Enrollment

### What ZDR is
**Zero Data Retention (ZDR)** is an OpenAI org-level setting that disables the default 30-day prompt/response retention window. With ZDR enabled, OpenAI does not persist any request or response data — including voice audio, transcripts, and tool-call payloads — beyond what is needed for the live API call.

### Why we require it
OpenAI's [Under-18 API Guidance](https://platform.openai.com/docs/guides/under-18-usage) requires ZDR before the API can be used to process the data of users under 13. Our 3-5 and 6-8 cohorts are squarely in that bucket. Without ZDR, we cannot legally route those age bands through `REALTIME_VOICE_PROVIDER=openai` in production.

### How to request enrollment
ZDR is **not self-serve**. The operator must contact OpenAI directly.

1. Log into the OpenAI org dashboard as an owner.
2. Open a support request via `https://help.openai.com/` → "Submit a request" → category "Privacy and data".
3. Sales/Trust & Safety usually replies within 3–10 business days. Timeline varies; treat anything beyond two weeks as "denied or stalled" and trigger the contingency in Section 7.

### What to say in the request
A short, specific template. Copy and adapt:

> Hello — we operate **Kids Creative Workshop**, a COPPA-aligned creative platform for children aged 3–12. We use OpenAI Realtime API (`gpt-realtime-mini` default, `gpt-realtime-2` escalation) for a two-way spoken conversation feature ("Talk to Buddy"). All audio passes through a fail-closed content safety pipeline (threshold 0.85–0.90 per age band) before any TTS output reaches the child. Raw audio bytes are never persisted to our disk. We need **Zero Data Retention** enrolled on org `<ORG_ID>` to comply with OpenAI's Under-18 API Guidance for our under-13 cohort. We can share our DPA, safety pipeline architecture, and consent flow on request.

Attach: link to our public privacy policy, link to the parent consent screen (`ParentConsentGate` with `kind="voice_conversation"`), and our DPA if signed.

### Expected timeline
- **Median**: 5–10 business days from first reply to enrollment confirmed.
- **Worst case observed in industry reports**: 4–6 weeks for orgs with no prior enterprise relationship.
- ZDR enrollment is per-org, not per-project. Once enrolled, all downstream Realtime API traffic is ZDR by default — no per-request flag needed.

### What to do if denied
See [Section 7: ZDR Contingency](#section-7-zdr-contingency-decision-tree) for the three documented paths.

---

## Section 2: Cost Ceiling

### Why the cap matters
OpenAI Realtime is billed per audio-minute. A single runaway client (browser tab pinned open with VAD active overnight) can burn the monthly budget in hours. The monthly org-level cap is the **last line of defense** — application quota (§3.9.1) is the first.

### Worked example
Assumptions for a soft-launch tier:

| Variable | Value |
|---|---|
| Active users | 100 |
| Avg voice minutes / user / day | 20 |
| Rate (gpt-realtime-mini, cached) | $0.075 / min |
| Days / month | 30 |

```
100 users × 20 min/day × 30 days × $0.075/min = $4,500 / month
```

Round up for headroom on `gpt-realtime-2` escalations and unexpected spikes:

```
$4,500 × 1.4 = $6,300 → set monthly cap to $6,500
```

For a 1,000-user beta, scale linearly: `$45,000 × 1.4 ≈ $65,000/mo`. For 10,000 users at this profile the monthly cap reaches **$650K/mo at full uncached rates** — at that scale, negotiate enterprise pricing with OpenAI before launch.

### How to set the cap in the OpenAI dashboard
1. OpenAI dashboard → **Settings** → **Billing** → **Limits**.
2. Set **Monthly usage limit** to the computed cap (e.g. `$6,500`).
3. Set **Email notification threshold** to 80% of cap (e.g. `$5,200`).
4. Save. OpenAI emails the org owner at the threshold and hard-stops the API at the limit.

Reference: [OpenAI usage limits docs](https://platform.openai.com/docs/guides/production-best-practices#manage-rate-limits).

### Application-level alerting + auto-failover
The dashboard cap is the external hard limit. We also want internal warning + graceful degradation **before** the OpenAI hard-stop. This is the surface owned by **#648 (cost telemetry + tier selection)**:

- Environment variable: `OPENAI_REALTIME_MONTHLY_CAP_USD=6500` (mirrors the dashboard value).
- Per-session cost estimate populated into `voice_sessions.cost_estimate_usd` (column added in #648).
- Daily rollup job aggregates org-month-to-date spend; emits an alert at **80% of cap** (warn) and triggers auto-failover to `REALTIME_VOICE_PROVIDER=hybrid` at **100%**.
- Auto-failover writes to a feature flag (not the env var directly) so the process does not need to restart; provider selection is re-evaluated per session.

> **Status**: #648 is the implementation surface. Until #648 lands, treat the OpenAI dashboard cap as the only enforcement and monitor the billing email manually. **Do not flip `=openai` to 100% of traffic without #648 in place.**

---

## Section 3: Fallback Validation

### Why we drill the fallback
`REALTIME_VOICE_PROVIDER=hybrid` (Whisper + Claude + ElevenLabs) is the documented rollback if OpenAI Realtime misbehaves under load, if ZDR enrollment lapses, or if the OpenAI org hits its cap. The fallback only works if it has been exercised in production-shaped infrastructure. **Smoke-test the fallback in production before flipping the primary path to `=openai`.**

### Smoke-test procedure
Run this once on the production backend (Railway in our deployment, see [ops.md §3](ops.md)) on a quiet day, with one tester on `/my-agent`:

```bash
# 1. On Railway, set the env var for the backend service.
railway variables --set REALTIME_VOICE_PROVIDER=hybrid

# 2. Restart the backend process. (Railway restarts on env change automatically;
#    verify the new env value in the latest deployment logs.)
railway logs --service kids-creative-backend | grep REALTIME_VOICE_PROVIDER

# 3. From a browser logged in as a test parent with a child profile that has
#    both microphone_consent and voice_conversation_consent set:
#    - Navigate to /my-agent
#    - Tap "Start Talking" in the AgentChatPanel header
#    - Speak: "Hi buddy, what's your favourite story?"
#    - Confirm: buddy speaks back within ~2.5s, transcript appears in chat

# 4. Verify the provider in the broker log:
railway logs --service kids-creative-backend | grep -E "provider=hybrid|HybridRealtimeVoiceProvider"

# 5. Roll forward to OpenAI:
railway variables --set REALTIME_VOICE_PROVIDER=openai

# 6. Confirm OpenAI path serves a session end-to-end before declaring the
#    fallback drill complete.
```

### Propagation timing
- **Env var flip → effective**: one process restart cycle (~30s on Railway).
- **Frontend impact**: none. The frontend hits the same `/api/v1/me/agent/voice/session` endpoint; the backend resolves the provider per session.
- **Existing sessions**: not migrated. In-flight sessions continue on their original provider until they end normally. New sessions pick up the new provider.

### Fallback chain (built into the resolver)
Source: [`backend/src/services/realtime_voice_service.py`](../../backend/src/services/realtime_voice_service.py) lines 1160-1195, function `resolve_realtime_provider`.

```
REALTIME_VOICE_PROVIDER=openai
    └─ if OPENAI_API_KEY missing → ValueError at startup (fail-fast)
       (operator must set OPENAI_API_KEY or switch the env var)

REALTIME_VOICE_PROVIDER=hybrid (default)
    └─ HybridRealtimeVoiceProvider
       ├─ OPENAI_API_KEY present  → real Whisper STT
       ├─ ANTHROPIC_API_KEY present → real Claude
       ├─ ELEVENLABS_API_KEY present → real ElevenLabs TTS
       └─ any key missing → that stage degrades to mock; broker stays up

REALTIME_VOICE_PROVIDER=mock
    └─ MockRealtimeVoiceProvider (test / dev only — never in prod)
```

The hybrid path is designed so partial credential outages do not take the buddy offline. The mock path is for dev and contract tests only — production should hard-fail if `=mock` is ever set.

---

## Section 4: Telemetry Verification

### Dashboards that must be live
| Dashboard | Owner | Surface | Status |
|---|---|---|---|
| Voice latency (p50/p95 first-audio-ms) | Ops dashboard | session_end events | **Required at launch** (#657 emits the data; #609 wires the Parent Dashboard view) |
| Voice cost (per-session + monthly rollup) | Billing dashboard | `voice_sessions.cost_estimate_usd` | **Required at launch** (#648 populates the column) |
| Provider error rate | Ops dashboard | structured logs `voice_session_end{provider, error_code}` | **Required at launch** (#648 instruments the field) |
| Parent Dashboard voice tile | Parent UI | session_end forwarded to Phase D | **Phase D (#609) — not blocking launch** |

### Alerts that must fire
| Metric | Threshold | Action |
|---|---|---|
| `first_audio_ms` p95 over 5 min | > 2,500 ms | Page on-call (UX-degraded) |
| `first_audio_ms` p95 over 5 min | > 4,000 ms | Auto-failover candidate — investigate or flip env to hybrid |
| Monthly org spend | > 80% of `OPENAI_REALTIME_MONTHLY_CAP_USD` | Warning email + Slack notification |
| Monthly org spend | > 100% of cap | Auto-failover to hybrid (via #648 feature flag) |
| Provider error rate over 15 min | > 5% of sessions | Page on-call (provider-degraded) |

### Where the data comes from
- **`first_audio_ms`** field is emitted in the `session_end` WebSocket event by the broker. See [`backend/src/api/routes/voice_realtime.py`](../../backend/src/api/routes/voice_realtime.py) line 741. The field was added under #657.
- **`voice_session_end`** structured log line (provider, duration, cost estimate, error code) is emitted by the broker's `finally` block. The cost estimate column is populated under #648.
- The `voice_sessions` row terminal state is written by `voice_session_repo.end_session(...)` at line 743 of the same file.

> **Operator action**: before launch, confirm the latency and cost panels show non-zero data from at least one real test session. If the panel is blank but logs show events, the wiring between log shipper and dashboard is broken — fix that first.

---

## Section 5: Safety Verification

### Contract tests that gate ship
All ten must be green on `main` before flipping `=openai`:

| Test | File | What it locks |
|---|---|---|
| `test_voice_safety_pre_tts_contract` | `backend/tests/contracts/test_voice_safety_pre_tts_contract.py` | Per-utterance + per-reply safety gates fail-closed before audio reaches the client |
| `test_openai_realtime_provider_contract` | `backend/tests/contracts/test_openai_realtime_provider_contract.py` | OpenAI provider conforms to the `RealtimeVoiceProvider` interface |
| `test_voice_broker_openai_provider_contract` | `backend/tests/contracts/test_voice_broker_openai_provider_contract.py` | Broker correctly routes OpenAI provider events end-to-end |
| `test_voice_function_calling_contract` | `backend/tests/contracts/test_voice_function_calling_contract.py` | Realtime function-calling envelope matches what the tool layer expects |
| `test_launch_flow_voice_text_parity_contract` | `backend/tests/contracts/test_launch_flow_voice_text_parity_contract.py` | `launch_flow` handoff behaves identically from voice and text entry |
| `test_voice_tool_calls_glue_contract` | `backend/tests/contracts/test_voice_tool_calls_glue_contract.py` | Tool calls from #655 actually fire through the #657 broker |
| `test_voice_safety_fallback_contract` | `backend/tests/contracts/test_voice_safety_fallback_contract.py` *(#608)* | Failing safety REPLACES the reply with the fallback; safety MCP exceptions fail closed; per-age threshold parity |
| `test_voice_safety_review_specialist_contract` | `backend/tests/contracts/test_voice_safety_review_specialist_contract.py` *(#608)* | Heavier safety-review specialist fires on borderline content; specialist rejection / crash both fail closed |
| `test_voice_enabled_skills_contract` | `backend/tests/contracts/test_voice_enabled_skills_contract.py` *(#608)* | `enabled_skills` refusal at token mint + tool-set filter before `session.update` (defense in depth) |
| `test_voice_token_expired_contract` | `backend/tests/contracts/test_voice_token_expired_contract.py` *(#608)* | Expired JWT surfaces as `auth_failed` over WS handshake (consistent with bad/replayed token paths) |

Run locally:
```bash
cd backend
python -m pytest tests/contracts/test_voice_*_contract.py tests/contracts/test_openai_realtime_provider_contract.py tests/contracts/test_launch_flow_voice_text_parity_contract.py -v
```

> **Status note**: as of writing, the glue test for #658 is on `main`. The four #608 tests landed alongside this update.

### Manual safety smoke checklist
Run with a test parent + child profile (age 6-8 unless noted). Use the production frontend pointed at production backend. Each test should complete in under 2 minutes.

- [ ] **Pre-TTS safety gate fires.** Speak: *"Tell me a scary story with monsters and blood."* Expected: buddy redirects to an age-appropriate alternative ("How about a story about a brave fox?") and no scary audio is played. The `safety_block` event SHOULD NOT be visible to the child; the redirect is graceful.
- [ ] **Mid-session input gate fires on profanity in transcript.** Mid-conversation, speak a clearly inappropriate word. Expected: `safety_block` event emitted to the client, captioned briefly, session continues with the buddy gently steering back.
- [ ] **Tool-call recovery.** Trigger a tool call (e.g. "Let's make a story") and use a test build that injects an unknown tool name. Expected: handler returns an error envelope, model recovers, no broker crash.
- [ ] **Per-age threshold check.** Repeat the first test with a child profile aged 3-5. Expected: threshold is **0.90** (raised); the same prompt SHOULD be refused even more aggressively. Compare with age 9-12 (threshold 0.85) for a borderline-content prompt.
- [ ] **Audio-not-persisted invariant.** After the session ends, confirm only transcripts exist in `agent_chat_messages` and no audio files exist for the session in storage. Covered by contract tests, but spot-check on prod once.

### Per-age thresholds
From PRD §3.16.6:

| Age band | Safety threshold |
|---|---|
| 3-5 | 0.90 |
| 6-8 | 0.85 |
| 9-12 | 0.85 |

The threshold is enforced by `check_content_safety` (MCP tool, `mcp__safety-check__check_content_safety`) before any TTS output. Both the child's finalized utterance AND the buddy's reply are gated. Either failure emits a `safety_block` event and prevents audio from streaming.

---

## Section 6: Tool Versioning

### Why versioning matters
Realtime function-calling tool schemas are part of the API contract between the model and our backend. If we silently change a tool's schema, an in-flight realtime session built against the old schema can mis-call us. We pin the version and require new tool names for backward-incompatible changes.

### How the version is pinned
Source: [`backend/src/services/realtime_voice_tools.py`](../../backend/src/services/realtime_voice_tools.py) line 55.

```python
TOOL_VERSION: str = "1.0.0"
```

Every tool definition emitted to the realtime session carries this version field (lines 165, 185, 205, 235, 260, 286). The realtime session prompt includes the tool list verbatim, so the version travels implicitly with the schema.

### How to ship a backward-incompatible change
**Do NOT edit an existing tool's schema in a way that changes required fields, field types, or semantics.** Instead:

1. Define a new tool with a new name. Example: `launch_flow` → `launch_flow_v2`.
2. Keep the old tool registered for at least one release cycle so older client builds continue working.
3. Bump `TOOL_VERSION` (e.g. `1.0.0` → `1.1.0` for additive changes, `2.0.0` for the new tool family).
4. Update the realtime session prompt to prefer the new tool.
5. Watch the drift warnings (next subsection) to see when old-tool traffic drops to zero.
6. Remove the old tool only after drift is at zero for a full retention window.

Backward-compatible additions (a new optional field, a new tool name) bump the minor version. Removals or required-field changes bump the major version.

### Drift detection
`warn_on_version_drift(model_version)` is called whenever a tool-call payload arrives from the model. See [`backend/src/services/realtime_voice_tools.py`](../../backend/src/services/realtime_voice_tools.py) lines 58–70. It logs a warning if the model reports a tool version that does not match `TOOL_VERSION`. This is the canary for "we changed something we shouldn't have" or "a stale client is still talking to us."

Ship #655 lands this hook; #658 will exercise it end-to-end.

---

## Section 7: ZDR Contingency (Decision Tree)

If ZDR is denied or stalls past two weeks, OpenAI Realtime cannot legally serve our under-13 cohort. Three options exist. **Operator + legal decide; engineering implements.**

```
                    ┌────────────────────────────────┐
                    │ ZDR denied or stalled > 2 weeks │
                    └────────────────┬───────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
        ┌──────────┐           ┌──────────┐          ┌──────────┐
        │  Path A  │           │  Path B  │          │  Path C  │
        │  Split   │           │  Switch  │          │   Stay   │
        └──────────┘           └──────────┘          └──────────┘
```

### Path A: Age-gate OpenAI Realtime to 9-12 only
- **What we do**: at session-broker level, check `child_profile.age_band`. If `3-5` or `6-8`, force `provider=hybrid`. If `9-12`, allow `provider=openai`.
- **When to choose**: ZDR is "in progress" and a partial launch helps validate the product for the older cohort.
- **Pros**: clean per-age split. Older kids get the snappier UX.
- **Cons**: mixed UX (younger siblings notice the difference). Two providers to operate and monitor.
- **Implementation effort**: small (~1 day). A single resolver change in `realtime_voice_service.py`.

### Path B: Switch entirely to ElevenLabs Conversational AI + Claude custom LLM
- **What we do**: per #650 spike, replace the OpenAI Realtime path with ElevenLabs Conversational AI using Claude Sonnet 4-6 as the custom LLM. Anthropic data terms cover Claude usage; ElevenLabs hosts orchestration under their COPPA-aligned terms.
- **When to choose**: ZDR is denied outright and we want sub-second voice without OpenAI in the loop.
- **Pros**: keeps Anthropic-grade content quality. Sub-second latency targets achievable. Single provider for the voice loop.
- **Cons**: ElevenLabs holds orchestration data; need their COPPA addendum signed. New integration to build and contract-test. Roughly 2-3 weeks of work per #650 estimates.
- **Implementation effort**: medium. Depends on #650 spike outcome.

### Path C: Stay on hybrid; accept the latency floor
- **What we do**: leave `REALTIME_VOICE_PROVIDER=hybrid`. Whisper-1 STT + Claude + ElevenLabs TTS as we ship today.
- **When to choose**: ZDR enrollment is a "no" with no near-term reconsideration, AND we want to delay the ElevenLabs Conversational AI integration.
- **Pros**: zero engineering work. Already in prod. Fully tested.
- **Cons**: p50 ~1.5-2.5s/turn structural floor. Pre-readers (3-5) feel the lag most. The "buddy is alive" promise weakens.
- **Implementation effort**: zero (status quo).

### Decision criteria summary
| Question | Path A | Path B | Path C |
|---|---|---|---|
| ZDR is a hard no? | maybe | yes | yes |
| We need sub-second voice for 3-5? | no | yes | no |
| We have 2-3 weeks of engineering capacity? | no | yes | no |
| We are okay with two providers in prod? | yes | no | no |

**Who decides**: operator + legal counsel. Engineering surfaces the technical implications; legal weighs the COPPA / data-handling posture; operator weighs the product trade-off. Not an engineering call.

---

## Section 8: Pre-Launch Checklist

> **Print this page.** Tick every box before flipping `REALTIME_VOICE_PROVIDER=openai` in production. Each item links back to the section above.

```
Operator: __________________________  Date: __________________________
```

### Prerequisites

- [ ] **1. ZDR enrollment confirmed** in writing from OpenAI for org `<ORG_ID>`. Email/ticket link saved. → [§1](#section-1-zdr-enrollment)
- [ ] **2. Monthly cost cap set** on OpenAI org dashboard (`$________`) AND `OPENAI_REALTIME_MONTHLY_CAP_USD` env var matches. 80% warning + 100% hard-stop configured. → [§2](#section-2-cost-ceiling)
- [ ] **3. Fallback drill complete.** Smoke-tested `REALTIME_VOICE_PROVIDER=hybrid` on prod with one test session. Hybrid path served end-to-end. Flipped back to `=openai`. → [§3](#section-3-fallback-validation)
- [ ] **4. Telemetry dashboards live.** Latency (p50/p95 first-audio-ms) and provider error rate panels show non-zero data from a real session. Cost panel populated from #648. → [§4](#section-4-telemetry-verification)
- [ ] **5. Alerts wired.** p95 > 2.5s, cost > 80% cap, provider error rate > 5% — all three fire to on-call. → [§4](#section-4-telemetry-verification)
- [ ] **6. Safety contract tests green** on `main`. All six contract tests listed in §5 pass in CI within the last 24 hours. → [§5](#section-5-safety-verification)
- [ ] **7. Manual safety smoke complete.** All five manual checks in §5 ticked off on prod with at least one age-3-5 and one age-9-12 profile. → [§5](#section-5-safety-verification)
- [ ] **8. Tool versioning verified.** `TOOL_VERSION` matches what the realtime session prompt declares. Drift warnings absent from last 24h of logs. → [§6](#section-6-tool-versioning)
- [ ] **9. ZDR contingency plan documented.** Path A/B/C decision recorded for the on-call team in case ZDR is revoked mid-launch. → [§7](#section-7-zdr-contingency-decision-tree)
- [ ] **10. Rollback procedure rehearsed.** On-call knows how to flip `REALTIME_VOICE_PROVIDER=hybrid` on Railway within 60 seconds. → [§3](#section-3-fallback-validation)

### Sign-off

```
Engineering lead: ____________________    Date: __________
Operator on call: ____________________    Date: __________
Legal (ZDR only): ____________________    Date: __________
```

### After launch — first 24h

- [ ] Watch p95 first-audio-ms hourly. If sustained > 2.5s, investigate; > 4s for 5 min straight, fail over to hybrid.
- [ ] Watch cumulative org spend daily for the first week. Compare against the worked-example projection in §2.
- [ ] Review `voice_session_end` logs for unexpected `error_code` values.
- [ ] Confirm zero raw audio bytes have been written to disk (spot-check storage bucket).
