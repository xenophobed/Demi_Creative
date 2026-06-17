# Spike: ElevenLabs Conversational AI + Claude Custom LLM as ZDR-Denial Fallback

> **Issue**: [#650](https://github.com/xenophobed/Demi_Creative/issues/650) | **Parent epic**: [#605 Talk to Buddy — Realtime Voice](https://github.com/xenophobed/Demi_Creative/issues/605) | **PRD anchor**: [§3.16.8 ZDR contingency option (b)](../product/PRD.md#3168-launch-prerequisites-added-in-v2-cutover) | **Time-box**: 2 days | **Status**: complete
>
> **Sibling docs**: [voice-launch-prerequisites.md](../guides/voice-launch-prerequisites.md) covers the primary OpenAI Realtime path and the ZDR enrollment workflow. This doc covers ONE of the three documented contingencies (option b) if that enrollment is denied or stalled past the launch window.

---

## 1. TL;DR

**Go / no-go**: **Conditional GO** as the chosen ZDR-denial contingency, but only if the operator can sign an **ElevenLabs Enterprise agreement with Zero Retention Mode + signed DPA** before we route any under-13 traffic through it. Without Zero Retention Mode, the path is a **NO-GO** because ElevenLabs Conversational AI defaults to 2-year transcript+audio retention and their public privacy policy explicitly states the platform is "not intended for or directed at children under the age of 18" ([source](https://elevenlabs.io/privacy-policy)). On their Pro/self-serve tier we would be in violation of their own ToS.

**Single biggest reward**: Architectural fit is excellent. ElevenLabs Conversational AI custom-LLM webhook accepts an **OpenAI-compatible Chat Completions SSE endpoint** ([source](https://elevenlabs.io/docs/conversational-ai/customization/llm/custom-llm)), which means we can stand up a thin OpenAI-shaped shim in front of `my_agent_proxy.stream_my_agent_chat` and preserve the entire Claude Agent SDK orchestration tree (subagents, memory wiring, `launch_flow`, safety) with **zero changes to specialist code**. The Provider Protocol seam in [`backend/src/services/realtime_voice_service.py:262`](../../backend/src/services/realtime_voice_service.py) already supports this — a new `ElevenLabsConvAIProvider` slots in alongside `OpenAIRealtimeProvider`.

**Single biggest risk**: We lose **in-process safety gating**. Today the broker calls `_safety_check_text` between transcript-finalize and TTS, and again between Claude reply and TTS (`backend/src/services/realtime_voice_service.py:564`, fail-closed). When ElevenLabs hosts the orchestration loop, our safety check would only run inside our custom-LLM webhook on the *reply text*, not on the *child's transcript* (which we never see) and not on the *synthesized audio* (which streams direct ElevenLabs → browser). ElevenLabs Guardrails 2.0 ([source](https://elevenlabs.io/blog/guardrails)) layers on top, but it is keyword/policy-based, not our age-tiered safety pipeline. **Net: our 0.90 safety floor for the 3-5 cohort weakens to "best-effort by ElevenLabs Guardrails + our reply-text gate"** — a real product safety regression we must accept consciously.

---

## 2. Architecture sketch

### 2.1 Provider class shape

The provider Protocol in [`backend/src/services/realtime_voice_service.py:262-299`](../../backend/src/services/realtime_voice_service.py) declares five methods: `start_session`, `push_audio`, `finalize_utterance`, `synthesize_speech`, `close`. The `OpenAIRealtimeProvider` (line 772) keeps a server-side WebSocket open to OpenAI; `ElevenLabsConvAIProvider` would do the same shape but talk to ElevenLabs's Conversational AI WebSocket endpoint instead. **However, the semantics shift**: with OpenAI Realtime, our broker still drives the loop. With ElevenLabs Conversational AI, **ElevenLabs drives the loop** — they call *us* (the custom-LLM webhook). Two seams:

```python
# Seam A — provider class (existing pattern)
class ElevenLabsConvAIProvider:           # implements RealtimeVoiceProvider
    name = "elevenlabs_convai"
    # start_session opens ws://api.elevenlabs.io/v1/convai/conversation
    # push_audio forwards PCM frames upstream
    # finalize_utterance is a no-op (ElevenLabs decides turn boundaries)
    # synthesize_speech is a no-op (audio streams in via the same WS)
    # close shuts the WS

# Seam B — NEW: custom-LLM webhook (no equivalent in OpenAI Realtime path)
# POST /api/v1/internal/voice/llm/chat/completions
#   request: OpenAI Chat Completions shape with messages[] + tools[]
#   response: SSE stream of OpenAI-shaped delta chunks ending data: [DONE]
# Auth: bearer token issued per voice session, single-use, 60s TTL (mirrors
# voice_ephemeral_token.py pattern). Body is forwarded into
# stream_my_agent_chat() so all specialist orchestration stays intact.
```

### 2.2 Sequence (one turn)

```
Browser              Our WS broker         ElevenLabs ConvAI         Our LLM webhook         Claude Agent SDK
   │                       │                       │                       │                       │
   │── PCM frame ─────────▶│                       │                       │                       │
   │                       │── forward PCM ───────▶│                       │                       │
   │                       │                       │ (STT inside EL)       │                       │
   │                       │                       │── POST /chat ───────▶│                       │
   │                       │                       │   (messages + tools)  │── stream_my_agent ──▶│
   │                       │                       │                       │                       │── safety ──┐
   │                       │                       │                       │                       │            │
   │                       │                       │                       │◀── tokens ────────────│◀───────────┘
   │                       │                       │◀── SSE deltas ────────│                       │
   │                       │                       │ (TTS inside EL)       │                       │
   │                       │◀── audio frames ──────│                       │                       │
   │◀── audio frames ──────│                       │                       │                       │
   │                       │                       │                       │                       │
   │                       │ tool-call event arrives via WS                │                       │
   │                       │── launch_flow control frame ─────────────────▶│ (browser navigates)   │
```

**Where each thing lives**:
- **Whisper-equivalent STT**: inside ElevenLabs (their model, their infra, our audio bytes transit).
- **TTS**: inside ElevenLabs (Flash v2 by default; we configure voice per child age tier).
- **Brain (Claude)**: our infra. ElevenLabs's custom-LLM webhook hits our endpoint, we forward to `stream_my_agent_chat`, Claude does the thinking. Anthropic API call originates from **our** infra with **our** Anthropic key — Claude traffic never touches ElevenLabs.
- **Tools**: declared in the custom-LLM webhook response as OpenAI-format `tool_calls`. ElevenLabs forwards tool-call invocations back to us as WebSocket events on the main session WS (server tools pattern; [source](https://elevenlabs.io/docs/agents-platform/customization/tools/server-tools)). Our broker handles `launch_flow` → fires control frame to browser, identical to the OpenAI Realtime path.
- **Safety**: see §4. Reply-text gate stays in the webhook. Transcript-text gate is lost (we never see the raw transcript before the LLM call lands). Audio-output gate is lost (audio bytes never reach our broker).

### 2.3 What the custom-LLM webhook actually is

A new FastAPI route — call it `POST /api/v1/internal/voice/llm/chat/completions` — that:
1. Authenticates a per-session bearer token (issued by an extended `voice_ephemeral_token.py`).
2. Looks up `(user_id, child_id, agent_id, target_age)` from the token.
3. Forwards `messages[-1].content` into `stream_my_agent_chat(message=..., user_id=..., child_id=..., age_group=..., ...)`.
4. Re-shapes the SSE event stream from `stream_my_agent_chat` (which emits `status`, `text_delta`, `result`, `launch_flow`, `complete` events) into OpenAI Chat Completions delta chunks.
5. Maps `launch_flow` SSE events to OpenAI `tool_calls` so ElevenLabs forwards them back to us through the main session WS.

This is **glue code, not new orchestration**. The Claude Agent SDK call tree, prompts, memory, and safety inside `stream_my_agent_chat` are reused unchanged.

---

## 3. Cost comparison

Assumptions: 15 min/day per active user, 30 days/month, blended 50% cached / 50% uncached ratio (a generous cache hit rate — system prompt + per-age preamble + last 10 messages of history). All figures in USD/month. Sources: OpenAI Realtime token math [callsphere](https://callsphere.ai/blog/vw2c-openai-realtime-cost-per-minute-math-2026) and [OpenAI community pricing thread](https://community.openai.com/t/gpt-realtime-gpt-realtime-mini-pricing-update/1372904); ElevenLabs Agents pricing [official](https://elevenlabs.io/pricing/agents) and [pxlpeak breakdown](https://pxlpeak.com/blog/ai-tools/elevenlabs-pricing-guide); Claude Sonnet 4 pricing assumed at $3/$15 per M tokens (Anthropic public rate card).

| Path | Per-min cost (blended) | 100 users / mo | 1,000 users / mo | 10,000 users / mo |
|---|---|---|---|---|
| **OpenAI Realtime (`gpt-realtime-mini`, primary)** | $0.145 (avg of $0.075 cached + $0.215 uncached) | $6,525 | $65,250 | $652,500 |
| **OpenAI Realtime (`gpt-realtime-2`, escalation)** | $0.315 | $14,175 | $141,750 | $1,417,500 |
| **ElevenLabs ConvAI (Turbo tier, $0.10/min) + Claude Sonnet 4 LLM cost** | $0.10 EL + ~$0.04 Claude¹ + $22 base ÷ user count | $6,322 | $63,022 | $629,742 |
| **ElevenLabs ConvAI (Standard tier, $0.08/min) + Claude Sonnet 4 LLM cost** | $0.08 EL + ~$0.04 Claude¹ + $22 base ÷ user count | $5,422 | $54,022 | $539,742 |
| **Hybrid (Whisper + Claude + ElevenLabs Flash TTS)** | ~$0.06/min (current cascaded path) | $2,700 | $27,000 | $270,000 |

¹ Claude Sonnet 4 cost per voice minute, rough estimate: ~150 input tokens (with prompt cache hits) + ~80 output tokens per turn × ~6 turns/min × ($3 in + $15 out per M tokens) ≈ $0.03–$0.05/min. Cache-hit-dependent.

### Cost takeaways

- **ElevenLabs Turbo + Claude is roughly cost-parity with `gpt-realtime-mini`** at all scales (~3% cheaper at 1k users). This is **good** — switching to the fallback does not double the bill.
- **ElevenLabs is roughly half the cost of `gpt-realtime-2`**. So if our quota mix shifts toward the escalated tier, the fallback gets relatively *more* attractive on cost grounds alone.
- **Hybrid stays the cheapest** by 2–3× because there is no realtime infrastructure premium. But it carries the 1.5–2.5s latency floor that drove the v2 cutover in the first place — for the 3-5 cohort, that's a UX no-go.
- The $22/mo ElevenLabs base plan is a **rounding error** at any meaningful user count.

---

## 4. Ranked risks

Probability × Impact rank. Probability is qualitative (Low / Med / High) given current public ElevenLabs posture; Impact is on the product (Low / Med / High / Critical).

| # | Risk | P | I | P×I | Mitigation |
|---|---|---|---|---|---|
| 1 | **ElevenLabs ToS prohibits under-18 user data on self-serve tiers** ([source](https://elevenlabs.io/privacy-policy)). Without Enterprise + DPA + Zero Retention Mode in writing, we are in breach. | High | Critical | **Critical** | Hard-gate the cutover on Enterprise contract signed AND Zero Retention Mode enabled. Don't ship without both. Log in §6 as the gating open question for sales. |
| 2 | **Default 2-year transcript+audio retention** is the wrong posture for a children's product. Zero Retention Mode is Enterprise-only and not self-serve. | High | Critical | **Critical** | Same as #1. If Enterprise tier is not financially viable at our scale, fall back to contingency path (a) age-gated split or (c) stay-on-hybrid. |
| 3 | **Loss of in-process safety pipeline** for transcript and audio. We can only safety-check the LLM reply text; raw transcript and synthesized audio bytes never pass through `_safety_check_text`. | High | High | **High** | (a) Tighten reply-text safety to 0.92 for under-13 (above the current 0.90 floor) to compensate. (b) Enable all ElevenLabs Guardrails 2.0 categories. (c) Add a Custom Guardrail in plain English mirroring our content-safety policy. None of this fully restores the transcript-input gate; this is a real residual risk we accept by choosing this path. |
| 4 | **ElevenLabs is a single point of failure** for the whole loop (STT + orchestration + TTS share their infra). Our current hybrid path has independent failure domains. | Med | High | **High** | The fallback-within-fallback to hybrid (`REALTIME_VOICE_PROVIDER=hybrid` env flip) still works because Whisper and Claude live elsewhere — but ElevenLabs Flash TTS is also ElevenLabs, so any platform-wide outage takes hybrid down too. Mitigation: keep an OpenAI TTS path warm as a tertiary fallback. |
| 5 | **No published uptime SLA** for non-Enterprise tiers ([source](https://aloa.co/ai/comparisons/ai-voice-comparison/elevenlabs-vs-google-cloud-tts)). Enterprise SLAs negotiated case-by-case. | Med | High | **High** | Negotiate explicit 99.9% uptime in the Enterprise contract. Wire `voice_session_end` telemetry to detect provider-side failures (close codes, abnormal terminations) and auto-failover to hybrid at sustained error rate. |
| 6 | **Tool-call shape drift**: ElevenLabs expects OpenAI-format tool definitions. Our `launch_flow` schema must serialize cleanly to OpenAI tool JSON. | Med | Med | **Med** | Pin tool schema version (already required by PRD §3.16.8 item 6). Contract test: round-trip `launch_flow` payload through OpenAI tool JSON without loss. Reuse the OpenAI Realtime tool-shape helpers already shipped for #645. |
| 7 | **EU data residency** for any future EU children traffic. ElevenLabs offers EU residency on Enterprise ([source](https://elevenlabs.io/blog/introducing-european-data-residency)) but it must be elected. | Low | High | **Med** | Not blocking for US launch. Add as an Enterprise contract clause if/when we open EU. |
| 8 | **Latency regression from custom-LLM webhook hop**: ElevenLabs → our webhook → Claude → SSE back to ElevenLabs adds 1 network round-trip vs. their hosted LLMs. | Med | Med | **Med** | Deploy webhook in same region as ElevenLabs primary (US-East). Use streaming SSE from token 0 (don't wait for full Claude reply). p95 budget remains < 2500ms per PRD §3.16.8 item 4. |
| 9 | **Cost surprises from "LLM fees add 10-30%"** language in ElevenLabs pricing ([source](https://pxlpeak.com/blog/ai-tools/elevenlabs-pricing-guide)). That uplift applies to *their* LLM tiers; with custom LLM, we pay Anthropic directly and ElevenLabs's per-minute rate stays as quoted. Worth verifying in writing. | Low | Med | **Low** | Confirm with sales: "custom LLM = no LLM markup, per-minute rate is Standard $0.08 / Turbo $0.10 only." Open question #6. |
| 10 | **Voice cloning concerns** — ElevenLabs's brand is voice cloning, which is the *opposite* of what we want for a children's product. Parents may not understand the distinction. | Low | Med | **Low** | Consent screen copy explicitly states "the buddy's voice is a pre-selected stock voice; no child or family voice is ever cloned." Reuse §3.16.3 stacked consent UI. |

---

## 5. Effort estimate (2-week emergency ship)

If ZDR is denied and operator picks path (b), here's a story breakdown to ship to production in 2 weeks. Maps each story to existing infrastructure that survives vs. needs replacement.

| # | Story | Survives | Needs new | Effort |
|---|---|---|---|---|
| E7-1 | Spike close-out — operator signs ElevenLabs Enterprise contract with Zero Retention Mode + DPA | nothing technical | contracts only | 1 wk wall-clock (parallel to dev) |
| E7-2 | `ElevenLabsConvAIProvider` class implementing `RealtimeVoiceProvider` Protocol | Protocol seam at `realtime_voice_service.py:262` survives unchanged | new ~400 LOC provider class + WS state machine | 3 d |
| E7-3 | Custom-LLM webhook: `POST /api/v1/internal/voice/llm/chat/completions` — OpenAI Chat Completions SSE shim over `stream_my_agent_chat` | `my_agent_proxy.stream_my_agent_chat` survives unchanged (subagents, memory, launch_flow, safety) | new route + SSE re-shaper + per-session bearer token | 2 d |
| E7-4 | Extend `voice_ephemeral_token.py` to mint webhook bearer tokens (60s TTL, single-use, bound to `(user_id, child_id, agent_id)`) | existing token pattern survives | one new token type + middleware | 0.5 d |
| E7-5 | Tool shape adapter: map our `launch_flow` schema to OpenAI tool JSON; map ElevenLabs tool-call events back to our `launch_flow` payload | tool helpers from #645 survive | thin adapter (~50 LOC) + contract test | 1 d |
| E7-6 | Safety pipeline rewire: reply-text gate moves into the webhook (still fail-closed); add Custom Guardrail in ElevenLabs dashboard mirroring `check_content_safety` policy text | `_safety_check_text` survives; called inside webhook instead of broker | move 1 call site + ElevenLabs dashboard config | 1 d |
| E7-7 | Consent screen copy update: "voice channel uses ElevenLabs (provider); your buddy's brain is still Claude (Anthropic)" | `ParentConsentGate kind="voice_conversation"` from #619 survives | copy + DPA disclosure | 0.5 d |
| E7-8 | Provider selection: `REALTIME_VOICE_PROVIDER=elevenlabs_convai` env path | `_select_provider` function at `realtime_voice_service.py:1367` survives | one new branch | 0.25 d |
| E7-9 | Contract tests: `test_elevenlabs_convai_provider_contract`, `test_voice_safety_pre_tts_contract` extended for new path | test scaffolding survives | new test file (~300 LOC) | 1.5 d |
| E7-10 | Smoke test in staging: 10 end-to-end voice sessions across all three age bands, verify `launch_flow` handoffs, safety failures, idle timeout, parent revocation | telemetry + ops dashboard survive | manual test plan | 1 d |
| E7-11 | Cost telemetry: extend `estimate_session_cost_usd` (`realtime_voice_service.py:150`) with ElevenLabs rate table | helper survives | rate table addition + test | 0.5 d |
| E7-12 | Documentation: update `voice-launch-prerequisites.md` Section 7 contingency decision tree with new "path (b) selected" runbook | doc survives | one section | 0.5 d |

**Total**: ~12 dev days + 1 week of contract negotiation in parallel. Tight but achievable for a 2-week target if E7-1 (contract) starts immediately on day 0.

**What survives is significant**: the `RealtimeVoiceProvider` Protocol, `stream_my_agent_chat`, all specialist subagents, all prompts, the safety pipeline (mostly), the consent system, the telemetry. The provider Protocol seam shipped in #613 is the architectural decision that makes this 2-week target possible at all.

---

## 6. Open questions (need ElevenLabs sales or proof-of-concept)

Worth knowing what to ask if we ever invoke this path.

1. **Q (sales)**: Is **Zero Retention Mode available outside HIPAA BAA** customers? Public docs imply it's an Enterprise feature, but we are not a HIPAA Covered Entity. We need it for COPPA, not HIPAA. ([starting point](https://compliance.elevenlabs.io/))
2. **Q (sales)**: What does **Enterprise tier minimum monthly commitment** look like at 100 / 1,000 / 10,000 active users? If the floor is e.g. $50k/yr, ElevenLabs fallback may be uneconomic at our soft-launch scale even though per-minute math works.
3. **Q (legal)**: Does ElevenLabs's standard **DPA** cover children's data under COPPA? Their privacy policy is explicit that the platform is not for under-18s — does the Enterprise DPA carve out a different posture for products built for kids?
4. **Q (sales)**: What is the **negotiated uptime SLA** on Enterprise? We need 99.9% minimum to match the OpenAI Realtime posture.
5. **Q (PoC)**: Does **Claude Sonnet 4 streaming through our custom-LLM webhook** actually hit the < 2500ms p95 budget end-to-end (browser → EL STT → webhook → Claude first token → SSE back → EL TTS first frame → browser)? Only a real PoC can confirm. The webhook hop is the new unknown vs. picking an EL-hosted LLM.
6. **Q (billing)**: When using **custom LLM, is the per-minute rate truly $0.08 (Standard) / $0.10 (Turbo)** with no LLM markup? Public pricing language is ambiguous about whether the markup applies to custom LLM users.
7. **Q (technical)**: How does ElevenLabs **handle a custom-LLM webhook returning a 5xx mid-stream**? Does the session crash, retry, or fall through to a fallback LLM? We need failure semantics defined for the SRE runbook.
8. **Q (technical)**: Can we **disable ElevenLabs Guardrails entirely** when our reply-text safety check is the source of truth, or must we layer them? Layering is fine; conflict is not.
9. **Q (technical)**: What is the **maximum SSE response time** before ElevenLabs times out the custom-LLM call? Our Claude proxy can take 3–5 s for specialist invocations. If EL's timeout is < 5 s, `launch_flow` handoffs may break.
10. **Q (compliance)**: Is **audio data residency** configurable independent of metadata residency? Some COPPA-conservative legal postures want EU/US split.

---

## 7. Decision criteria for execution

Pull the trigger on path (b) ONLY if **all** of these conditions hold:

- [ ] **ZDR enrollment with OpenAI is denied** or has not landed within 4 weeks of submission, AND
- [ ] Operator decision is to **keep the 3-5 cohort on the platform** (we don't accept dropping 3-5 entirely or path (a) age-split as a permanent posture), AND
- [ ] **ElevenLabs Enterprise contract with Zero Retention Mode + DPA is signed or has high confidence of signing within 1 week**, AND
- [ ] **Open question #1 (Zero Retention without HIPAA BAA)** is answered Yes by ElevenLabs in writing, AND
- [ ] **Open question #2 (Enterprise minimum commit)** lands at a number the business will fund at our current user count, AND
- [ ] **PoC built per open question #5** confirms p95 latency < 2500ms.

If ANY of those fail, **fall through to path (c) stay-on-hybrid** (lower bar, already shipped, no contracts needed) and accept the 1.5–2.5s latency floor for the 3-5 cohort. Path (a) age-split is a third option but creates a mixed UX that is hard to explain to parents and hard to operate.

---

## 8. Comparison to other contingency paths

Recap from [PRD §3.16.8 ZDR contingency](../product/PRD.md#3168-launch-prerequisites-added-in-v2-cutover):

### Path (a) — age-gated split (OpenAI Realtime for 9-12, hybrid for 3-8)

**Why path (b) beats it**: Path (a) creates a **mixed UX** where two children of different ages on the same family account get fundamentally different voice latency (~500ms vs ~2000ms). Hard to explain in marketing copy. Hard to operate two paths in production permanently. And it does not preserve voice-first as the design intent — 3-8 cohort gets degraded UX *forever*, not just during ZDR limbo. Path (b) gives all age bands the realtime UX.

**Where path (a) wins**: Zero contracts to sign. Ships in 1 day (env flag + age-routing). If ZDR is denied and we are in a hurry to launch *anything*, path (a) is the immediate band-aid while path (b) negotiations run in parallel. **Recommended actually as a stopgap**, not a destination.

### Path (c) — stay on hybrid

**Why path (b) beats it**: Hybrid's cascaded Whisper → Claude → ElevenLabs Flash TTS path has a **1.5–2.5s p50 latency floor** that breaks the "the buddy is alive" promise for pre-readers. This is the exact reason the v2 cutover happened. Going back to hybrid is a strategic retreat from the voice-first product position.

**Where path (c) wins**: Already shipped. Already tested. Zero contracts. Lowest cost (~2-3× cheaper than path b). If the business decides voice-first is not worth the contract+cost premium, path (c) is the rational fallback. **Recommended if path (b) Enterprise math doesn't pencil out.**

### Summary

| Criterion | Path (b) ElevenLabs+Claude | Path (a) age-split | Path (c) stay-on-hybrid |
|---|---|---|---|
| Time to ship | 2 weeks + 1 week contract | 1 day | 0 days |
| UX consistency across ages | Uniform realtime | **Split, mixed** | Uniform slow |
| Voice-first product promise | Preserved | Partially preserved | **Broken for pre-readers** |
| Safety pipeline fidelity | **Degraded (reply-text only)** | Full on hybrid; full on OpenAI Realtime path | Full |
| Cost vs primary path | Parity with mini, cheaper than 2 | Mixed | 2-3× cheaper |
| Contract / legal lift | **High (Enterprise + DPA)** | Low | Low |
| Single point of failure | ElevenLabs | Split | Cascaded (3 providers) |
| Recommended use | Permanent fallback once contracts land | Stopgap during contract negotiation | Permanent fallback if business won't fund Enterprise |

**Concrete recommendation if ZDR is denied tomorrow**: ship path (a) within 24 hours (env-flag age routing), simultaneously open the path (b) ElevenLabs Enterprise contract, and have path (c) `REALTIME_VOICE_PROVIDER=hybrid` as the proven tertiary fallback. We are not picking one of three — we are sequencing all three based on negotiation outcome.

---

## Appendix: Sources

External:
- [ElevenLabs Custom LLM docs](https://elevenlabs.io/docs/conversational-ai/customization/llm/custom-llm) — OpenAI Chat Completions SSE contract for the webhook
- [ElevenLabs Server Tools docs](https://elevenlabs.io/docs/agents-platform/customization/tools/server-tools) — tool-call event shape
- [ElevenLabs Guardrails 2.0 announcement](https://elevenlabs.io/blog/guardrails) — safety layer composition
- [ElevenLabs Claude Sonnet 4 announcement](https://elevenlabs.io/blog/claude-sonnet-4-is-now-available-in-conversational-ai) — Claude as first-class LLM
- [ElevenLabs Privacy Policy](https://elevenlabs.io/privacy-policy) — under-18 prohibition, 3-year voice data retention default
- [ElevenLabs DPA](https://elevenlabs.io/dpa) — Enterprise data processing terms
- [ElevenLabs Agents pricing](https://elevenlabs.io/pricing/agents) — per-minute rates by tier
- [ElevenLabs Trust Center](https://compliance.elevenlabs.io/) — SOC2 Type II, ISO 27001, HIPAA attestations
- [ElevenLabs European Data Residency](https://elevenlabs.io/blog/introducing-european-data-residency) — EU residency on Enterprise
- [Pxlpeak ElevenLabs pricing breakdown](https://pxlpeak.com/blog/ai-tools/elevenlabs-pricing-guide) — independent rate verification + "LLM fees add 10-30%" caveat
- [CallSphere OpenAI Realtime cost math](https://callsphere.ai/blog/vw2c-openai-realtime-cost-per-minute-math-2026) — token math for the comparison table
- [OpenAI community pricing thread](https://community.openai.com/t/gpt-realtime-gpt-realtime-mini-pricing-update/1372904) — current `gpt-realtime` / `gpt-realtime-mini` pricing
- [Aloa SLA comparison](https://aloa.co/ai/comparisons/ai-voice-comparison/elevenlabs-vs-google-cloud-tts) — ElevenLabs has no published SLA outside Enterprise

Internal:
- [`backend/src/services/realtime_voice_service.py:262`](../../backend/src/services/realtime_voice_service.py) — `RealtimeVoiceProvider` Protocol (the seam this fallback plugs into)
- [`backend/src/services/realtime_voice_service.py:772`](../../backend/src/services/realtime_voice_service.py) — `OpenAIRealtimeProvider` (the class shape `ElevenLabsConvAIProvider` mirrors)
- [`backend/src/services/realtime_voice_service.py:564`](../../backend/src/services/realtime_voice_service.py) — `_safety_check_text` call site we lose visibility on
- [`backend/src/services/realtime_voice_service.py:1367`](../../backend/src/services/realtime_voice_service.py) — `_select_provider` env-driven dispatch
- [`backend/src/services/voice_ephemeral_token.py`](../../backend/src/services/voice_ephemeral_token.py) — token pattern reused for webhook bearer auth
- [`backend/src/agents/my_agent_proxy.py:1066`](../../backend/src/agents/my_agent_proxy.py) — `stream_my_agent_chat` entry the webhook wraps
- [`docs/guides/voice-launch-prerequisites.md`](../guides/voice-launch-prerequisites.md) — sibling doc covering the primary path
- [`docs/product/PRD.md` §3.16.8](../product/PRD.md#3168-launch-prerequisites-added-in-v2-cutover) — ZDR contingency definition
