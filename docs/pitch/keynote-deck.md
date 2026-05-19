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

"Good morning, everyone. I'm here to tell you about Kids Creative Workshop. It's an agentic app for kids, built on the Claude Agent SDK. And before I get into how it works, I want to start with a moment."

🎬 Delivery: Warm and slow. Smile on "good morning." Pause briefly after "Claude Agent SDK." Then click forward.
➡ Transition: pivots directly into the emotional moment on slide 2.
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
⏱ ~30 seconds · 5-min cut: KEEP

"Picture three moments in a kid's day.

The first one: a five-year-old hands her drawing to her buddy, and watches it become a story — with her character, in her voice.

[pause for 2 seconds]

The second: that same character — the one she just invented — stars in the next adventure. Her choices, her ending.

[pause for 2 seconds]

The third: tomorrow morning, today's news arrives as her own podcast. Kid-safe, in her buddy's voice.

[pause for 3 seconds]

One buddy. Three kinds of moments. Her world, every time."

🎬 Delivery: Slow down a lot here. The pauses ARE the slide. Don't rush. If you feel the silence is awkward, it's probably the right length.
➡ Transition: "But today's AI fails her on every single one of those moments. Here's how."
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
⏱ ~30 seconds · 5-min cut: KEEP

"Today's AI fails kids on four fronts.

First, it's not personalized enough. Outputs are generic. There's no memory of her characters, her voice, or her age.

Second, it's not highly customized. Every child gets the same prompt and gets back the same answer. There's no buddy identity, no per-child capability set.

Third, there's no news that's actually suited for kids. Today's news products are adult-first. No age-aware filter, no narrative voice for kids.

And fourth, there's no long-term persistence. Every session resets. Lightning the puppy that the kid drew last Friday? Forgotten by Monday.

[pause briefly]

Existing AI extracts from kids. We want to collaborate with them."

🎬 Delivery: Number each problem clearly — "first," "second," "third," "fourth." That cadence helps the audience follow along with the 4-card grid on screen.
➡ Transition: "Let me show you how our agent's abilities fix each one of these."
-->

---

# Meet **My Agent** — *one ability per problem*

| Problem | Our agent's ability |
|---|---|
| Not personalized enough | **Persona + character memory** — buddy is named & customized; recurring characters recalled across sessions (`character_repo`) |
| Not highly customized | **Per-child `AgentDefinition` + skills gating** — age-aware capabilities (3–5 / 6–8 / 9–12); buddy persona shared as system context to every specialist |
| No suited news for kids | **`kids_daily` specialist** — age-stratified prompts + per-reply safety review; news arrives as a kid-safe podcast in the buddy's voice |
| No long-term persistence | **`agent_repo` + `character_repo` + vector search** — buddy persona and recurring characters survive every session; one buddy, for life |

<small>What kids feel: **interactive** (streaming) · **proactive** (recommendations + recall) · **persistent** (memory).</small>

<!--
🎤 SCRIPT · Slide 4 · Our agent's abilities
⏱ ~40 seconds · 5-min cut: KEEP

"So here's how we solve each one.

For "not personalized enough" — we built persona and character memory. The buddy is named by the child, customized by the child, and recurring characters like Lightning the puppy get recalled across every session through our character repository.

For "not highly customized" — each child gets their own agent definition, with skills gated by their age. Three to five, six to eight, nine to twelve — different capability sets for each. And the buddy's persona flows as system context to every specialist underneath.

For "no kid-news" — we have a dedicated kids-daily specialist. It uses age-stratified prompts, runs every reply through a safety review, and delivers the news as a kid-safe podcast in the buddy's own voice.

And for "no persistence" — we use an agent repository, a character repository, and vector search. The buddy survives every session. One buddy, for life.

And kids feel three things right away: the experience is interactive — the story streams as it writes itself. It's proactive — the buddy suggests and recalls. And it's persistent — same buddy persona, every time."

🎬 Delivery: Walk problem-to-solution. The 1-to-1 mapping is the structure — say "for X, we built Y" for each row. End on the three feelings — those are what stick in the kid's memory.
➡ Transition: "All of these abilities are built on a small set of SDK primitives. Let me show you."
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
⏱ ~45 seconds · 5-min cut: KEEP

"We've built six agentic features into one stack.

The first is interactive. We use server-sent events with async-generator agents, so the story writes itself token by token, right there on the kid's screen.

The second is responsive. We use Claude Haiku for speed. Our intent routing combines deterministic keyword rules with LLM disambiguation, and each agent has its own curated set of skills.

Third is proactive. Prompt engineering shapes the buddy's starter suggestions. Vector database recall surfaces recurring characters. And our character repository proposes the next move based on what the kid has done before.

Fourth is persistent. Vector database plus SQL repositories hold the buddy across sessions. We use ChromaDB locally and pgvector in production.

Fifth is reactive. Every reply runs through our safety MCP tool. We use age-aware thresholds — point-nine-zero for three to five year olds, point-eight-five for six to twelve. If a reply fails the safety check, we ask the model to suggest improvements and retry.

And the sixth one — autonomous — is the next frontier. Multi-step planning, self-prompted explore loops, scheduled buddy initiatives. We're one ceiling away from this."

🎬 Delivery: Walk row by row. Slow down on the reactive one — that's the safety story, the most important moat. When you say "autonomous," be clear it's future — say "this is what we're going to build next." Don't claim it as shipped.
➡ Transition: "But one agent alone hit a ceiling pretty quickly. So we extended to a team."
-->

---

## Four agent architecture patterns — *we use all four*

| # | Pattern | What it does | Where we use it |
|---|---|---|---|
| 1 | **🤖 Single agent** | One agent, one job · linear inference | Straight TTS via `audio_narration` |
| 2 | **🔀 Sub-agent fan-out** | Same task spawned in parallel for speed | Concurrent vision crops · parallel `character_repo` lookups |
| 3 | **👥 Agent team** | Multiple agents collaborate by **role** · defined via `AgentDefinition` | **My Agent**: proxy + 4 role specialists + `safety_review` |
| 4 | **🎼 Multi-agent orchestrator** | Agents created **dynamically** · A2A extensible to external teams | Proxy registers new `AgentDefinition`s at runtime |

<small>**Shared state** within a team flows through `build_my_agent_context()` — persona, child_id, recurring characters reach every specialist. **A2A** extends to external agent teams (future).</small>

<!--
🎤 SCRIPT · Slide 6 · Four architecture patterns
⏱ ~32 seconds · 5-min cut: KEEP

"There are four agent architecture patterns, and we use all four.

The first is the single agent. One agent, one job, linear inference. We use this for simple flows like our audio narration — it just turns text into speech, no orchestration needed.

The second is sub-agent fan-out. The same task gets spawned in parallel for speed. We use this when we need concurrent vision crops, or when we want to look up multiple characters from our repository at once.

The third is the agent team. Multiple agents collaborate by role, each defined via an AgentDefinition. This is what our My Agent is — a proxy plus four role specialists plus a safety review subagent.

The fourth is the multi-agent orchestrator. Agents get created dynamically at runtime. This is what makes us extensible — the proxy can register new AgentDefinitions on the fly.

Now within a team, shared state flows through what we call the agent context — the persona, the child ID, the recurring characters all reach every specialist. And in the future, we'll extend this with agent-to-agent bridges to external teams."

🎬 Delivery: Walk pattern by pattern with the concrete example. The "we use all four" line is the punchline — most teams pick one and force-fit everything else.
➡ Transition: "And every agent in the team is wired to six memory layers."
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
⏱ ~38 seconds · 5-min cut: KEEP

"Memory is what makes a buddy actually feel like a buddy. We've broken it into six layers.

Session memory — what was said in this conversation. We store it in the agent chat repository.

Working memory — the per-turn execution context. The in-flight tool results, the persona, the recurring characters. All passed to every specialist via the agent context builder.

Episodic memory — the kid's past creations. Stories, interactive sessions, kids-daily episodes. Three tables.

Factual memory — buddy persona, child profile, preferences. That lives in the agent repository, the preference repository, and the users table.

Semantic memory — embeddings of characters, themes, narrative style. ChromaDB locally, pgvector in production, accessed via our vector search MCP.

And procedural memory — how the buddy actually generates each kind of content. That's our versioned markdown prompts, our at-tool skills, and the enabled-skills gating on each agent.

So put it all together: the buddy remembers, understands, acts, talks, and reasons in flight."

🎬 Delivery: Walk each layer briskly. Slow down on procedural memory — that's the one most teams don't have, and it's worth a beat. End on the closing line slowly: "remembers, understands, acts, talks, and reasons in flight."
➡ Transition: "And here's how those memory layers and the four patterns compose together in our actual team."
-->

---

<!-- _backgroundColor: "#0F172A" -->
<!-- _color: "#F8FAFC" -->
<!-- _class: dark -->

## The team — *one proxy, four specialists, one safety gate*

One agent hit a ceiling. Branching stories, news podcasts, per-reply safety — each needed its own expertise. We extended to an **agent team** — still on Claude Agent SDK.

![architecture diagram h:380](assets/architecture.svg)

**Unlocks**: 🎯 **responsive** · 🎨 **dynamic** · ➕ **A2A extensible**

<!--
🎤 SCRIPT · Slide 8 · The team (CENTERPIECE)
⏱ ~55 seconds · 5-min cut: KEEP

"This is the architecture. Branching adventures, daily podcasts, per-reply safety — each one needed its own expertise. So we extended to an agent team. All still on the Claude Agent SDK.

[point at the proxy node at the top]

When a child sends a message, the proxy receives it first. The proxy orchestrates everything — it routes the intent using a mix of deterministic rules and LLM disambiguation.

[point at the four specialists in the middle]

Then it hands off to one of four specialists. Image story, interactive story, kids daily, or audio narration. Each one has its own prompt, its own tools, and its own skill set.

[point at safety_review at the bottom — pause briefly]

But here's the part that earns the trust. Every reply passes through safety review. That subagent is the non-negotiable gate before anything ever reaches the child.

[point at the shared context bus underneath]

And underneath all of it — the shared context. Persona, child ID, recurring characters — they all flow to every agent. So Lightning the puppy in the story is the same Lightning in the podcast. The character continuity is built in at the architecture level.

This unlocks three things. We're responsive — the right specialist runs in milliseconds. We're dynamic — different experience per turn, without changing the chat surface. And we're A2A extensible — adding a new specialist takes one AgentDefinition."

🎬 Delivery: This is the centerpiece slide. Walk top to bottom, taking your time. Pause after "before it ever reaches the child" — that's the moment that earns judges' trust. Don't rush.
➡ Transition: "None of these were accidents. Every primitive in this architecture earned its place."
-->

---

## Three-layer infrastructure — *each service does one thing*

![infrastructure h:420](assets/infrastructure.svg)

<!--
🎤 SCRIPT · Slide 9 · Three-layer infrastructure
⏱ ~32 seconds · 5-min cut: KEEP

"Now let me show you the infrastructure. Three managed services, one HTTPS hop between each.

At the top, Vercel hosts the frontend. It's a React single-page app served from a CDN — static files, fast everywhere.

In the middle, Railway runs the FastAPI backend. That's where the Claude Agent SDK lives, along with our seven MCP servers. Railway auto-deploys whenever we push to main.

At the bottom, Supabase is the database. Postgres plus pgvector for embeddings, plus auth, plus file storage. It's a managed service, always on.

And on the side, we use a handful of AI APIs — Anthropic for Claude, OpenAI for TTS, ElevenLabs for premium voices, and Tavily for kid-safe web search.

The thing I want you to take away is — each service does one job. Each HTTPS hop is one boundary. There's no magic, no monorepo coupling. We can replace any layer without touching the others."

🎬 Delivery: Trace the diagram top to bottom as you speak. The closing line — "no magic, no monorepo coupling" — is what earns the architecture credit. Say it slowly.
➡ Transition: "And inside the backend, the same discipline holds."
-->

---

## Backend — *seven layers, one direction*

![backend layers h:440](assets/backend-layers.svg)

<!--
🎤 SCRIPT · Slide 10 · Backend layered architecture
⏱ ~35 seconds · 5-min cut: KEEP

"Now inside the backend itself, we keep the same discipline. Seven layers, all talking in one direction.

At the top, routes parse the incoming request — we have fourteen route modules.

Below that, dependencies handle auth and quota — we use dependency injection, not inline checks.

Then the agents layer orchestrates the AI — that's our proxy plus four specialists, all on the Claude Agent SDK.

Below that, the MCP servers are the tool layer. Seven of them. Typed envelopes, with what we call the dot-handler calling convention.

Then services hold the business logic — fourteen modules, including the shared agent context builder.

Repositories wrap database access — twenty of them, one per table.

And at the very bottom, the database adapter. SQLite in dev, Postgres plus pgvector in production.

The rule is simple: each layer talks down, no layer talks up. That's how we replace any single layer without touching the others."

🎬 Delivery: Walk through layer by layer. The closing line — "each layer talks down, no layer talks up" — is the architectural discipline. Land it slowly.
➡ Transition: "OK, that's the system. Let me show you what the kid actually sees."
-->

---

## The buddy — *three states, one identity*

![buddy states h:410](assets/buddy-states.png)

<small>**Empty state** → **Customize** (name, avatar, animal-emoji, theme) → **Chat** (three starter prompts that route to specialists). Three React states. One persona, persisted across every session.</small>

<!--
🎤 SCRIPT · Slide 11 · The buddy (3-state strip)
⏱ ~30 seconds · 5-min cut: KEEP

"Here's the buddy. Three states, one identity.

When the child first arrives, there's no buddy yet — just an empty state inviting them to create one.

Then they customize. They name their buddy, pick an avatar emoji, choose a theme. This whole step takes about three minutes, and honestly, kids love this part more than the chat itself.

Once that's done, they land on the chat screen. The buddy greets them with three starter prompts, and each prompt routes to a different specialist underneath — story, news, or adventure.

Three React states. One persona. And the buddy persists across every session through our agent repository."

🎬 Delivery: Point at each pane on screen as you describe it. The "kids love this part more than the chat itself" line should feel like a real observation, not a brag — say it casually.
➡ Transition: "And here's what their buddy actually creates."
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
⏱ ~38 seconds · 5-min cut: KEEP

"These are real outputs from the live app. Let me walk you through them.

On the left — 'The Singing Shells of Coral Bay.' This is an art story. The child uploaded a drawing, and the buddy turned it into a sixty-second narrative — with their character, Ember, and the rest of the crew. The cover illustration on the left was generated too.

In the middle — 'Ember and the Golden Dragon's Cozy Cloud.' This is an interactive story. The same Ember from the art story is now starring in a branching adventure. Down at the bottom, you can see three choices the kid picks from — each one changes the ending.

And on the right — 'Amazing Animals and How We Keep Them Safe.' This is a kids daily episode. Cover art, transcript on the side, audio playback. And there's Ember again, this time as the guest anchor.

Three different surfaces. Same character across all of them. This is character continuity made real — not just claimed."

🎬 Delivery: Point at each pane in order. Say "Ember" by name on each one — that's what makes the character continuity concrete. The closing line — "made real, not just claimed" — is the moat.
➡ Transition: "And kids share what they make — safely. Here's how."
-->

---

## Community & sharing — *COPPA by schema, not by policy*

| Where most products fail | What we do |
|---|---|
| Posts JOIN to `users.name` for byline | `hub_posts.agent_name` is a **snapshot column** — written at post time, never JOINed |
| `users.email` accidentally leaks via API | Read paths can't reach `users` at all — schema doesn't allow it |
| Safety is a code-review checklist | Safety is a CHECK constraint + invariant test |

```
hub_posts (id, agent_name, agent_avatar, agent_title, story_id, ...)
                              ▲ immutable persona snapshot — no user JOIN
```

<small>Result: every Hub post is bylined by **the buddy persona**, never by the child. Zero PII exposure. Verified by `test_hub_coppa_invariant.py`.</small>

<!--
🎤 SCRIPT · Slide 13 · Community & sharing (COPPA at schema)
⏱ ~32 seconds · 5-min cut: KEEP

"OK, so kids share what they create. The question is — how do we do this safely?

Here's where most kid-AI products fail COPPA. They join posts back to the users table to get the byline. And somewhere along the way, a child's real name leaks out.

We don't have that risk, because our schema doesn't allow it.

The hub posts table has agent_name, agent_avatar, agent_title — immutable persona snapshot columns written once at post time. There's no read path that JOINs the users table. The unsafe query literally can't even be expressed.

Safety isn't a code review checklist for us. It's a schema invariant, and we have a contract test — test_hub_coppa_invariant — that fails if anyone ever tries to write that join."

🎬 Delivery: This is the COPPA moat. The line "the unsafe query literally can't even be expressed" is the key claim — say it slowly. The test name at the end is the receipt.
➡ Transition: "And the architecture is built to extend. Let me show you what that looks like in code."
-->

---

## Open by design — *one AgentDefinition adds a specialist*

```python
# Adding a "music_story" specialist to the agent team:
proxy.register(AgentDefinition(
    name="music_story",
    model="haiku",
    system_prompt=Path("prompts/music-story.md").read_text(),
    tools=["music_generator", "vector_search"],
    enabled_skills=["compose"],
))

# Routing picks it up automatically. Safety gate runs on every reply.
# Shared context (persona, child_id, recurring chars) flows in.
```

<small>**A2A bridge** (future) extends to external agent teams — partner specialists join the buddy's team via the same registration contract.</small>

<!--
🎤 SCRIPT · Slide 14 · Open by design (extensibility)
⏱ ~32 seconds · 5-min cut: KEEP

"This architecture is open by design. Let me show you.

If you want to add a brand new specialist to the buddy team, you write one AgentDefinition. That's it.

[gesture at the code on screen]

You give it a model — Haiku for speed. You give it a system prompt — that's a markdown file in our prompts folder. You give it a list of tools it can call. And you give it the skills it's allowed to use.

Once you register it, the routing picks it up automatically. The proxy's intent classifier reads the specialist's description and learns what trigger phrases route to it.

The safety gate runs on every reply, no matter which specialist generated it. And the shared context — persona, child ID, recurring characters — flows in to the new specialist just like the others.

And in the future, we'll add an A2A bridge. That lets external agent teams join the buddy's world, using exactly the same contract."

🎬 Delivery: Let the audience read the code on screen — don't rush. Then deliver the punchline — "one AgentDefinition" is the whole product claim, the moat. Slow on that.
➡ Transition: "And here's where we're headed next."
-->

---

## Roadmap — *two phases shipped, two ahead*

![roadmap h:380](assets/roadmap.svg)

<!--
🎤 SCRIPT · Slide 15 · Roadmap (Phase 1 → 4)
⏱ ~30 seconds · 5-min cut: KEEP

"This is our roadmap. Two phases shipped, two ahead.

Phase one was the MVP. Single agent. Image-to-story, plus safety, plus text-to-speech. Ninety-two out of ninety-two stories shipped — all done.

Phase two was the agent team. Multi-agent. Memory system. Kids Daily. Community. Per-reply safety. One hundred eighty out of one hundred eighty stories shipped — also done.

Phase three is in design right now — video and dynamic picture books, a parent dashboard, and gamification features.

Phase four is the vision — autonomous. Multi-step planning, scheduled buddy initiatives, and an A2A bridge so external agent teams can join.

And here's the thing I want you to remember about us — we don't just pitch features. We ship them."

🎬 Delivery: Tap each phase card on screen as you name it. The closing line — "we don't pitch features, we ship them" — is the receipt. Land it slowly.
➡ Transition: "And the engineering rigor behind that velocity is what I want to show you next."
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
🎤 SCRIPT · Slide 16 · Where we are
⏱ ~28 seconds · 5-min cut: KEEP

"So where are we today?

Two hundred and seventy-two stories shipped across three milestones. Phase one — the MVP single-agent — done. Phase two — the multi-agent team plus community — done. Phase three — video and the parent dashboard — in design.

Engineering rigor matters to us as much as features do.

We have over seven hundred contract tests. Per-reply programmatic safety on every output. We even caught and fixed a silent safety bypass in our own code in twenty-four hours. And we landed a merge train of seven pull requests just last week.

Like I said — we don't pitch features. We ship them."

🎬 Delivery: Speak the numbers out loud as words — "two hundred seventy-two" sounds bigger than "272." If you have real pilot users or feedback, swap them in for the test counts. The closing repeats slide 15's line — that's intentional, it lands the receipt.
➡ Transition: "And we own our bugs too. Let me show you some."
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
⏱ ~35 seconds · 5-min cut: DEFAULT-CUT (keep for 6-min slot)

"This is the slide most pitches don't have. We want to show you the bugs we caught — because how a team catches its own bugs tells you more than any feature list.

First one. We tried running the SDK as a subprocess for image-to-story. Railway kept killing it — out of memory under load. So we ported all three generation agents to a direct API. Got half the memory back overnight.

Second one. We were calling check-content-safety the wrong way. Turns out the wrapper isn't callable directly. The TypeError got swallowed silently. Every story was shipping with a default safety score of point-nine — which looked fine, but wasn't real. We caught it ourselves, in our own code, and fixed it in twenty-four hours.

Third one. We tried using a single agent plus a safety prompt. The model occasionally produced replies that weren't safe enough. So we built the per-reply programmatic safety with suggest-and-retry that you saw earlier.

Most pitches hide their bugs. We name ours."

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
🎤 SCRIPT · Slide 18 · Why this matters (CLOSING BOOKEND)
⏱ ~30 seconds · 5-min cut: KEEP

"So here's why this matters.

We're agentic from day one. This isn't a wrapper, it isn't just a prompt. It's a real SDK, with real tools, and real orchestration underneath.

We've shipped two hundred seventy-two stories across three milestones — that's our execution proof.

We have programmatic safety on every reply — non-negotiable, code-enforced. No vibes.

We've built a community that protects child PII at the schema level — COPPA by construction.

And we've built a buddy that genuinely grows with the child — character continuity across the image story, the interactive adventure, the podcast, and the share.

[pause for 2 seconds]

This is AI that grows up with kids — safely.

[pause, hold eye contact for 2 more seconds]

I'd love to take any questions you have."

🎬 Delivery: Read each "we've..." line briskly so they stack. Then pause hard before the closing line. Deliver "AI that grows up with kids — safely" slowly, holding eye contact. Don't smile until you've finished asking for questions.
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
🎤 SCRIPT · Slide 19 · Appendix (Q&A backup, HIDDEN BY DEFAULT)
⏱ Variable · Only reveal during Q&A

This slide should be HIDDEN during the main presentation:
Keynote → right-click slide thumbnail → Skip Slide

Only reveal it if a judge asks a deep technical question. Then jump straight to the row that answers them.

Here are three example answers you might give out loud:

If they ask "what's the difference between an agent and a subagent?":
"An agent in our system is an AgentDefinition — it has a model, a system prompt, a set of tools, and a set of skills. A subagent is one of those registered underneath our proxy. The SDK's Agent tool is what lets the proxy delegate to a subagent based on the child's intent."

If they ask "why didn't you just use a bigger prompt?":
"Two reasons. First, quality degrades as you stuff more specialties into one prompt — the model loses focus. And second, we'd lose the per-reply safety subagent as a separate gate, which is non-negotiable for a kids product."

If they ask "how is your COPPA pattern different from other kid-AI products?":
"Most teams enforce their kid-PII rules in code review. We enforce them in the schema. The hub_posts table has agent_name, agent_avatar, and agent_title as immutable snapshot columns — written once at post time. No read path in our codebase JOINs the users table. The unsafe query literally can't be expressed in our schema."

🎬 Don't read the whole table out loud. Just jump to the row that answers the question and explain it conversationally.
-->
