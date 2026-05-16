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
⏱ ~8 seconds · 5-min cut: KEEP

"Good [morning/afternoon]. Kids Creative Workshop —
an agentic app for kids, built on Claude Agent SDK.

Let me start with a moment."

🎬 Delivery: Warm and slow. Don't rush the subtitle. Pause, then click.
➡ Transition: pivot directly to the emotional anchor on slide 2.
-->

---

<!-- _class: title -->

# A 5-year-old hands you a crayon drawing.

<br>

# *What if it became a story?*

<br>

# *In her character. Her voice. Her world.*

<!--
🎤 SCRIPT · Slide 2 · The moment
⏱ ~25 seconds · 5-min cut: KEEP

"A five-year-old hands you a crayon drawing.

[3-second pause]

What if it became a story?

[3-second pause]

In her character. Her voice. Her world.

[3-second pause]

Everything technical I'm about to show you exists in service of that moment."

🎬 Delivery: SLOW. The pauses are the slide. Don't fill the silence.
➡ Transition: "But today's AI can't do this. Here's why."
-->

---

## Today's AI fails kids in two opposite ways

|  | ChatGPT | Image generators |
|---|---|---|
| **Treats kid as** | input | object to replace |
| **Their drawing** | ignored | erased |
| **Their character** | forgotten | redesigned |
| **Their voice** | overridden | gone |

# Existing AI **extracts**. We **collaborate**.

<!--
🎤 SCRIPT · Slide 3 · Today's AI fails kids
⏱ ~20 seconds · 5-min cut: DEFAULT-CUT (optional)

"Today's AI fails kids in two opposite ways.

ChatGPT treats the kid as input — their drawing ignored,
their character forgotten, their voice overridden.

Image generators treat the kid as an object to replace —
their drawing erased, their character redesigned.

[brief pause]

Existing AI extracts. We collaborate."

🎬 Delivery: Quick. The contrast does the work. Don't dwell.
➡ Transition: "Here's what we built instead."
-->

---

# Meet **My Agent**

A personal AI buddy the child **names**, **customizes**, and **grows with**.

- **Recognizes** their recurring characters (Lightning the puppy is back)
- **Routes** their requests to the right specialist
- **Protects** every reply with a safety subagent before delivery
- **Shares** under the buddy's name — zero PII, COPPA by construction

<small>One chat surface. Four specialists. One non-negotiable safety gate.</small>

<!--
🎤 SCRIPT · Slide 4 · Meet My Agent
⏱ ~30 seconds · 5-min cut: KEEP

"Meet My Agent — a personal AI buddy the child names,
customizes, and grows with.

It RECOGNIZES their recurring characters. Lightning the
puppy from last week is back.

It ROUTES their requests to the right specialist.

It PROTECTS every reply with a safety subagent before
the child sees it.

And it SHARES under the buddy's name — never the child's.
COPPA by construction.

One chat surface. Four specialists. One non-negotiable
safety gate."

🎬 Delivery: Don't read the bullets — narrate over them. Use "Lightning the puppy" by name; concrete sticks.
➡ Transition: "Let me show you how we built it. We started simple."
-->

---

## Foundation — *one agent, four primitives*

Built on **Claude Agent SDK**:

<div class="cards cols-2">
  <div class="card">
    <span class="card-emoji">🧭</span>
    <span class="card-title">Prompt design</span>
    <span class="card-body">Markdown prompts versioned in git</span>
  </div>
  <div class="card">
    <span class="card-emoji">🔧</span>
    <span class="card-title">Tools</span>
    <span class="card-body">Custom MCP servers: vision · vector · safety · TTS</span>
  </div>
  <div class="card">
    <span class="card-emoji">🔌</span>
    <span class="card-title">MCP</span>
    <span class="card-body">Tool calls as first-class affordances — not string-parsing</span>
  </div>
  <div class="card">
    <span class="card-emoji">🛠️</span>
    <span class="card-title">Skills</span>
    <span class="card-body"><code>@tool</code> decorators · per-agent skill gating</span>
  </div>
</div>

<small>One agent. No orchestrator. Just an LLM with the right scaffolding.</small>

<!--
🎤 SCRIPT · Slide 5 · Foundation — single agent
⏱ ~35 seconds · 5-min cut: KEEP

"We started simple — one agent, built right.
Four primitives compose it, all on Claude Agent SDK.

PROMPT DESIGN — markdown files versioned in git,
not Python strings. Code-reviewable.

TOOLS — custom MCP servers we wrote ourselves:
vision analysis, vector search, safety check, TTS.

MCP itself — tool calls become first-class
agent affordances, not parsed-string hacks.

SKILLS — composable behaviors with the @tool
decorator, gated per agent via enabled_skills.

One agent. No orchestrator yet. Just an LLM with
the right scaffolding."

🎬 Delivery: Point at each card as you name it. Don't read every word — narrate.
➡ Transition: "And that single agent already gave us three properties kids felt."
-->

---

## Three properties — kids feel them *immediately*

| 🌊 **Interactive** | 💡 **Proactive** | 🧠 **Persistent** |
|---|---|---|
| Streaming SSE — story writes itself, token by token | Recommends next moves · recalls recurring characters | Memory across sessions — same buddy for life |
| *"It's writing right now!"* | *"Lightning the puppy is back!"* | *"My buddy remembers."* |

<small>One agent. Three properties. **Already a real product.**</small>

<!--
🎤 SCRIPT · Slide 6 · Three properties
⏱ ~35 seconds · 5-min cut: KEEP

"Three properties kids felt immediately.

INTERACTIVE — Server-Sent Events stream the story
token by token. The kid watches it write itself.
'It's writing right now!'

PROACTIVE — the buddy suggests next moves and
recalls recurring characters across sessions.
'Lightning the puppy is back!'

PERSISTENT — character memory and agent memory
survive across sessions. Same buddy persona,
for life.

One agent. Three properties. Already a real product."

🎬 Delivery: End on "already a real product" — that's the pivot. Pause briefly. Then the next slide shows why one agent wasn't enough.
➡ Transition: "But one agent hit a ceiling."
-->

---

<!-- _backgroundColor: "#0F172A" -->
<!-- _color: "#F8FAFC" -->
<!-- _class: dark -->

## Extending to a team — *responsive + dynamic*

One agent hit a ceiling. Branching stories, news podcasts, per-reply safety — each needed its own expertise. We extended to an **agent team** — still on Claude Agent SDK.

![architecture diagram h:380](assets/architecture.svg)

**Unlocks**: 🎯 **responsive** · 🎨 **dynamic** · ➕ **A2A extensible**

<!--
🎤 SCRIPT · Slide 7 · Multi-agent team (CENTERPIECE)
⏱ ~50 seconds · 5-min cut: KEEP

"Branching adventures, daily podcasts, per-reply
safety — each needed its own expertise. So we
extended to an agent team. Still on Claude Agent SDK.

[point at proxy node — top of diagram]

The child's message comes in. The proxy ORCHESTRATES —
routes the intent with deterministic rules plus LLM
disambiguation.

[point at the four specialists]

Four specialists. Image story, interactive story,
kids daily, audio narration. Each has its own prompt,
tools, and skill set.

[point at safety_review — pause for emphasis]

Every reply passes through safety_review. That subagent
is the non-negotiable gate before anything reaches
the child.

[point at the shared context bus]

And underneath everything — SHARED CONTEXT. Persona,
child ID, recurring characters — flows to every agent.
So Lightning the puppy is the same dog in the story
AS in the podcast.

This unlocks responsive — right specialist in
milliseconds. Dynamic — different experience per turn.
And A2A extensible — new specialists plug in by
registering one AgentDefinition."

🎬 Delivery: This is the CENTERPIECE. Walk top-to-bottom. PAUSE after "before anything reaches the child" — let it land.
➡ Transition: "These weren't accidents — every primitive earned its place."
-->

---

## Decisions, not defaults — *every primitive earned its place*

| Decision | Alternative we rejected | What we chose | Why |
|---|---|---|---|
| **Prompts** | Python f-strings inline in code | Markdown files in `backend/src/prompts/` — `story-generation.md`, `age-adapter.md`, `interactive-story.md` | Versioned · code-reviewable · age-stratified per file |
| **Tools** | Direct API calls in agent loops | Custom MCP servers · typed JSON envelopes · `.handler` calling convention | Composable · testable · independently versionable |
| **Skills** | Hardcoded behaviors per agent class | `enabled_skills` field on `AgentDefinition` · `_enabled(agent, skill)` runs server-side | Per-age gating · A2A plug-in · single registration |
| **Multi-agent** | Bigger prompt + conditional branching | Proxy + 4 subagents + shared context bus | Specialty isolation · safety_review on **every** reply · responsive routing |

**Vocabulary** — *agent* · *subagent* · *team* · *orchestrator* — each role is precise. See appendix.

<!--
🎤 SCRIPT · Slide 8 · Decisions, not defaults
⏱ ~30 seconds · 5-min cut: DEFAULT-CUT (keep for 6-min slot)

"Every primitive on the previous slides was a decision.

PROMPTS — we could have inlined them as Python f-strings.
We chose markdown files in git. Versioned. Code-reviewable.
Age-stratified per file.

TOOLS — we could have called the API directly inside
agent code. We chose custom MCP servers with typed
envelopes. Composable. Testable.

SKILLS — we could have hardcoded behaviors per agent.
We chose enabled_skills as a field on AgentDefinition —
per-age gating, A2A extensible, server-side gate.

MULTI-AGENT — we could have written a bigger prompt
with branching. We chose a proxy plus four subagents.
Each specialty isolated. Safety subagent on EVERY reply.

We didn't adopt defaults."

🎬 Delivery: Walk row by row, ~7 seconds each. Land hard on "We didn't adopt defaults."
➡ Transition: "Three layers, six bets — here's where we innovate."
-->

---

## Where we innovate — *three layers, six bets*

| 🤖 **Agentic stack** | 🛡️ **Safety architecture** | 🌟 **Kid experience** |
|---|---|---|
| **Multi-agent + shared state** on Claude Agent SDK | **Per-reply programmatic safety** — age-aware (0.90 / 0.85) | **Character continuity** across image · story · podcast · share |
| **A2A extensible** — one `AgentDefinition` to add a specialist | **COPPA at the schema level** — the unsafe JOIN *can't be expressed* | **One buddy, N specialists, one identity** |

<small>Most kid-AI products ship **one** of these. We ship **all six**.</small>

<!--
🎤 SCRIPT · Slide 9 · Innovation moats
⏱ ~30 seconds · 5-min cut: KEEP

"Three layers. Six specific bets.

AGENTIC STACK — multi-agent with shared state on Claude
Agent SDK. A2A extensible — new specialists plug in
by registering one AgentDefinition.

SAFETY ARCHITECTURE — per-reply programmatic safety,
age-aware thresholds. And COPPA enforced AT THE SCHEMA
LEVEL. The unsafe JOIN can't even be expressed.

KID EXPERIENCE — character continuity across image,
story, podcast, and community. One buddy, many
specialists, one identity.

[brief pause]

Most kid-AI products ship ONE of these.

We ship ALL SIX."

🎬 Delivery: Read each cell as a defensible CLAIM, not a feature list. PAUSE before the closing line. Land hard on "all six."
➡ Transition: "Here's what kids actually do."
-->

---

## What kids actually do — *one chat, four specialists*

![product hero h:380](assets/product-hero.png)

The buddy's three starter prompts map to three specialists: **bedtime story** → `image_story` · **news for kids** → `kids_daily` · **choose-your-own** → `interactive_story`. One chat. One persona. The orchestrator dispatches.

> 🎬 **Live demo here — 15 seconds.** Open the app. Draw → buddy generates a story with their character.

<!--
🎤 SCRIPT · Slide 10 · Product proof + demo beat
⏱ ~35 seconds · 5-min cut: KEEP

"You can see the buddy here — Dianna in this case —
offering three starter prompts.

Each one routes to a different specialist underneath.

'Tell me a bedtime story' goes to image_story.

'What's in the news for kids' goes to kids_daily.

'Choose your own adventure' goes to interactive_story.

One chat surface. The multi-agent team behind it.

[OPTIONAL — 15-second live demo here. Open the app.
Draw → buddy generates a story with their character.
Pick ONE flow, not all four. Let it land.]"

🎬 Delivery: Point at the hero screenshot. Read the 3 prompts. Make the mapping to specialists EXPLICIT — it's the proof of the slide-7 architecture.
➡ Transition: "Here's where we are in shipping this."
-->

---

## Where we are

| Milestone | Status |
|---|---|
| **Phase 1** MVP — Single agent + image-to-story + safety + TTS | ✅ **92/92** shipped |
| **Phase 2** Multi-agent team + memory + news + community | ✅ **180/180** shipped |
| **Phase 3** Video · parent dashboard · gamification | 🔜 In design |

<br>

**Engineering rigor:** 700+ contract tests · per-reply programmatic safety (age-aware) · silent safety-bypass caught + fixed in 1 day · merge-train of 7 PRs landed last week

<small>*Add real numbers in Keynote: pilot users · sessions/week · feedback quotes.*</small>

<!--
🎤 SCRIPT · Slide 11 · Where we are
⏱ ~25 seconds · 5-min cut: KEEP

"Two hundred seventy-two stories shipped across
three milestones.

Phase 1 — MVP, single agent — done.
Phase 2 — multi-agent team plus community — done.
Phase 3 — video and parent dashboard — in design.

Engineering rigor matters as much as features.

Seven hundred contract tests. Per-reply programmatic
safety. A silent safety-bypass we caught and fixed
in twenty-four hours. A merge train of seven PRs
landed last week.

We don't pitch features — we ship them."

🎬 Delivery: Speak the numbers slowly. "Two hundred seventy-two" beats "272/272" by a long way out loud. If you have real pilot numbers, replace the placeholder.
➡ Transition: "And we own our bugs too."
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
🎤 SCRIPT · Slide 12 · Failures we owned
⏱ ~30 seconds · 5-min cut: DEFAULT-CUT (keep for 6-min slot)

"And we own our bugs.

We tried the SDK subprocess for image-to-story.
Railway killed it — out-of-memory under load.
So we ported all three generation agents to direct
API. Got half the memory back.

We tried calling check_content_safety directly.
The wrapper isn't callable. The TypeError got
swallowed. Every story shipped with a default
0.9 score. We caught it ourselves and fixed it
in twenty-four hours.

We tried single agent plus a safety prompt.
The model occasionally produced unsafe replies.
So we built per-reply programmatic safety with
suggest-and-retry.

Most pitches hide bugs. We name ours."

🎬 Delivery: Counter-intuitive slide. Speak each row in ~9 seconds. The 24-hour bypass story is the receipt — speak it slowly.
➡ Transition: "Here's why this matters."
-->

---

<!-- _class: title -->

# Why this matters

- **Agentic from day one** — not a wrapper, not a prompt. Real SDK, real tools, real orchestration.
- **272 stories shipped** across 3 milestones — *execution proof*
- **Programmatic safety on every reply** — non-negotiable, code-enforced, not vibes
- **Community that protects child PII at the schema level** — COPPA by construction
- **A buddy that grows with the child** — character continuity across image, story, podcast, share

<br>

# *AI that grows up* ***with*** *kids — safely.*

<!--
🎤 SCRIPT · Slide 13 · Why this matters (CLOSING BOOKEND)
⏱ ~25 seconds · 5-min cut: KEEP

"Why this matters.

Agentic from day one — not a wrapper, not a prompt.
Real SDK. Real tools. Real orchestration.

272 stories shipped across three milestones —
execution proof.

Programmatic safety on every reply — non-negotiable,
code-enforced, not vibes.

A community that protects child PII at the schema
level — COPPA by construction.

A buddy that grows with the child — character
continuity across image, story, podcast, and share.

[PAUSE]

AI that grows up WITH kids — safely.

[PAUSE — hold eye contact, don't fill the silence]

Happy to take questions."

🎬 Delivery: Read the achievements briskly. PAUSE before the closing line. Deliver it SLOWLY, holding eye contact. Don't smile until you've said "happy to take questions."
➡ End of pitch.
-->

---

## Appendix — technical deep-dive *(backup for Q&A)*

| Topic | One-line answer |
|---|---|
| **Agent** | `AgentDefinition(model="haiku", system_prompt=..., tools=[...], enabled_skills=[...])` — one specialist w/ a curated capability set |
| **Subagent** | An agent registered under the proxy's `agents=` dict · invoked via the SDK's `Agent` tool delegation |
| **Agent team** | Proxy + 4 subagents (image_story · interactive_story · kids_daily · audio_narration) + safety_review · all share the context bus |
| **Orchestrator** | The proxy ("My Agent") — routes intent · composes specialist outputs · runs safety_review on every reply |
| **Why this shape** | Bigger prompt → quality degrades w/ specialty count · prompt chaining → no shared state · agent team → shared context + parallel specialty + A2A extensibility |
| **SDK** | `claude_agent_sdk` — `ClaudeSDKClient` + `AgentDefinition`s + custom MCP servers via `@tool` |
| **Intent routing** | `_classify_intent(utterance, age)` — deterministic keyword rules + LLM disambiguation · age 3-5 vague `"story?"` → image_story by default |
| **Per-reply safety** | `enforce_chat_safety()` after every proxy reply · age-aware threshold · `suggest_content_improvements` retry · `safety_blocked` SSE telemetry on fail |
| **Shared state** | `build_my_agent_context(user_id, child_id)` passes persona + recurring characters to every specialist's system prompt |
| **COPPA pattern** | `hub_posts.agent_name`, `agent_avatar`, `agent_title` — immutable snapshot columns; no read path JOINs `users` |
| **Streaming** | SSE event types: `status` · `progress` · `tool_use` · `tool_result` · `launch_flow` · `safety_blocked` · `result` · `complete` |
| **Testing** | 700+ contract tests · per-MCP-tool + per-agent + per-route contracts · pytest, `pytest-asyncio` |
| **Tech stack** | FastAPI + Pydantic v2 · SQLite (dev) / Postgres + pgvector (prod) · React 18 + TypeScript + Tailwind + TanStack Query |

<small>This slide is hidden by default. Reveal only if a judge probes the architecture.</small>

<!--
🎤 SCRIPT · Slide 14 · Appendix (Q&A backup, HIDDEN BY DEFAULT)
⏱ Variable · Only reveal during Q&A

This slide should be HIDDEN during the main presentation:
Keynote → right-click slide thumbnail → Skip Slide

REVEAL only if a judge asks a deep technical question.
Then jump straight to the relevant row.

Example responses you might say:

If asked "what's the difference between agent and subagent?":
"An agent is an AgentDefinition — model, system prompt,
tools, and skills. A subagent is one of those registered
under our proxy's agents dictionary. The SDK's Agent tool
lets the proxy delegate to a subagent based on intent."

If asked "why not just a bigger prompt?":
"Quality degrades as specialty count grows in one prompt.
And we'd lose per-reply safety as a separate subagent —
which is the non-negotiable gate."

If asked "how is your COPPA pattern different?":
"Most teams enforce kid-PII rules in code review.
We enforce them in the schema. The hub_posts table has
agent_name, agent_avatar, agent_title as immutable
snapshot columns. There's no read path that JOINs users.
The unsafe query can't be expressed."

🎬 Don't read the whole table out loud — jump to the row that answers the question.
-->
