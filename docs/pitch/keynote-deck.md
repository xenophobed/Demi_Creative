---
marp: true
paginate: true
backgroundColor: "#FFFFFF"
color: "#1E293B"
size: 16:9
style: |
  section {
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", "Segoe UI", sans-serif;
    padding: 60px 80px;
    background: #FFFFFF;
  }
  section.title {
    background: linear-gradient(135deg, #FDF2F8 0%, #F5F3FF 100%);
  }
  section.dark {
    background: #0F172A;
    color: #F8FAFC;
  }
  section.dark h1, section.dark h2 { color: #F472B6; }
  section.dark em { color: #C4B5FD; }
  section.dark small { color: #94A3B8; }
  h1 {
    color: #DB2777;
    font-size: 56px;
    font-weight: 800;
    line-height: 1.1;
    margin: 0 0 28px;
  }
  h2 {
    color: #7C3AED;
    font-size: 36px;
    font-weight: 700;
    margin: 0 0 24px;
  }
  h3 {
    color: #1E293B;
    font-size: 24px;
    font-weight: 600;
  }
  p, li { font-size: 22px; line-height: 1.5; }
  strong { color: #DB2777; }
  em { color: #7C3AED; font-style: italic; }
  table { border-collapse: collapse; margin: 16px 0; width: 100%; }
  th, td { padding: 12px 18px; border-bottom: 1px solid #E2E8F0; font-size: 19px; text-align: left; vertical-align: top; }
  th { color: #7C3AED; font-weight: 700; }
  .cards { display: grid; gap: 22px; margin: 24px 0; }
  .cards.cols-2 { grid-template-columns: repeat(2, 1fr); }
  .cards.cols-3 { grid-template-columns: repeat(3, 1fr); }
  .card {
    background: #FDFCFF;
    border: 1px solid #E9D5FF;
    border-radius: 14px;
    padding: 22px 24px;
    box-shadow: 0 2px 8px rgba(124, 58, 237, 0.08);
  }
  .card .card-emoji { font-size: 30px; line-height: 1; margin-bottom: 6px; display: block; }
  .card .card-title { color: #7C3AED; font-size: 22px; font-weight: 700; margin: 0 0 8px; display: block; }
  .card .card-body { color: #1E293B; font-size: 19px; line-height: 1.45; }
  .card .card-quote { color: #7C3AED; font-size: 16px; font-style: italic; margin-top: 8px; display: block; }
  code, pre { font-family: "SF Mono", "Menlo", monospace; }
  pre { background: #F8FAFC; color: #0F172A; padding: 18px 22px; border-radius: 12px; font-size: 16px; line-height: 1.4; }
  small { color: #64748B; font-size: 18px; }
  footer { color: #94A3B8; font-size: 14px; }
---

<!-- _class: title -->

![cover mark h:90](assets/cover-mark.svg)

# Kids Creative Workshop

## An *agentic* app for kids — built on Claude Agent SDK.

<br>

<small>5-minute pitch · Single agent → agent team · 2026</small>

<!--
🎤 SCRIPT · Slide 1 · Title
⏱ ~7 seconds · 5-min cut: KEEP

"Good morning. This is Kids Creative Workshop — an agentic app for kids, built on the Claude Agent SDK. Let me start with a moment."

🎬 Warm and slow. Pause before "Let me start with a moment."
-->

---

<!-- _class: title -->

# Three moments. One buddy.

<br>

# *Her drawing — becomes a story.*

# *Her character — stars in the next adventure.*

# *Tomorrow's news — arrives as her podcast.*

<!--
🎤 SCRIPT · Slide 2 · Three moments
⏱ ~22 seconds · 5-min cut: KEEP

"Three moments in a kid's day.

She hands her drawing to her buddy — and it becomes a story, in her character.

[pause]

That same character stars in the next adventure — her choices, her ending.

[pause]

And tomorrow's news arrives as her own podcast — kid-safe.

One buddy. Three moments. Her world, every time."

🎬 Slow down. The pauses are the slide.
➡ Next: "But today's AI fails her on every one of these."
-->

---

## Today's AI fails kids on *four* fronts

| 🚫 **Not personalized enough** | 🚫 **Not highly customized** |
|---|---|
| Generic output. No memory of *her* characters, *her* voice, *her* age. | Same prompt, same answer for every child. No buddy identity. No per-child capability set. |

| 🚫 **No suited news for kids** | 🚫 **No long-term persistence** |
|---|---|
| Today's news products are adult-first. No age-aware filter. No narrative voice for kids. | Each session resets. *Lightning the puppy* is forgotten by Monday. |

<small>Existing AI **extracts**. We **collaborate**.</small>

<!--
🎤 SCRIPT · Slide 3 · Four problems
⏱ ~24 seconds · 5-min cut: KEEP

"Today's AI fails kids on four fronts.

One — it's not personalized. Generic output, no memory of her characters or her age.

Two — it's not customized. Every child gets the same prompt, the same answer.

Three — no kid-suited news. Today's news products are adult-first.

Four — no persistence. Every session resets — last week's character is forgotten.

Existing AI extracts from kids. We collaborate with them."

🎬 Number each problem — "one, two, three, four" — to match the grid on screen.
➡ Next: "Here's how our agent fixes each one."
-->

---

# Meet **My Agent** — *one ability per problem*

| Problem | Our agent's ability |
|---|---|
| Not personalized enough | **Persona + character memory** — buddy is named & customized; recurring characters recalled across sessions (`character_repo`) |
| Not highly customized | **Per-child buddy profile + skills gating** — age-aware capabilities (3–5 / 6–8 / 9–12); buddy persona shared as system context to every specialist |
| No suited news for kids | **`kids_daily` specialist** — age-stratified prompts + per-reply safety review; news arrives as a kid-safe podcast in the buddy's voice |
| No long-term persistence | **`agent_repo` + `character_repo` + vector search** — buddy persona and recurring characters survive every session; one buddy, for life |

<small>What kids feel: **interactive** (streaming) · **proactive** (recommendations + recall) · **persistent** (memory).</small>

<!--
🎤 SCRIPT · Slide 4 · Our agent's abilities
⏱ ~28 seconds · 5-min cut: KEEP

"Four problems, four abilities — one for each.

Not personalized — persona and character memory. Recurring characters recalled across every session.

Not customized — per-child agent definitions, with skills gated by age.

No kid-news — a dedicated kids-daily specialist: age-stratified, safety-reviewed, in the buddy's voice.

No persistence — agent and character repositories, plus vector search. One buddy, for life.

And kids feel three things: interactive, proactive, persistent."

🎬 Walk problem-to-ability, tight. End on the three feelings.
➡ Next: "These abilities run on a small set of SDK primitives."
-->

---

## Foundation — *six agentic features, one stack*

| Agentic feature | How we build it |
|---|---|
| 🌊 **Interactive** | Streaming **SSE** · async-generator agents · live tool-use events |
| 🎯 **Responsive** | **LLM model** (Claude Haiku for speed) · deterministic + LLM intent routing · per-agent skill curation |
| 💡 **Proactive** | **Prompt engineering** (system-prompt scaffolding for starter suggestions) · **vector DB** recall · `character_repo` lookups |
| 🧠 **Persistent** | **Vector DB** (ChromaDB / pgvector) · `agent_repo` + `character_repo` (SQL) · cross-session memory |
| 🛡️ **Reactive** | **MCP** safety tool · `@tool` decorator · `enforce_chat_safety` + suggest-and-retry · age-aware thresholds (0.90 / 0.85) |
| 🚀 **Autonomous** *(future)* | Multi-step planning · **skills** composition · self-prompted explore loops · scheduled buddy initiatives |

<small>Built from: **prompt engineering** · **MCP** · **tools** · **skills** · **LLM model** · **vector DB**. One stack — six features, one ceiling away from autonomous.</small>

<!--
🎤 SCRIPT · Slide 5 · Six agentic features
⏱ ~32 seconds · 5-min cut: KEEP

"Six agentic features, one stack.

Interactive — streaming SSE, so the story writes itself token by token.

Responsive — Claude Haiku for speed, plus deterministic and LLM intent routing.

Proactive — vector recall surfaces recurring characters and suggests next moves.

Persistent — vector DB plus SQL repositories hold the buddy across sessions.

Reactive — every reply runs through our safety tool, with age-aware thresholds.

And autonomous — that's next: multi-step planning, scheduled buddy initiatives."

🎬 Walk row by row. Slow down on reactive — that's the safety moat. Mark autonomous as future, not shipped.
➡ Next: "One agent hit a ceiling. So we extended to a team."
-->

---

## Four agent architecture patterns — *two shipped, two ready next*

| # | Pattern | What it does | Where we use it |
|---|---|---|---|
| 1 | **🤖 Single agent/tool** | One callable, one job · linear inference | TTS via the reusable `audio_narration` tool |
| 2 | **👥 Static agent team** | Multiple specialists collaborate by role | **My Agent** proxy routes to 3 product specialists + TTS tool + `safety_review` |
| 3 | **🔀 Sub-agent fan-out** *(future)* | Same task spawned in parallel for speed | Candidate path for parallel vision crops and richer memory search |
| 4 | **🎼 Dynamic orchestrator** *(future)* | Agents registered dynamically · A2A extensible to external teams | Future `AgentDefinition` registration / A2A bridge |

<small>**Shared state** within the shipped team flows through `build_my_agent_context()` — persona, tone, style, skills, topics, goals, child_id, and age. Recurring characters flow through `character_repo` and vector memory. **A2A** remains future work.</small>

<!--
🎤 SCRIPT · Slide 6 · Four architecture patterns
⏱ ~26 seconds · 5-min cut: KEEP

"Four agent architecture patterns — two shipped, two ready next.

Single agent or tool — one job, linear inference. We use it for text-to-speech.

Static agent team — our My Agent proxy routes to image story, interactive story, Kids Daily, a reusable audio tool, and safety review.

Sub-agent fan-out and dynamic orchestration are future extension paths.

Shared context carries persona and style; recurring characters come from character memory. A2A to external teams is future work."

🎬 Walk pattern by pattern. Land the shipped-versus-future split clearly.
➡ Next: "And every agent is wired to six memory layers."
-->

---

## Six memory types — *one buddy, layered recall*

| # | Memory type | What it stores | Backed by |
|---|---|---|---|
| 1 | **🗨️ Session** | This-chat conversation history | `agent_chat_repository` |
| 2 | **⚡ Working** | Per-turn execution context (in-flight tool results, persona) | `build_my_agent_context()` in proxy |
| 3 | **📅 Episodic** | Past creations — stories, podcasts, branching choices | `stories` · `interactive_sessions` · `kids_daily_episodes` |
| 4 | **📋 Factual** | Buddy persona, child profile, preferences | `agent_repo` · `preference_repository` · `users` |
| 5 | **🧠 Semantic** | Embeddings of characters, themes, narrative style | ChromaDB (dev) / pgvector (prod) via `vector_search_server` |
| 6 | **🛠️ Procedural** | How to generate each content type | `backend/src/prompts/*.md` · `@tool` skills · `enabled_skills` |

<small>The buddy **remembers** (factual + episodic), **understands** (semantic), **acts** (procedural), **talks** (session), and **reasons in flight** (working).</small>

<!--
🎤 SCRIPT · Slide 7 · Six memory types
⏱ ~28 seconds · 5-min cut: KEEP

"Memory is what makes a buddy feel like a buddy. Six layers.

Session — this conversation's history.

Working — the per-turn execution context.

Episodic — past creations: stories, podcasts, choices.

Factual — persona, child profile, preferences.

Semantic — embeddings of characters and themes, in our vector store.

Procedural — how the buddy generates each kind of content.

Put it together: the buddy remembers, understands, acts, talks, and reasons in flight."

🎬 Brisk through the six. Slow down on procedural — most teams don't have it. Land the closing line.
➡ Next: "Here's how the layers and patterns compose in our team."
-->

---

<!-- _backgroundColor: "#0F172A" -->
<!-- _color: "#F8FAFC" -->
<!-- _class: dark -->

## The team — *one proxy, three specialists, one tool, one safety gate*

One agent hit a ceiling. Branching stories, news podcasts, per-reply safety — each needed its own expertise. We extended to an **agent team** — still on Claude Agent SDK.

![architecture diagram h:380](assets/architecture.svg)

**Unlocks**: 🎯 **responsive** · 🎨 **dynamic** · ➕ **A2A extensible**

<!--
🎤 SCRIPT · Slide 8 · The team (CENTERPIECE)
⏱ ~38 seconds · 5-min cut: KEEP

"This is the architecture. Each surface needed its own expertise — so we built an agent team, on the Claude Agent SDK.

[point at the proxy]

A child's message hits the proxy first. It orchestrates — routes intent with deterministic rules plus LLM disambiguation.

[point at the specialists]

Then the right capability runs — image story, interactive story, and Kids Daily are specialists; audio narration is a reusable TTS tool. Each has its own prompt and tools.

[point at safety_review — pause]

Every reply passes through safety review before it reaches the child. That's the non-negotiable gate.

[point at the context bus]

And underneath, shared context — persona, characters — flows to every agent. Same character in the story and the podcast.

This unlocks responsive, dynamic, and A2A-extensible."

🎬 Centerpiece slide. Walk top to bottom. Pause after "before it reaches the child."
➡ Next: "Every primitive here earned its place."
-->

---

## Three-layer infrastructure — *each service does one thing*

![infrastructure h:420](assets/infrastructure.svg)

<!--
🎤 SCRIPT · Slide 9 · Three-layer infrastructure
⏱ ~24 seconds · 5-min cut: KEEP

"The infrastructure is three managed services.

Vercel hosts the frontend — a React app on a CDN.

Railway runs the FastAPI backend — the Agent SDK and seven MCP servers, auto-deployed from main.

Supabase is the database — Postgres with pgvector, plus auth and storage.

Plus AI APIs — Anthropic, OpenAI, ElevenLabs, Tavily.

Each service does one job. No magic, no monorepo coupling."

🎬 Trace top to bottom. Land "no magic, no monorepo coupling" slowly.
➡ Next: "Inside the backend, the same discipline holds."
-->

---

## Backend — *seven layers, one direction*

![backend layers h:440](assets/backend-layers.svg)

<!--
🎤 SCRIPT · Slide 10 · Backend layered architecture
⏱ ~26 seconds · 5-min cut: KEEP

"Inside the backend — seven layers, all talking one direction.

Routes parse requests. Dependencies handle auth and quota.

Agents orchestrate the AI. MCP servers are the tool layer — seven of them.

Services hold business logic — seventeen modules today. Repositories wrap database access — nineteen of them.

And the database adapter — SQLite in dev, Postgres in production.

Each layer talks down, never up. That's how we replace any layer in isolation."

🎬 Walk layer by layer. Land "talks down, never up" slowly.
➡ Next: "Let me show you what the kid actually sees."
-->

---

## The buddy — *three states, one identity*

![buddy states h:410](assets/buddy-states.png)

<small>**Empty state** → **Customize** (name, avatar, animal-emoji, theme) → **Chat** (three starter prompts that route to specialists). Three React states. One persona, persisted across every session.</small>

<!--
🎤 SCRIPT · Slide 11 · The buddy (3-state strip)
⏱ ~22 seconds · 5-min cut: KEEP

"Here's the buddy — three states, one identity.

First, the empty state — no buddy yet.

Then customize — the child names their buddy, picks an avatar, chooses a theme. Kids love this part.

Then chat — the buddy greets them with three starter prompts, each routing to a specialist.

Three states, one persona, persisted across every session."

🎬 Point at each pane. "Kids love this part" — say it casually, like an observation.
➡ Next: "And here's what the buddy actually creates."
-->

---

## What the buddy creates — *three surfaces, one character*

![real creative outputs h:430](assets/system-creates.png)

| 📖 Image-to-Story | 🌟 Interactive Story | 🎙️ Kids Daily |
|---|---|---|
| **The Singing Shells of Coral Bay** — art story with illustrated cover + 2-page narrative | **Ember and the Golden Dragon's Cozy Cloud** — branching scene with 3 "what happens next?" cards | **Amazing Animals and How We Keep Them Safe** — Kids Daily episode w/ cover art + transcript + audio |

<small>Same character — *Ember + the recurring crew* — across all three surfaces. **Real outputs from the live app, end to end.**</small>

<!--
🎤 SCRIPT · Slide 12 · What the buddy creates (real outputs)
⏱ ~28 seconds · 5-min cut: KEEP

"These are real outputs from the live app.

On the left — an art story. The child's drawing became a sixty-second narrative with their character, Ember.

In the middle — an interactive story. The same Ember, now in a branching adventure with three choices.

On the right — a kids daily episode. Ember again, as guest anchor, with transcript and audio.

Three surfaces, same character. Continuity made real — not just claimed."

🎬 Point at each pane. Say "Ember" each time — that makes continuity concrete.
➡ Next: "And kids share what they make — safely."
-->

---

## Community & sharing — *COPPA by schema, not by policy*

| Where most products fail | What we do |
|---|---|
| Posts JOIN to `users.name` for byline | `agent_name_snapshot`, `agent_avatar_id_snapshot`, and `agent_title_snapshot` are **snapshot columns** — written at post time, never JOINed |
| `users.email` accidentally leaks via API | Read paths can't reach `users` at all — schema doesn't allow it |
| Safety is a code-review checklist | Safety is a CHECK constraint + invariant test |

```
hub_posts (id, agent_name_snapshot, agent_avatar_id_snapshot, agent_title_snapshot, story_id, ...)
                              ▲ immutable persona snapshot — no user JOIN
```

<small>Result: every Hub post is bylined by **the buddy persona**, never by the child. Zero PII exposure. Verified by `test_hub_coppa_invariant.py`.</small>

<!--
🎤 SCRIPT · Slide 13 · Community & sharing (COPPA at schema)
⏱ ~24 seconds · 5-min cut: KEEP

"Kids share what they create — safely.

Most kid-AI products fail COPPA the same way: they join posts back to the users table for a byline, and a child's name leaks.

Our schema doesn't allow it. The hub-posts table has immutable persona snapshot columns. No read path joins the users table.

The unsafe query can't even be expressed. Safety is a schema invariant — with a test that enforces it."

🎬 The COPPA moat. Say "the unsafe query can't even be expressed" slowly.
➡ Next: "And the architecture is built to extend."
-->

---

## Open by design — *static team today, AgentDefinition extensions next*

```python
# Today: the proxy builds a fixed specialist map in _build_subagents().
subagents = {
    "image_story": image_story_agent,
    "interactive_story": interactive_story_agent,
    "kids_daily": kids_daily_agent,
}

# Future: adding a "music_story" specialist via AgentDefinition.
AgentDefinition(
    name="music_story",
    model="haiku",
    system_prompt=Path("prompts/music-story.md").read_text(),
    tools=["music_generator", "vector_search"],
    enabled_skills=["compose"],
)
```

<small>Today, routing is explicit and safety-gated. **A2A bridge** and dynamic `AgentDefinition` registration are future extension work.</small>

<!--
🎤 SCRIPT · Slide 14 · Open by design (extensibility)
⏱ ~24 seconds · 5-min cut: KEEP

"This architecture is open by design.

Today, the proxy builds a static specialist map. That keeps routing explicit and easy to test.

The next extension is AgentDefinition registration: a model, a prompt, tools, and skills. The safety gate still runs on every reply. Shared context still flows in.

And in the future, an A2A bridge lets external agent teams join — through the same contract."

🎬 Let the audience read the code. Land the split between today's static team and tomorrow's dynamic extension.
➡ Next: "And here's where we're headed."
-->

---

## Roadmap — *three phases shipped or nearly shipped, one vision*

![roadmap h:380](assets/roadmap.svg)

<!--
🎤 SCRIPT · Slide 15 · Roadmap (Phase 1 → 4)
⏱ ~30 seconds · 5-min cut: KEEP

"Our roadmap — two phases shipped, one nearly complete, one vision.

Phase one, the MVP — single agent, image-to-story, safety, TTS. Done.

Phase two, the agent team — multi-agent, memory, Kids Daily, community. Done.

Phase three, nearly complete — video, parent dashboard, gamification.

Phase four, the vision — autonomous.

We don't pitch features. We ship them."

🎬 Tap each phase card. Land "we don't pitch features, we ship them" slowly.
➡ Next: "And the engineering rigor behind that velocity."
-->

---

## Where we are

| Milestone | Status |
|---|---|
| **Phase 1** MVP — Single agent + image-to-story + safety + TTS | ✅ **95/95** shipped |
| **Phase 2** Multi-agent team + memory + news + community | ✅ **188/188** shipped |
| **Phase 3** Video · parent dashboard · gamification | 🚧 **30/32** shipped |

<br>

**Engineering rigor:** 700+ contract tests · per-reply programmatic safety (age-aware) · silent safety-bypass caught + fixed in 1 day · merge-train of 7 PRs landed last week

<small>*Add real numbers in Keynote: pilot users · sessions/week · feedback quotes.*</small>

<!--
🎤 SCRIPT · Slide 16 · Where we are
⏱ ~22 seconds · 5-min cut: KEEP

"Where we are today. Three hundred thirteen shipped work items out of three hundred fifteen tracked across milestones — phases one and two done, phase three nearly complete.

The engineering rigor: over seven hundred contract tests, per-reply safety, a silent safety bug we caught and fixed in twenty-four hours.

We don't pitch features. We ship them."

🎬 Speak numbers as words. If you have real pilot data, swap it in. Closing repeats slide 15 on purpose — lands the receipt.
➡ Next: "And we own our bugs too."
-->

---

## Failures we owned — *receipts, not theater*

| What we tried | How it broke | What we did about it |
|---|---|---|
| **SDK subprocess** for image-to-story | Railway exit -9 · OOM kills under load | Ported all 3 generation agents to direct API · ~50% memory drop |
| **`await check_content_safety({...})`** | `SdkMcpTool` wrapper not callable · `TypeError` swallowed → default 0.9 score | Caught + fixed in 24h · `.handler` calling convention · 3 agents, 1 PR |
| **Single agent + safety prompt** | Model occasionally produced unsafe replies | Per-reply programmatic safety subagent · age-aware · fail-closed retry |

<small>Most pitches hide bugs. We name ours — that's how you know we *actually* run safety like infrastructure.</small>

<!--
🎤 SCRIPT · Slide 17 · Failures we owned
⏱ ~26 seconds · 5-min cut: DEFAULT-CUT (keep for 6-min slot)

"This is the slide most pitches don't have — the bugs we caught.

One — we ran the SDK as a subprocess. Railway killed it on memory. We ported to a direct API and got half the memory back.

Two — we called the safety check the wrong way. A swallowed error meant stories shipped with a fake score. We caught it ourselves, fixed it in a day.

Three — a single agent with a safety prompt wasn't enough. So we built per-reply programmatic safety.

Most pitches hide bugs. We name ours."

🎬 Speak each row in ~7 seconds. The 24-hour bug story is the receipt — slow on it.
➡ Next: "Here's why this matters."
-->

---

<!-- _class: title -->

# Why this matters

- **Agentic from day one** — not a wrapper, not a prompt. Real SDK, real tools, real orchestration.
- **313 shipped / 315 tracked work items** across milestones — *execution proof*
- **Programmatic safety on every reply** — non-negotiable, code-enforced, not vibes
- **Community that protects child PII at the schema level** — COPPA by construction
- **A buddy that grows with the child** — character continuity across image, story, podcast, share

<br>

# *AI that grows up* ***with*** *kids — safely.*

<!--
🎤 SCRIPT · Slide 18 · Why this matters (CLOSING BOOKEND)
⏱ ~24 seconds · 5-min cut: KEEP

"Why this matters.

Agentic from day one — real SDK, real tools, real orchestration. Not a wrapper.

Three hundred thirteen shipped work items out of three hundred fifteen tracked across milestones — execution proof.

Programmatic safety on every reply — code-enforced, not vibes.

A community that protects child PII at the schema level.

A buddy that grows with the child.

[pause]

This is AI that grows up with kids — safely.

[pause — hold eye contact]

I'd love to take your questions."

🎬 Stack the lines briskly. Hard pause before "AI that grows up with kids — safely." Don't smile until you've asked for questions.
➡ End of pitch.
-->

---

## Appendix — technical deep-dive *(backup for Q&A)*

| Topic | One-line answer |
|---|---|
| **Specialist** | Static proxy entry with its own prompt, tools, and skill gates; future `AgentDefinition` registration can make this dynamic |
| **Subagent** | A specialist in the proxy's map · invoked through explicit intent routing and SDK delegation |
| **Agent team** | Proxy + 3 product subagents (image_story · interactive_story · kids_daily) + audio_narration tool + safety_review · all share the context bus |
| **Orchestrator** | The proxy ("My Agent") — routes intent · composes specialist outputs · runs safety_review on every reply |
| **Why this shape** | Bigger prompt → quality degrades w/ specialty count · prompt chaining → no shared state · agent team → shared context + parallel specialty + future A2A extensibility |
| **SDK** | `claude_agent_sdk` — `ClaudeSDKClient` + custom MCP servers via `@tool`; dynamic `AgentDefinition` registration is future extension work |
| **Intent routing** | `_classify_intent(utterance, age)` — deterministic keyword rules + LLM disambiguation · age 3-5 vague `"story?"` → image_story by default |
| **Per-reply safety** | `enforce_chat_safety()` after every proxy reply · age-aware threshold · `suggest_content_improvements` retry · `safety_blocked` SSE telemetry on fail |
| **Shared state** | `build_my_agent_context(user_id, child_id)` passes persona, tone, style, skills, topics, goals, child_id, and age; recurring characters flow through `character_repo` and vector memory |
| **COPPA pattern** | `hub_posts.agent_name_snapshot`, `agent_avatar_id_snapshot`, `agent_title_snapshot` — immutable snapshot columns; no read path JOINs `users` |
| **Streaming** | SSE event types: `status` · `progress` · `tool_use` · `tool_result` · `launch_flow` · `safety_blocked` · `result` · `complete` |
| **Testing** | 700+ contract tests · per-MCP-tool + per-agent + per-route contracts · pytest, `pytest-asyncio` |
| **Tech stack** | FastAPI + Pydantic v2 · SQLite (dev) / Postgres + pgvector (prod) · React 18 + TypeScript + Tailwind + TanStack Query |

<small>This slide is hidden by default. Reveal only if a judge probes the architecture.</small>

<!--
🎤 SCRIPT · Slide 19 · Appendix (Q&A backup, HIDDEN BY DEFAULT)
⏱ Variable · Only reveal during Q&A

This slide should be HIDDEN during the main presentation:
Keynote → right-click slide thumbnail → Skip Slide

Only reveal it if a judge asks a deep technical question. Then jump straight to the row that answers them.

Here are three example answers you might give out loud:

If they ask "what's the difference between an agent and a subagent?":
"Today, a specialist in our system is a static entry in the proxy's specialist map — it has its own prompt, tools, and skill gates. A subagent is one of those specialists invoked by the proxy based on the child's intent. AgentDefinition registration is the future extension path for new specialists."

If they ask "why didn't you just use a bigger prompt?":
"Two reasons. First, quality degrades as you stuff more specialties into one prompt — the model loses focus. And second, we'd lose the per-reply safety subagent as a separate gate, which is non-negotiable for a kids product."

If they ask "how is your COPPA pattern different from other kid-AI products?":
"Most teams enforce their kid-PII rules in code review. We enforce them in the schema. The hub_posts table has agent_name_snapshot, agent_avatar_id_snapshot, and agent_title_snapshot as immutable snapshot columns — written once at post time. No read path in our codebase JOINs the users table. The unsafe query literally can't be expressed in our schema."

🎬 Don't read the whole table out loud. Just jump to the row that answers the question and explain it conversationally.
-->
