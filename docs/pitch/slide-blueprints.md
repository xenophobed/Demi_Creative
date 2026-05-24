# Slide blueprints — contest pitch deck

Per-slide component spec for building the deck in Apple Keynote.
Keep this file open in your IDE alongside `keynote-deck.md` while assembling slides.

> **Narrative arc:**
> **Product (1–8)** — Three-moment hook (1–2) → four problems (3) → four agent abilities (4) → six agentic features (5) → four architecture patterns (6) → six memory types (7) → agent-team structure (8)
> **Technical (9–10)** — Three-layer infrastructure (9) → backend layered architecture (10)
> **Demo (11–13)** — The buddy 3-state strip (11) → what the system creates (12) → community & sharing (13)
> **Surprise (14–15)** — Open by design / extensibility (14) → roadmap (15)
> **Close (16–18)** — Where we are (16) → failures we owned (17) → why this matters (18)
> Plus appendix backup slide (19) hidden by default for Q&A.

---

## Design tokens (apply globally first)

| Token | Value | Used for |
|---|---|---|
| Brand pink | `#DB2777` | H1 headings · `<strong>` accent · primary button |
| Brand violet | `#7C3AED` | H2 headings · `<em>` accent · secondary highlight |
| Pink on dark | `#F472B6` | H1/H2 on dark slides only |
| Violet on dark | `#C4B5FD` | `<em>` on dark slides only |
| Slate body | `#1E293B` | Body text on light slides |
| Slate muted | `#64748B` | Captions · `<small>` · meta |
| Card border | `#E2E8F0` | Table dividers · subtle separators |
| Background light | `#FFFFFF` | Default slide |
| Background gradient | `linear-gradient(135deg, #FDF2F8 0%, #F5F3FF 100%)` | Title cards (slides 1, 2, 10) |
| Background dark | `#0F172A` | Multi-agent slide only (7) |
| Heading font | SF Pro Display (or Inter) — weight 800 (H1), 700 (H2) | All slides |
| Body font | SF Pro Text (or Inter) — weight 400 | All body text |

**Aspect ratio:** 16:9 widescreen
**Slide count:** 18 main + 1 appendix.
- **6-min cut** (recommended) — drop slide 17 → 17 visible at ~6:30
- **7-min cut** — keep all → 18 visible at ~7:00
- **5-min cut** — drop 9, 13, 14, 17 → 14 visible at ~5:00 (loses backend layers + community + extensibility — becomes product+roadmap pitch)
- **3-min cut** — drop 3, 6, 7, 9, 10, 13, 14, 17 → 10 visible at ~3:30 (only emotional hook + abilities + team + buddy + roadmap + close)

**Total target time:** ~6:30 with handoff buffer. **Recommended slot: 6 min.** The deck now spans product + technical + demo + surprise — a 5-min cut sacrifices either tech or demo depth.

---

## Slide 1 — Title

**Layout:** Title card · centered text · gradient background

**Background:** Pink→lavender gradient

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H1 brand | `Kids Creative Workshop` | Pink #DB2777 · 56px · weight 800 | Top-center |
| H2 thesis | `An agentic app for kids — built on Claude Agent SDK.` | Violet #7C3AED · 36px · italic accent on "agentic" | Below H1 · 30px gap |
| Caption | `5-minute pitch · Single agent → agent team · 2026` | Slate muted #64748B · 18px | Bottom-center · 40px from edge |

**Visuals:** Optional small brand mark or logo in top-right corner (~32px square)

**Timing:** ~8 seconds — don't dwell, this is the warm-up

**Speaker beat:** *"I want to start with a moment."* — then pause, click forward.

**Why this slide exists:** Names the thesis up front. The word **"agentic"** is doing real work — it signals to technical judges that this is an Agent SDK story, not a wrapper, before they tune out.

---

## Slide 2 — The moment

**Layout:** Title card · three short emotional lines · gradient background

**Background:** Same gradient as slide 1

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| Line 1 | `A 5-year-old hands you a crayon drawing.` | Pink #DB2777 · 56px · weight 800 | Top-third |
| Line 2 | `What if it became a story?` | Violet #7C3AED · 56px · weight 800 · italic | Center · 50px gap above |
| Line 3 | `In her character. Her voice. Her world.` | Violet #7C3AED · 56px · weight 800 · italic | Below line 2 · 50px gap |

**Visuals:** Optional: blurred warm-toned crayon-drawing photo as 20%-opacity background behind text. Skip if it competes with the text.

**Timing:** ~25 seconds — slow tempo, three deliberate pauses

**Speaker beat:** Read each line. Pause **3 seconds** between lines. The pauses ARE the slide.

**Why this slide exists:** Emotional anchor. Every technical claim that follows is in service of this single moment.

---

## Slide 3 — Today's AI fails kids *(OPTIONAL — drop for shorter cuts)*

**Layout:** Two-column comparison table · headline above · callout line below

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Today's AI fails kids in two opposite ways` | Violet #7C3AED · 36px · weight 700 | Top-left |
| Comparison table | 4 rows × 3 cols (label / ChatGPT / Image gen) | Violet headers · slate body · 19px · row borders #E2E8F0 | Center · full-width minus 80px padding |
| Closing line | `Existing AI extracts. We collaborate.` | Pink #DB2777 · 56px · weight 800 | Bottom · centered |

**Visuals:** None. Text + table only.

**Timing:** ~20 seconds — read the table top-to-bottom, land hard on the closer

**Why this slide exists:** Establishes the problem space sharply. Without it, judges might assume you're "ChatGPT for kids" — this slide closes that door.

---

## Slide 4 — Meet My Agent

**Layout:** Product intro · H1 + 4 bullets + tagline · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H1 product name | `Meet My Agent` | Pink #DB2777 · 56px · weight 800 (bold "My Agent") | Top-left |
| Tagline | `A personal AI buddy the child names, customizes, and grows with.` | Slate body #1E293B · 22px · regular | Below H1 · 30px gap |
| 4 bullets | Recognizes / Routes / Protects / Shares — each lead-bolded verb | Slate body · 22px · 1.5 line-height | Center-left · 50px gap below tagline |
| Footer line | `One chat surface. Four specialists. One non-negotiable safety gate.` | Slate muted #64748B · 18px | Bottom-left |

**Visuals:** Optional small buddy emoji (🤖 or 🦊) inline next to "My Agent" in the H1.

**Timing:** ~30 seconds — narrate over the bullets, don't read them

**Why this slide exists:** Names the product. The single-agent foundation slide (next) doesn't make sense without first knowing what the product IS.

---

## Slide 5 — Foundation: single agent with Claude Agent SDK *(NEW)*

**Layout:** 2×2 grid of building blocks · H2 above · footer below · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Foundation — one agent, with everything it needs` | Violet #7C3AED · 36px · weight 700 · italic accent on "one agent, with everything it needs" | Top-left |
| Intro sentence | `Built on Claude Agent SDK. Four primitives compose the single agent:` | Slate body · 22px | Below H2 |
| **Quadrant 1 — Prompt design** | 🧭 emoji + bold name + 1-line explanation: "Versioned markdown prompts in `backend/src/prompts/` — story-generation, age-adapter, interactive-story" | Cell of 2×2 grid · violet bold header · slate body 18px | Top-left quadrant |
| **Quadrant 2 — Tools** | 🔧 emoji + bold name + "Custom MCP servers we built — vision_analysis · vector_search · safety_check · tts_generator" | Cell · violet bold header · slate body 18px | Top-right quadrant |
| **Quadrant 3 — MCP** | 🔌 emoji + bold name + "Model Context Protocol — tool calls become first-class agent affordances, not parsed-string hacks" | Cell · violet bold header · slate body 18px | Bottom-left quadrant |
| **Quadrant 4 — Skills** | 🛠️ emoji + bold name + "Composable behaviors — `@tool` decorators, skill gating per-agent via `enabled_skills`" | Cell · violet bold header · slate body 18px | Bottom-right quadrant |
| Footer line | `One agent. No orchestrator yet. Just an LLM with the right scaffolding.` | Slate muted #64748B · 18px · italic | Bottom-center |

**Visuals:** The 2×2 grid IS the visual. After Keynote import, you may want to:
- Replace the inline table with proper 2×2 card layout (rounded rectangles with subtle drop shadow)
- Each card same dimensions (~440 × 200px), 30px gap between cards
- Emoji at 36px in top-left of each card, header at 22px bold violet next to it, body text at 18px slate underneath

**Timing:** ~35 seconds

**Speaker beat:** *"We started simple — one agent, built right. Four primitives — prompt design, tools, MCP, and skills — compose the whole thing."* Quickly call out one concrete thing per quadrant:
- *Prompt design*: "Prompts live in markdown files in git, versioned and reviewed like code."
- *Tools*: "We wrote our own MCP servers — vision for the drawings, vector search for character memory, safety as a non-negotiable gate."
- *MCP*: "Tool calls go through MCP — first-class, not string-parsed hacks."
- *Skills*: "Skills are gated per-agent — that's how a 3-year-old's buddy and a 10-year-old's buddy have different capabilities from the same codebase."

**Why this slide exists:** Sets up the EVOLUTION story. Judges who don't understand "we started with one agent and grew" can't appreciate slide 7 (the agent team).

---

## Slide 6 — Three properties of the single agent *(NEW)*

**Layout:** 3-column property cards · H2 above · footer below · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Three properties the single agent already delivers` | Violet #7C3AED · 36px · weight 700 · italic accent on "already" | Top-left |
| **Column 1 — Interactive** | 🌊 (big emoji 64px) + bold "Interactive" + main line "Streaming via SSE — the kid watches the story write itself, token by token" + italic quote "Reads like a story being told." | Card layout · violet header · slate body 18px · italic quote 16px violet | Left third |
| **Column 2 — Proactive** | 💡 (big emoji 64px) + bold "Proactive" + main line "Recommendations — buddy suggests next moves; Kids Daily picks topics; character memory recalls" + italic quote "Lightning the puppy is back!" | Card layout · violet header · slate body 18px · italic quote 16px violet | Middle third |
| **Column 3 — Persistent** | 🧠 (big emoji 64px) + bold "Persistent" + main line "Memory — character_repo, agent_repo, vector search · survives across sessions" + italic quote "Same buddy persona for life." | Card layout · violet header · slate body 18px · italic quote 16px violet | Right third |
| Footer line | `One agent. Three properties kids feel immediately. Already a real product.` | Slate muted #64748B · 18px · italic | Bottom-center |

**Visuals:** Big emojis (64px) at the top of each card. Cards equal width, 30px gaps. Subtle border + drop shadow if Keynote default is too flat.

**Timing:** ~35 seconds

**Speaker beat:** *"And that single agent already delivered three properties kids felt immediately — interactive, proactive, and persistent."* For each: read the bold word, point at the italic quote underneath. Land on the footer line: *"Already a real product."* — that's the **pivot** before slide 7.

**Why this slide exists:** The "what good agentic feels like" slide. Concrete kid moments under each property. The footer line "already a real product" is the **pivot** that sets up "but one agent wasn't enough" on the next slide.

---

## Slide 7 — Extending to a team: multi-agent *(NEW · CENTERPIECE)*

**Layout:** Dark slide · H2 + intro + diagram + unlocks · DARK BACKGROUND

**Background:** Dark slate `#0F172A` — sets the centerpiece apart visually

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Extending to a team — responsive + dynamic` | Pink-on-dark #F472B6 · 36px · weight 700 · italic accent on "responsive + dynamic" | Top-left |
| Intro line | `One agent hit a ceiling. Branching stories, news podcasts, per-reply safety — each needed its own expertise.` | Light slate #F8FAFC · 22px | Below H2 |
| Bridge line | `We extended to an agent team — still on Claude Agent SDK.` | Light slate #F8FAFC · 22px · italic | Below intro |
| **Diagram** | Boxes-and-arrows: My Agent (proxy, labeled "orchestrator / intent routing") fans out to 3 product specialists (image_story, interactive_story, kids_daily) plus an audio_narration TTS tool. All feed into safety_review labeled "runs on EVERY reply". Below them: horizontal "shared context bus" labeled "persona · child_id · age · characters · preferences" | **REBUILD WITH NATIVE KEYNOTE SHAPES** after import. Rounded rectangles, white outline, violet-on-dark connector lines, the shared context bus as a horizontal pill underneath. | Center · full-width · ~60% slide height |
| Unlocks line | `🎯 responsive · 🎨 dynamic · ➕ A2A extensible` | Pink-on-dark #F472B6 · 28px · weight 700 · separators in slate muted | Below diagram · centered |

**Visuals:** The diagram IS the slide. The ASCII version in `keynote-deck.md` is a placeholder. After import, **you MUST rebuild this** in Keynote with native shapes:
1. **Proxy node** in center top — rounded rectangle, slightly larger, label "My Agent (proxy)" and a small "intent routing" caption
2. **3 product specialists + audio tool** fanning out below — same-size rounded rectangles, labeled with the agent/tool names
3. **safety_review** node below the specialists, with arrows from each specialist into it
4. **Shared context bus** — a thin horizontal pill underneath everything, labeled "shared context: persona · tone · child_id · age · characters · preferences"
5. Use **violet-on-dark connector lines** (#C4B5FD on #0F172A) for arrows

**Timing:** ~50 seconds — the longest slide; this is the centerpiece

**Speaker beat:** Walk the diagram top-to-bottom. About 10 seconds per element:
1. *"We extended — same SDK, new shape."*
2. *"The proxy ORCHESTRATES — routes the child's intent to the right specialist."*
3. *"Four specialists, each with their own prompt, tools, and skills."*
4. *"Every reply passes through safety_review — that subagent is the non-negotiable gate."* **(pause here)**
5. *"And underneath everything — SHARED CONTEXT. Persona, child_id, recurring characters — flows to every agent. So Lightning the puppy is the same dog in the story AS in the podcast."*
6. *"Two more properties unlocked: responsive (right specialist in milliseconds) and dynamic (different experience per turn). And A2A extensible — new specialists plug in by registering one AgentDefinition."*

**Why this slide exists:** **THE moat.** Multi-agent orchestration with shared state is hard. Doing it for kids with per-reply safety is harder. If a judge remembers only one technical slide, this is it.

---

## Slide 8 — Decisions, not defaults *(NEW · design rationale)*

**Layout:** 4-column × 4-row table · H2 above · vocabulary footer · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Decisions, not defaults — every primitive earned its place` | Violet #7C3AED · 36px · weight 700 · italic accent on "every primitive earned its place" | Top-left |
| Table headers | `Decision` · `Alternative we rejected` · `What we chose` · `Why` | Violet #7C3AED · 18px · weight 700 | Row 1 |
| Row — Prompts | `Prompts` / `Python f-strings inline in code` / `Markdown files in backend/src/prompts/` / `Versioned · code-reviewable · age-stratified per file` | Slate body · 17px · bold "Prompts" · code styling for file paths | Row 2 |
| Row — Tools | `Tools` / `Direct API calls in agent loops` / `Custom MCP servers · typed JSON envelopes · .handler calling convention` / `Composable · testable · independently versionable` | Slate body · 17px · bold "Tools" · code styling for .handler | Row 3 |
| Row — Skills | `Skills` / `Hardcoded behaviors per agent class` / `enabled_skills field on AgentDefinition · _enabled(agent, skill) runs server-side` / `Per-age gating · A2A plug-in · single registration` | Slate body · 17px · bold "Skills" · code styling | Row 4 |
| Row — Multi-agent | `Multi-agent` / `Bigger prompt + conditional branching` / `Proxy + 3 product subagents + audio tool + shared context bus` / `Specialty isolation · safety_review on EVERY reply · responsive routing` | Slate body · 17px · bold "Multi-agent" · "EVERY" emphasized | Row 5 |
| Vocabulary footer | `Vocabulary — agent · subagent · team · orchestrator — each role is precise. See appendix.` | Slate body · 18px · italic on the four vocabulary words | Below table · 24px gap |

**Visuals:** None. The 4×4 table IS the slide.

**Timing:** ~30 seconds

**Speaker beat:** Walk it row-by-row, ~7 seconds per row:
1. *"Prompts could have been Python f-strings. We chose markdown in git — versioned and code-reviewable."*
2. *"Tools could have been direct API calls. We chose MCP servers with typed envelopes — composable and testable."*
3. *"Skills could have been hardcoded. We chose enabled_skills as a field on AgentDefinition — per-age gating, A2A extensible."*
4. *"Multi-agent could have been a bigger prompt with branching. We chose a proxy plus 4 subagents — specialty isolated, safety_review runs on EVERY reply."*

Close: *"We didn't adopt defaults. Each row is a trade-off we made deliberately."* Point at the vocabulary footer: *"And we use precise terms — agent, subagent, team, orchestrator. Each role is distinct."*

**Why this slide exists:** Distinguishes "we wrote prompts and called the API" from "we made architectural decisions and designed primitives that compose." Judges who care about technical depth want to see the **decision framework**, not just the implementation list. Without this slide, slide 5 (Foundation) reads like "we used the SDK"; with this slide, it reads "we designed our primitives deliberately."

**Default-cut for 5-min slot.** Keep for 6-min slot, technical-heavy judging panels, or when fielding "how is your stack different from X?" follow-ups.

---

## Slide 9 — Innovation moats *(was slide 8)*

**Layout:** 3-column × 2-row matrix · H2 above · footer punchline · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Where we innovate — three layers, six specific bets` | Violet #7C3AED · 36px · weight 700 · italic accent on "three layers, six specific bets" | Top-left |
| **Column header 1 — Agentic stack** | 🤖 emoji + bold "Agentic stack" | Violet #7C3AED · 24px · weight 700 · emoji 32px | Top of left column |
| **Column header 2 — Safety architecture** | 🛡️ emoji + bold "Safety architecture" | Violet #7C3AED · 24px · weight 700 · emoji 32px | Top of middle column |
| **Column header 3 — Kid experience** | 🌟 emoji + bold "Kid experience" | Violet #7C3AED · 24px · weight 700 · emoji 32px | Top of right column |
| **Row 1 / col 1** | `Multi-agent + shared state on Claude Agent SDK — proxy + 3 product specialists, a TTS tool, and a shared context bus` | Slate body · 17px · bold "Multi-agent + shared state" | Cell |
| **Row 1 / col 2** | `Per-reply programmatic safety — age-aware thresholds (0.90 for 3-5, 0.85 for 6-12), suggest-then-retry` | Slate body · 17px · bold "Per-reply programmatic safety" | Cell |
| **Row 1 / col 3** | `Character continuity across surfaces — Lightning the puppy in image, story, podcast, and community` | Slate body · 17px · bold "Character continuity across surfaces" | Cell |
| **Row 2 / col 1** | `A2A extensible — new specialists plug in via one AgentDefinition registration` | Slate body · 17px · bold "A2A extensible" | Cell |
| **Row 2 / col 2** | `COPPA at the schema level — persona-snapshot columns; the unsafe JOIN can't be expressed` | Slate body · 17px · bold "COPPA at the schema level" · italic accent on "can't be expressed" | Cell |
| **Row 2 / col 3** | `One buddy, N specialists, one identity — child sees one persona; system orchestrates the rest` | Slate body · 17px · bold "One buddy, N specialists, one identity" | Cell |
| Punchline | `Most kid-AI products ship one of these. We ship all six.` | Slate muted #64748B · 20px · italic · **bold "one"** and **bold "all six"** | Bottom-center · 40px from edge |

**Visuals:** The 3×2 matrix IS the slide. After Keynote import:
- Replace the raw table with a proper 3×2 card grid (each cell ~390 × 180px, 20px gaps)
- Column headers get their own row above the cards, in a slightly lighter violet (#A78BFA) tint
- Subtle 1px border + drop shadow on each card

**Timing:** ~30 seconds

**Speaker beat:** Walk it column-by-column, ~7 seconds per cell:
1. *"Agentic stack: multi-agent with shared state on the SDK — A2A extensible, so new specialists plug in by registering a single AgentDefinition."*
2. *"Safety architecture: per-reply programmatic safety with age-aware thresholds — and COPPA enforced AT THE SCHEMA LEVEL. The unsafe JOIN can't even be expressed."*
3. *"Kid experience: character continuity across surfaces — same Lightning the puppy from her drawing shows up in her interactive story, her podcast, her community feed. One buddy, many specialists, one identity."*

Land hard on: *"Most ship one of these. We ship all six."* Pause. Then move.

**Why this slide exists:** This is the "we are not a wrapper" slide. The architecture diagram on slide 7 shows WHAT we built; this slide names WHY it's defensible. Judges in startup competitions score on novelty + defensibility — this is the slide that answers both at once.

---

## Slide 10 — What kids do + how they share *(was slide 9)*

**Layout:** 3-column table + screenshots + community footer · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `What kids actually do — and how they share` | Violet #7C3AED · 36px · weight 700 | Top-left |
| 3-column table | 📖 Image-to-Story · 🌟 Interactive Story · 🎙️ Kids Daily — each col: emoji + bold name + 1-line | Violet headers · 19px body · equal columns | Below H2 · 30px gap |
| 3 product screenshots | Drag from repo root: `my-agent.png` · pick a story screenshot · `content-hub-logged-in.png` (or any showing actual content) | Equal-sized · ~260px tall · 20px gaps · drop shadows · rounded corners | Below table · 40px gap |
| Community footer | `And they share safely in Content Hub — bylined under their buddy's persona, not their name. COPPA-by-construction at the schema level: no JOIN to the user table from any community read path.` | Slate body · 18px · bold "COPPA-by-construction at the schema level" | Bottom · full-width |

**Visuals:** **3 screenshots are required.** Without them this is the weakest slide. Repo has `content-hub.png`, `my-agent.png`, `group-page-magazine.png`. Use what's most representative of each surface.

**Timing:** ~35 seconds

**Speaker beat:** Point at each screenshot in order. Use **Lightning the puppy as the through-line**:
*"Same Lightning the puppy from her drawing appears in her interactive story, AND as guest anchor on her Kids Daily podcast. And she shares all of it in Content Hub — under her buddy's name, never her own. COPPA isn't enforced in code reviews. The schema can't even express the unsafe JOIN."*

**Why this slide exists:** Proves the shared-state architecture WORKS — same character, three surfaces, plus community. Without screenshots this slide is words; with screenshots it's product proof.

---

## Slide 11 — Where we are (traction) *(was slide 10)*

**Layout:** Phase-progress table · engineering rigor line · meta caption · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Where we are` | Violet #7C3AED · 36px · weight 700 | Top-left |
| Progress table | 3 rows: Phase 1 MVP ✅ 92/92 (single agent) · Phase 2 ✅ 180/180 (multi-agent team) · Phase 3 🔜 In design | Violet headers · 20px body · ✅/🔜 emoji · bold counts | Center · full-width minus 80px |
| Engineering rigor line | `Engineering rigor: 700+ contract tests · per-reply programmatic safety (age-aware) · silent safety-bypass caught + fixed in 1 day · merge-train of 7 PRs landed last week` | Slate body · 18px · bold "Engineering rigor:" | Below table · 30px gap |
| Real-numbers line | `Add real numbers in Keynote: pilot users · sessions/week · feedback quotes.` | Slate muted #64748B · 16px · italic | Bottom · centered |

**Visuals:** Optional: a small line/bar chart if you have usage data.

**Timing:** ~25 seconds

**Speaker beat:** *"292 tracked work items across shipped and planned milestones. We don't pitch features — we ship them. And the engineering rigor line — programmatic per-reply safety, caught and fixed a silent safety-bypass in one day, landed a 7-PR merge train last week — that's how we treat production AI for kids."*

**Why this slide exists:** Execution velocity + engineering rigor are the contest-judged proxies for "this team can ship." Both deserve their own line.

**⚠️ MUST do before presenting:** Replace the italic "Add real numbers" line with actual usage data OR with "Closed-beta launching <date> with N families".

---

## Slide 12 — Failures we owned *(anti-pitch slide, was slide 11)*

**Layout:** 3-column table · H2 above · punchline below · light background

**Background:** Default white

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H2 heading | `Failures we owned — receipts, not theater` | Violet #7C3AED · 36px · weight 700 · italic accent on "receipts, not theater" | Top-left |
| Table headers | `What we tried` · `How it broke` · `What we did about it` | Violet #7C3AED · 19px · weight 700 | Row 1 |
| Row 1 — subprocess | `SDK subprocess for image-to-story` / `Railway exit -9 · OOM kills` / `Ported all 3 agents to direct API · ~50% memory drop` | Slate body · 18px · bold "SDK subprocess" | Row 2 |
| Row 2 — wrapper | `await check_content_safety({...})` / `SdkMcpTool wrapper not callable · TypeError swallowed → default 0.9` / `Caught + fixed in 24h · .handler convention · 3 agents, 1 PR` | Slate body · 18px · code styling on the broken call | Row 3 |
| Row 3 — single agent | `Single agent + safety prompt` / `Model occasionally produced unsafe replies` / `Per-reply programmatic safety subagent · age-aware · fail-closed retry` | Slate body · 18px · bold "Single agent + safety prompt" | Row 4 |
| Punchline | `Most pitches hide bugs. We name ours — that's how you know we actually run safety like infrastructure.` | Slate muted #64748B · 18px · italic accent on "actually" | Bottom · centered |

**Visuals:** None. The table IS the slide.

**Timing:** ~30 seconds

**Speaker beat:** Land each row in ~9 seconds:
1. *"SDK subprocess for image-to-story — Railway killed it. We ported to direct API, got half the memory back."*
2. *"Called check_content_safety directly — the wrapper isn't callable, TypeError swallowed, every story shipped with a default 0.9 score. We caught it ourselves and fixed it in a day."*
3. *"Single agent + safety prompt was not enough — built per-reply programmatic safety with retry."*

Land hard on punchline: *"Most pitches hide bugs. We name ours."*

**Why this slide exists:** Counter-intuitive. Most pitches show only wins. This slide builds trust by showing the team is critical of its own AI. Judges remember it. **Optional** — drop first if your slot is tight, but if you keep it, the trust-building beat is uniquely strong.

---

## Slide 13 — Why this matters *(CLOSING BOOKEND, was slide 12)*

**Layout:** Title card · 5 achievements + closing bookend line · gradient background

**Background:** Same pink→lavender gradient as slide 1 (visual bookend)

**Components:**

| Component | Content | Style | Position |
|---|---|---|---|
| H1 heading | `Why this matters` | Pink #DB2777 · 56px · weight 800 | Top-left |
| 5 achievements | Agentic from day one · 292 tracked work items · Programmatic safety on every reply · COPPA at schema level · Buddy that grows with the child | Slate body · 22px · 1.5 line-height · **bold lead phrase** + supporting clause | Center-left · 40px gap below H1 |
| Closing bookend | `AI that grows up *with* kids — safely.` | Pink #DB2777 · 56px · weight 800 · italic accent on "with" | Bottom-center · 50px from edge |

**Visuals:** None. The gradient + typography is the visual.

**Timing:** ~25 seconds

**Speaker beat:** Read achievements briskly. **Pause.** Then deliver the closing line slowly, holding eye contact. Don't fill the silence — let it land. *"Happy to take questions."*

**Why this slide exists:** Bookends the opening. Slide 1 said *"An agentic app for kids."* Slide 10 says *"AI that grows up WITH kids — safely."* Same agentic-but-kid-centric axis, broader scope. The bookend signals you finished the story.

---

## Master timing — 5-min cut (12 visible slides, default-cut 9 + 13)

| # | Slide | Target |
|---|---|---|
| 1 | Title | 8s |
| 2 | Three moments | 28s |
| 3 | Four problems | 28s |
| 4 | **Our agent's abilities** (problem → ability) | 30s |
| 5 | **Six agentic features** (capability × stack) | 35s |
| 6 | **Four architecture patterns** | 28s |
| 7 | **Six memory types** | 30s |
| 8 | **The team** (1 proxy + 3 specialists + TTS tool + safety) ⭐ centerpiece | 40s |
| ~~9~~ | ~~Why this shape (default-cut for 5-min)~~ | — |
| 10 | **What's good about it** (moats) | 28s |
| 11 | Product proof + demo beat | 32s |
| 12 | Where we are | 25s |
| ~~13~~ | ~~Failures we owned (default-cut for 5-min)~~ | — |
| 14 | Why this matters | 25s |
| | **Total** | **~5:37** |

Tight — over by 37s on a strict 5-min slot. Trim speakers' tempo by ~3s/slide to hit 5:00, OR push to a 6-min slot (preferred).

## Master timing — 6-min cut (13 visible slides, add slide 9 back)

13 slides, ~6:05 total. Keeps the rationale slide. Strongly recommended cut for technical judging.

## Master timing — 7-min cut (all 14 main slides)

14 slides, ~6:35 total. Adds "Failures we owned" too. Use for a 7-min slot or expanded Q&A buffer.

## Master timing — 4-min cut (drop slides 3 + 7 + 9 + 13)

10 visible slides, ~4:33 total. Drops "Four problems" (forces slide 4 to carry framing), "Six memory types", "Why this shape", and "Failures we owned". Faster but loses the memory-system depth.

## Master timing — 3-min cut (drop slides 3 + 6 + 7 + 9 + 13)

9 visible slides, ~3:55 total. Compresses slide 8 (team) to 30s. Loses both patterns and memory framing — only use if forced.

---

## Build order in Keynote

1. **Import the .pptx** (`open docs/pitch/keynote-deck.pptx`)
2. **Set master typography** to SF Pro Display / SF Pro Text (or Inter) for all slides
3. **Slide 5**: rebuild the 2×2 grid as proper cards with drop shadows (the raw table is the placeholder)
4. **Slide 6**: rebuild the 3-column cards with big emojis at top, italic quotes in violet
5. **Slide 7**: **delete the ASCII diagram and rebuild with native Keynote shapes** — biggest single polish win
6. **Slide 8**: drag 3 screenshots from repo root (`content-hub.png`, `my-agent.png`, `group-page-magazine.png` — pick 3 most representative)
7. **Slide 9**: replace the italic placeholder line with real usage numbers OR a credible "Closed-beta launching <date>" line
8. **Rehearse out loud with a timer.** Cut anything that doesn't fit. Don't skip this step.
