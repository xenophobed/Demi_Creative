# Speaker scripts — Kids Creative Workshop pitch deck

> All 19 scripts in natural spoken English. Read straight from the page.
> Total run time ~7:00. Default 6-min cut drops slide 17 → ~6:30.
> 5-min cut drops slides 9, 13, 14, 17.

---

## Slide 1 — Title · ⏱ ~8s

> *"Good morning, everyone. I'm here to tell you about Kids Creative Workshop. It's an agentic app for kids, built on the Claude Agent SDK. And before I get into how it works, I want to start with a moment."*

🎬 Smile on "good morning." Pause briefly after "Claude Agent SDK."

---

## Slide 2 — Three moments · ⏱ ~30s

> *"Picture three moments in a kid's day.*
>
> *The first one: a five-year-old hands her drawing to her buddy, and watches it become a story — with her character, in her voice.*
>
> *[pause for 2 seconds]*
>
> *The second: that same character — the one she just invented — stars in the next adventure. Her choices, her ending.*
>
> *[pause for 2 seconds]*
>
> *The third: tomorrow morning, today's news arrives as her own podcast. Kid-safe, in her buddy's voice.*
>
> *[pause for 3 seconds]*
>
> *One buddy. Three kinds of moments. Her world, every time."*

🎬 Slow down a lot here. The pauses ARE the slide. If it feels awkwardly silent, it's probably the right length.

---

## Slide 3 — Four problems · ⏱ ~30s

> *"Today's AI fails kids on four fronts.*
>
> *First, it's not personalized enough. Outputs are generic. There's no memory of her characters, her voice, or her age.*
>
> *Second, it's not highly customized. Every child gets the same prompt and gets back the same answer. There's no buddy identity, no per-child capability set.*
>
> *Third, there's no news that's actually suited for kids. Today's news products are adult-first. No age-aware filter, no narrative voice for kids.*
>
> *And fourth, there's no long-term persistence. Every session resets. Lightning the puppy that the kid drew last Friday? Forgotten by Monday.*
>
> *[brief pause]*
>
> *Existing AI extracts from kids. We want to collaborate with them."*

🎬 Number each problem clearly — "first," "second," "third," "fourth."

---

## Slide 4 — Our agent's abilities · ⏱ ~40s

> *"So here's how we solve each one.*
>
> *For "not personalized enough" — we built persona and character memory. The buddy is named by the child, customized by the child, and recurring characters like Lightning the puppy get recalled across every session through our character repository.*
>
> *For "not highly customized" — each child gets their own agent definition, with skills gated by their age. Three to five, six to eight, nine to twelve — different capability sets for each. And the buddy's persona flows as system context to every specialist underneath.*
>
> *For "no kid-news" — we have a dedicated kids-daily specialist. It uses age-stratified prompts, runs every reply through a safety review, and delivers the news as a kid-safe podcast in the buddy's own voice.*
>
> *And for "no persistence" — we use an agent repository, a character repository, and vector search. The buddy survives every session. One buddy, for life.*
>
> *And kids feel three things right away: the experience is interactive — the story streams as it writes itself. It's proactive — the buddy suggests and recalls. And it's persistent — same buddy persona, every time."*

🎬 Walk problem-to-solution: "for X, we built Y." End on the three feelings.

---

## Slide 5 — Six agentic features · ⏱ ~45s

> *"We've built six agentic features into one stack.*
>
> *The first is interactive. We use server-sent events with async-generator agents, so the story writes itself token by token, right there on the kid's screen.*
>
> *The second is responsive. We use Claude Haiku for speed. Our intent routing combines deterministic keyword rules with LLM disambiguation, and each agent has its own curated set of skills.*
>
> *Third is proactive. Prompt engineering shapes the buddy's starter suggestions. Vector database recall surfaces recurring characters. And our character repository proposes the next move based on what the kid has done before.*
>
> *Fourth is persistent. Vector database plus SQL repositories hold the buddy across sessions. We use ChromaDB locally and pgvector in production.*
>
> *Fifth is reactive. Every reply runs through our safety MCP tool. We use age-aware thresholds — point-nine-zero for three to five year olds, point-eight-five for six to twelve. If a reply fails the safety check, we ask the model to suggest improvements and retry.*
>
> *And the sixth one — autonomous — is the next frontier. Multi-step planning, self-prompted explore loops, scheduled buddy initiatives. We're one ceiling away from this."*

🎬 Slow down on reactive (the safety story). When you say "autonomous," be clear it's future — don't claim it as shipped.

---

## Slide 6 — Four architecture patterns · ⏱ ~32s

> *"There are four agent architecture patterns, and we use all four.*
>
> *The first is the single agent. One agent, one job, linear inference. We use this for simple flows like our audio narration — it just turns text into speech, no orchestration needed.*
>
> *The second is sub-agent fan-out. The same task gets spawned in parallel for speed. We use this when we need concurrent vision crops, or when we want to look up multiple characters from our repository at once.*
>
> *The third is the agent team. Multiple agents collaborate by role, each defined via an AgentDefinition. This is what our My Agent is — a proxy plus four role specialists plus a safety review subagent.*
>
> *The fourth is the multi-agent orchestrator. Agents get created dynamically at runtime. This is what makes us extensible — the proxy can register new AgentDefinitions on the fly.*
>
> *Now within a team, shared state flows through what we call the agent context — the persona, the child ID, the recurring characters all reach every specialist. And in the future, we'll extend this with agent-to-agent bridges to external teams."*

🎬 The "we use all four" line is the punchline.

---

## Slide 7 — Six memory types · ⏱ ~38s

> *"Memory is what makes a buddy actually feel like a buddy. We've broken it into six layers.*
>
> *Session memory — what was said in this conversation. We store it in the agent chat repository.*
>
> *Working memory — the per-turn execution context. The in-flight tool results, the persona, the recurring characters. All passed to every specialist via the agent context builder.*
>
> *Episodic memory — the kid's past creations. Stories, interactive sessions, kids-daily episodes. Three tables.*
>
> *Factual memory — buddy persona, child profile, preferences. That lives in the agent repository, the preference repository, and the users table.*
>
> *Semantic memory — embeddings of characters, themes, narrative style. ChromaDB locally, pgvector in production, accessed via our vector search MCP.*
>
> *And procedural memory — how the buddy actually generates each kind of content. That's our versioned markdown prompts, our at-tool skills, and the enabled-skills gating on each agent.*
>
> *So put it all together: the buddy remembers, understands, acts, talks, and reasons in flight."*

🎬 Slow down on procedural memory — that's the layer most teams don't have. Land the closing slowly.

---

## Slide 8 — The team (CENTERPIECE) · ⏱ ~55s

> *"This is the architecture. Branching adventures, daily podcasts, per-reply safety — each one needed its own expertise. So we extended to an agent team. All still on the Claude Agent SDK.*
>
> *[point at the proxy node at the top]*
>
> *When a child sends a message, the proxy receives it first. The proxy orchestrates everything — it routes the intent using a mix of deterministic rules and LLM disambiguation.*
>
> *[point at the specialists and tools in the middle]*
>
> *Then it hands off to the right capability. Image story, interactive story, and Kids Daily are product specialists; audio narration is a reusable TTS tool. Each one has its own prompt or typed interface, its own tools, and its own skill set.*
>
> *[point at safety_review at the bottom — pause briefly]*
>
> *But here's the part that earns the trust. Every reply passes through safety review. That subagent is the non-negotiable gate before anything ever reaches the child.*
>
> *[point at the shared context bus underneath]*
>
> *And underneath all of it is shared context. Persona, tone, style, skills, topics, goals, child ID, age, and recurring characters all flow through the same orchestration path. So Lightning the puppy in the story is the same Lightning in the podcast. The character continuity is built in at the architecture level through character memory and vector recall.*
>
> *This unlocks three things. We're responsive — the right specialist runs in milliseconds. We're dynamic — different experience per turn, without changing the chat surface. And we're A2A extensible — adding a new specialist takes one AgentDefinition."*

🎬 Centerpiece slide. Walk top to bottom slowly. Pause after "before it ever reaches the child."

---

## Slide 9 — Three-layer infrastructure · ⏱ ~32s

> *"Now let me show you the infrastructure. Three managed services, one HTTPS hop between each.*
>
> *At the top, Vercel hosts the frontend. It's a React single-page app served from a CDN — static files, fast everywhere.*
>
> *In the middle, Railway runs the FastAPI backend. That's where the Claude Agent SDK lives, along with our seven MCP servers. Railway auto-deploys whenever we push to main.*
>
> *At the bottom, Supabase is the database. Postgres plus pgvector for embeddings, plus auth, plus file storage. It's a managed service, always on.*
>
> *And on the side, we use a handful of AI APIs — Anthropic for Claude, OpenAI for TTS, ElevenLabs for premium voices, and Tavily for kid-safe web search.*
>
> *The thing I want you to take away is — each service does one job. Each HTTPS hop is one boundary. There's no magic, no monorepo coupling. We can replace any layer without touching the others."*

🎬 Trace top to bottom. Closing line — "no magic, no monorepo coupling" — slow on this.

---

## Slide 10 — Backend layered architecture · ⏱ ~35s

> *"Now inside the backend itself, we keep the same discipline. Seven layers, all talking in one direction.*
>
> *At the top, routes parse the incoming request — we have fourteen route modules.*
>
> *Below that, dependencies handle auth and quota — we use dependency injection, not inline checks.*
>
> *Then the agents layer orchestrates the AI — that's our proxy plus four specialists, all on the Claude Agent SDK.*
>
> *Below that, the MCP servers are the tool layer. Seven of them. Typed envelopes, with what we call the dot-handler calling convention.*
>
> *Then services hold the business logic — fourteen modules, including the shared agent context builder.*
>
> *Repositories wrap database access — twenty of them, one per table.*
>
> *And at the very bottom, the database adapter. SQLite in dev, Postgres plus pgvector in production.*
>
> *The rule is simple: each layer talks down, no layer talks up. That's how we replace any single layer without touching the others."*

🎬 Walk through layer by layer. Closing rule line is the architectural discipline — land it slowly.

---

## Slide 11 — The buddy (3-state strip) · ⏱ ~30s

> *"Here's the buddy. Three states, one identity.*
>
> *When the child first arrives, there's no buddy yet — just an empty state inviting them to create one.*
>
> *Then they customize. They name their buddy, pick an avatar emoji, choose a theme. This whole step takes about three minutes, and honestly, kids love this part more than the chat itself.*
>
> *Once that's done, they land on the chat screen. The buddy greets them with three starter prompts, and each prompt routes to a different specialist underneath — story, news, or adventure.*
>
> *Three React states. One persona. And the buddy persists across every session through our agent repository."*

🎬 The "kids love this part more than the chat itself" should feel like a real observation, not a brag.

---

## Slide 12 — What the buddy creates · ⏱ ~38s

> *"These are real outputs from the live app. Let me walk you through them.*
>
> *On the left — 'The Singing Shells of Coral Bay.' This is an art story. The child uploaded a drawing, and the buddy turned it into a sixty-second narrative — with their character, Ember, and the rest of the crew. The cover illustration on the left was generated too.*
>
> *In the middle — 'Ember and the Golden Dragon's Cozy Cloud.' This is an interactive story. The same Ember from the art story is now starring in a branching adventure. Down at the bottom, you can see three choices the kid picks from — each one changes the ending.*
>
> *And on the right — 'Amazing Animals and How We Keep Them Safe.' This is a kids daily episode. Cover art, transcript on the side, audio playback. And there's Ember again, this time as the guest anchor.*
>
> *Three different surfaces. Same character across all of them. This is character continuity made real — not just claimed."*

🎬 Say "Ember" by name on each pane.

---

## Slide 13 — Community & sharing · ⏱ ~32s · **DEFAULT-CUT for 5-min**

> *"OK, so kids share what they create. The question is — how do we do this safely?*
>
> *Here's where most kid-AI products fail COPPA. They join posts back to the users table to get the byline. And somewhere along the way, a child's real name leaks out.*
>
> *We don't have that risk, because our schema doesn't allow it.*
>
> *The hub posts table has agent_name, agent_avatar, agent_title — immutable persona snapshot columns written once at post time. There's no read path that JOINs the users table. The unsafe query literally can't even be expressed.*
>
> *Safety isn't a code review checklist for us. It's a schema invariant, and we have a contract test — test_hub_coppa_invariant — that fails if anyone ever tries to write that join."*

🎬 The "literally can't be expressed" line is the COPPA moat. Land slowly.

---

## Slide 14 — Open by design · ⏱ ~32s · **DEFAULT-CUT for 5-min**

> *"This architecture is open by design. Let me show you.*
>
> *If you want to add a brand new specialist to the buddy team, you write one AgentDefinition. That's it.*
>
> *[gesture at the code on screen]*
>
> *You give it a model — Haiku for speed. You give it a system prompt — that's a markdown file in our prompts folder. You give it a list of tools it can call. And you give it the skills it's allowed to use.*
>
> *Once you register it, the routing picks it up automatically. The proxy's intent classifier reads the specialist's description and learns what trigger phrases route to it.*
>
> *The safety gate runs on every reply, no matter which specialist generated it. And the shared context — persona, tone, child ID, age, and recurring characters — flows in to the new specialist just like the others.*
>
> *And in the future, we'll add an A2A bridge. That lets external agent teams join the buddy's world, using exactly the same contract."*

🎬 Let the audience read the code. "One AgentDefinition" is the moat.

---

## Slide 15 — Roadmap · ⏱ ~30s

> *"This is our roadmap. Two phases shipped, two ahead.*
>
> *Phase one was the MVP. Single agent. Image-to-story, plus safety, plus text-to-speech. Ninety-two out of ninety-two stories shipped — all done.*
>
> *Phase two was the agent team. Multi-agent. Memory system. Kids Daily. Community. Per-reply safety. One hundred eighty out of one hundred eighty stories shipped — also done.*
>
> *Phase three is in design right now — video and dynamic picture books, a parent dashboard, and gamification features.*
>
> *Phase four is the vision — autonomous. Multi-step planning, scheduled buddy initiatives, and an A2A bridge so external agent teams can join.*
>
> *And here's the thing I want you to remember about us — we don't just pitch features. We ship them."*

🎬 Tap each phase card. Closing line is the receipt.

---

## Slide 16 — Where we are · ⏱ ~28s

> *"So where are we today?*
>
> *Two hundred and seventy-two stories shipped across three milestones. Phase one — the MVP single-agent — done. Phase two — the multi-agent team plus community — done. Phase three — video and the parent dashboard — in design.*
>
> *Engineering rigor matters to us as much as features do.*
>
> *We have over seven hundred contract tests. Per-reply programmatic safety on every output. We even caught and fixed a silent safety bypass in our own code in twenty-four hours. And we landed a merge train of seven pull requests just last week.*
>
> *Like I said — we don't pitch features. We ship them."*

🎬 Speak numbers as words. The closing is intentionally a repeat — lands the receipt.

---

## Slide 17 — Failures we owned · ⏱ ~35s · **DEFAULT-CUT for 5-min**

> *"This is the slide most pitches don't have. We want to show you the bugs we caught — because how a team catches its own bugs tells you more than any feature list.*
>
> *First one. We tried running the SDK as a subprocess for image-to-story. Railway kept killing it — out of memory under load. So we ported all three generation agents to a direct API. Got half the memory back overnight.*
>
> *Second one. We were calling check-content-safety the wrong way. Turns out the wrapper isn't callable directly. The TypeError got swallowed silently. Every story was shipping with a default safety score of point-nine — which looked fine, but wasn't real. We caught it ourselves, in our own code, and fixed it in twenty-four hours.*
>
> *Third one. We tried using a single agent plus a safety prompt. The model occasionally produced replies that weren't safe enough. So we built the per-reply programmatic safety with suggest-and-retry that you saw earlier.*
>
> *Most pitches hide their bugs. We name ours."*

🎬 The 24-hour bypass story is the receipt. Slow on it.

---

## Slide 18 — Why this matters (CLOSING) · ⏱ ~30s

> *"So here's why this matters.*
>
> *We're agentic from day one. This isn't a wrapper, it isn't just a prompt. It's a real SDK, with real tools, and real orchestration underneath.*
>
> *We've shipped two hundred seventy-two stories across three milestones — that's our execution proof.*
>
> *We have programmatic safety on every reply — non-negotiable, code-enforced. No vibes.*
>
> *We've built a community that protects child PII at the schema level — COPPA by construction.*
>
> *And we've built a buddy that genuinely grows with the child — character continuity across the image story, the interactive adventure, the podcast, and the share.*
>
> *[pause for 2 seconds]*
>
> *This is AI that grows up with kids — safely.*
>
> *[pause, hold eye contact for 2 more seconds]*
>
> *I'd love to take any questions you have."*

🎬 Read "we've..." lines briskly. Hard pause before "AI that grows up with kids — safely." Don't smile until you've finished asking for questions.

---

## Slide 19 — Appendix (Q&A backup, HIDDEN)

Only reveal if a judge asks a technical question. Jump to the matching row.

**If asked "what's the difference between agent and subagent?":**
> *"An agent in our system is an AgentDefinition — it has a model, a system prompt, a set of tools, and a set of skills. A subagent is one of those registered underneath our proxy. The SDK's Agent tool is what lets the proxy delegate to a subagent based on the child's intent."*

**If asked "why didn't you just use a bigger prompt?":**
> *"Two reasons. First, quality degrades as you stuff more specialties into one prompt — the model loses focus. And second, we'd lose the per-reply safety subagent as a separate gate, which is non-negotiable for a kids product."*

**If asked "how is your COPPA pattern different?":**
> *"Most teams enforce their kid-PII rules in code review. We enforce them in the schema. The hub_posts table has agent_name, agent_avatar, and agent_title as immutable snapshot columns — written once at post time. No read path in our codebase JOINs the users table. The unsafe query literally can't be expressed in our schema."*

---

## Total run time

| Cut | Slides | Time |
|---|---|---|
| **6-min** (recommended) | 1–16, 18 (drop 17) | ~6:30 |
| **7-min** (full) | All 18 main | ~7:00 |
| **5-min** (tight) | Drop 9, 13, 14, 17 | ~5:00 |
| **3-min** (forced) | 1, 2, 4, 5, 8, 11, 15, 16, 18 | ~3:30 |

## Delivery tips

- **Numbers as words.** "Two hundred seventy-two" sounds bigger than "272."
- **Pauses are content.** When the script says `[pause]`, take 2-3 seconds. Silence is harder for you than for the audience.
- **First sentences are anchors.** Memorize the first sentence of each slide. Paraphrase the rest.
- **Closing bookend.** Slide 18's closing line mirrors slide 1's thesis — that's the rhythm.

---

*Source of truth: `docs/pitch/keynote-deck.md`. Re-extract with `grep -A 50 "🎤 SCRIPT" keynote-deck.md` after edits.*
