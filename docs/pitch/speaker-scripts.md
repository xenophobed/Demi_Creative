# Speaker scripts — Kids Creative Workshop pitch deck

> All 19 scripts, condensed — every key fact kept, filler cut.
> Read straight from the page. Re-time with a stopwatch; aim for a 6-min slot,
> drop slide 17 (Failures) if tight. Slide 19 is Q&A backup — only used if asked.

## Slide 1 — Title
*~7 seconds · 5-min cut: KEEP*

> "Good morning. This is Kids Creative Workshop — an agentic app for kids, built on the Claude Agent SDK. Let me start with a moment."

---

## Slide 2 — Three moments
*~22 seconds · 5-min cut: KEEP*

> "Three moments in a kid's day.
>
> She hands her drawing to her buddy — and it becomes a story, in her character.
>
> [pause]
>
> That same character stars in the next adventure — her choices, her ending.
>
> [pause]
>
> And tomorrow's news arrives as her own podcast — kid-safe.
>
> One buddy. Three moments. Her world, every time."

---

## Slide 3 — Four problems
*~24 seconds · 5-min cut: KEEP*

> "Today's AI fails kids on four fronts.
>
> One — it's not personalized. Generic output, no memory of her characters or her age.
>
> Two — it's not customized. Every child gets the same prompt, the same answer.
>
> Three — no kid-suited news. Today's news products are adult-first.
>
> Four — no persistence. Every session resets — last week's character is forgotten.
>
> Existing AI extracts from kids. We collaborate with them."

---

## Slide 4 — Our agent's abilities
*~28 seconds · 5-min cut: KEEP*

> "Four problems, four abilities — one for each.
>
> Not personalized — persona and character memory. Recurring characters recalled across every session.
>
> Not customized — per-child agent definitions, with skills gated by age.
>
> No kid-news — a dedicated kids-daily specialist: age-stratified, safety-reviewed, in the buddy's voice.
>
> No persistence — agent and character repositories, plus vector search. One buddy, for life.
>
> And kids feel three things: interactive, proactive, persistent."

---

## Slide 5 — Six agentic features
*~32 seconds · 5-min cut: KEEP*

> "Six agentic features, one stack.
>
> Interactive — streaming SSE, so the story writes itself token by token.
>
> Responsive — Claude Haiku for speed, plus deterministic and LLM intent routing.
>
> Proactive — vector recall surfaces recurring characters and suggests next moves.
>
> Persistent — vector DB plus SQL repositories hold the buddy across sessions.
>
> Reactive — every reply runs through our safety tool, with age-aware thresholds.
>
> And autonomous — that's next: multi-step planning, scheduled buddy initiatives."

---

## Slide 6 — Four architecture patterns
*~26 seconds · 5-min cut: KEEP*

> "Four agent architecture patterns — and we use all four.
>
> Single agent — one job, linear inference. We use it for text-to-speech.
>
> Sub-agent fan-out — the same task in parallel, for speed.
>
> Agent team — multiple agents collaborating by role, each an AgentDefinition. That's our My Agent.
>
> Multi-agent orchestrator — agents created dynamically at runtime. That's what makes us extensible.
>
> Shared state flows to every specialist through the agent context. A2A to external teams is future work."

---

## Slide 7 — Six memory types
*~28 seconds · 5-min cut: KEEP*

> "Memory is what makes a buddy feel like a buddy. Six layers.
>
> Session — this conversation's history.
>
> Working — the per-turn execution context.
>
> Episodic — past creations: stories, podcasts, choices.
>
> Factual — persona, child profile, preferences.
>
> Semantic — embeddings of characters and themes, in our vector store.
>
> Procedural — how the buddy generates each kind of content.
>
> Put it together: the buddy remembers, understands, acts, talks, and reasons in flight."

---

## Slide 8 — The team (CENTERPIECE)
*~38 seconds · 5-min cut: KEEP*

> "This is the architecture. Each surface needed its own expertise — so we built an agent team, on the Claude Agent SDK.
>
> [point at the proxy]
>
> A child's message hits the proxy first. It orchestrates — routes intent with deterministic rules plus LLM disambiguation.
>
> [point at the specialists]
>
> Then the right capability runs — image story, interactive story, and Kids Daily are specialists; audio narration is a reusable TTS tool. Each has its own prompt and tools.
>
> [point at safety_review — pause]
>
> Every reply passes through safety review before it reaches the child. That's the non-negotiable gate.
>
> [point at the context bus]
>
> And underneath, shared context — persona, characters — flows to every agent. Same character in the story and the podcast.
>
> This unlocks responsive, dynamic, and A2A-extensible."

---

## Slide 9 — Three-layer infrastructure
*~24 seconds · 5-min cut: KEEP*

> "The infrastructure is three managed services.
>
> Vercel hosts the frontend — a React app on a CDN.
>
> Railway runs the FastAPI backend — the Agent SDK and seven MCP servers, auto-deployed from main.
>
> Supabase is the database — Postgres with pgvector, plus auth and storage.
>
> Plus AI APIs — Anthropic, OpenAI, ElevenLabs, Tavily.
>
> Each service does one job. No magic, no monorepo coupling."

---

## Slide 10 — Backend layered architecture
*~26 seconds · 5-min cut: KEEP*

> "Inside the backend — seven layers, all talking one direction.
>
> Routes parse requests. Dependencies handle auth and quota.
>
> Agents orchestrate the AI. MCP servers are the tool layer — seven of them.
>
> Services hold business logic. Repositories wrap database access — twenty of them.
>
> And the database adapter — SQLite in dev, Postgres in production.
>
> Each layer talks down, never up. That's how we replace any layer in isolation."

---

## Slide 11 — The buddy (3-state strip)
*~22 seconds · 5-min cut: KEEP*

> "Here's the buddy — three states, one identity.
>
> First, the empty state — no buddy yet.
>
> Then customize — the child names their buddy, picks an avatar, chooses a theme. Kids love this part.
>
> Then chat — the buddy greets them with three starter prompts, each routing to a specialist.
>
> Three states, one persona, persisted across every session."

---

## Slide 12 — What the buddy creates (real outputs)
*~28 seconds · 5-min cut: KEEP*

> "These are real outputs from the live app.
>
> On the left — an art story. The child's drawing became a sixty-second narrative with their character, Ember.
>
> In the middle — an interactive story. The same Ember, now in a branching adventure with three choices.
>
> On the right — a kids daily episode. Ember again, as guest anchor, with transcript and audio.
>
> Three surfaces, same character. Continuity made real — not just claimed."

---

## Slide 13 — Community & sharing (COPPA at schema)
*~24 seconds · 5-min cut: KEEP*

> "Kids share what they create — safely.
>
> Most kid-AI products fail COPPA the same way: they join posts back to the users table for a byline, and a child's name leaks.
>
> Our schema doesn't allow it. The hub-posts table has immutable persona snapshot columns. No read path joins the users table.
>
> The unsafe query can't even be expressed. Safety is a schema invariant — with a test that enforces it."

---

## Slide 14 — Open by design (extensibility)
*~24 seconds · 5-min cut: KEEP*

> "This architecture is open by design.
>
> Adding a new specialist takes one AgentDefinition — a model, a prompt, its tools, its skills.
>
> Register it, and routing picks it up automatically. The safety gate still runs on every reply. Shared context still flows in.
>
> And in the future, an A2A bridge lets external agent teams join — through the same contract."

---

## Slide 15 — Roadmap (Phase 1 → 4)
*~30 seconds · 5-min cut: KEEP*

> "Our roadmap — two phases shipped, two ahead.
>
> Phase one, the MVP — single agent, image-to-story, safety, TTS. Done.
>
> Phase two, the agent team — multi-agent, memory, Kids Daily, community. Done.
>
> Phase three, in design — video, parent dashboard, gamification.
>
> Phase four, the vision — autonomous.
>
> We don't pitch features. We ship them."

---

## Slide 16 — Where we are
*~22 seconds · 5-min cut: KEEP*

> "Where we are today. Two hundred ninety-two tracked work items — phases one and two done, phase three moving into build.
>
> The engineering rigor: over seven hundred contract tests, per-reply safety, a silent safety bug we caught and fixed in twenty-four hours.
>
> We don't pitch features. We ship them."

---

## Slide 17 — Failures we owned
*~26 seconds · 5-min cut: DEFAULT-CUT (keep for 6-min slot)*

> "This is the slide most pitches don't have — the bugs we caught.
>
> One — we ran the SDK as a subprocess. Railway killed it on memory. We ported to a direct API and got half the memory back.
>
> Two — we called the safety check the wrong way. A swallowed error meant stories shipped with a fake score. We caught it ourselves, fixed it in a day.
>
> Three — a single agent with a safety prompt wasn't enough. So we built per-reply programmatic safety.
>
> Most pitches hide bugs. We name ours."

---

## Slide 18 — Why this matters (CLOSING BOOKEND)
*~24 seconds · 5-min cut: KEEP*

> "Why this matters.
>
> Agentic from day one — real SDK, real tools, real orchestration. Not a wrapper.
>
> 292 tracked work items across shipped and planned milestones — execution proof.
>
> Programmatic safety on every reply — code-enforced, not vibes.
>
> A community that protects child PII at the schema level.
>
> A buddy that grows with the child.
>
> [pause]
>
> This is AI that grows up with kids — safely.
>
> [pause — hold eye contact]
>
> I'd love to take your questions."

---

## Slide 19 — Appendix (Q&A backup, HIDDEN BY DEFAULT)
*Variable · Only reveal during Q&A*

> This slide should be HIDDEN during the main presentation:
> Keynote → right-click slide thumbnail → Skip Slide
>
> Only reveal it if a judge asks a deep technical question. Then jump straight to the row that answers them.
>
> Here are three example answers you might give out loud:
>
> If they ask "what's the difference between an agent and a subagent?":
> "An agent in our system is an AgentDefinition — it has a model, a system prompt, a set of tools, and a set of skills. A subagent is one of those registered underneath our proxy. The SDK's Agent tool is what lets the proxy delegate to a subagent based on the child's intent."
>
> If they ask "why didn't you just use a bigger prompt?":
> "Two reasons. First, quality degrades as you stuff more specialties into one prompt — the model loses focus. And second, we'd lose the per-reply safety subagent as a separate gate, which is non-negotiable for a kids product."
>
> If they ask "how is your COPPA pattern different from other kid-AI products?":
> "Most teams enforce their kid-PII rules in code review. We enforce them in the schema. The hub_posts table has agent_name, agent_avatar, and agent_title as immutable snapshot columns — written once at post time. No read path in our codebase JOINs the users table. The unsafe query literally can't be expressed in our schema."

---

