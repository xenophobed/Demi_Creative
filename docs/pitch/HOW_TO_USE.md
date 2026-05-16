# Pitch deck — compile & import to Keynote

> **Context:** 5-minute pitch deck for an AI startup pitch **competition** (contest judging, not fundraising). Lead with the multi-agent architecture as the moat. Close with a "why this matters" bookend, not a money ask.

## What's in here

- `keynote-deck.md` — the deck source, written in [Marp](https://marp.app) (markdown that compiles to PPTX/PDF/HTML)
- `slide-blueprints.md` — **per-slide build sheet** (layout · components · style · timing · speaker beat · why-this-slide-exists). Open this alongside the deck while building in Keynote.

## One-time setup

You don't need to install anything globally — `npx` will fetch Marp on first use.

```bash
# Optional: install once for faster compiles
npm install -g @marp-team/marp-cli
```

## Compile to PowerPoint (for Keynote)

From the repo root:

```bash
npx @marp-team/marp-cli docs/pitch/keynote-deck.md --pptx --output docs/pitch/keynote-deck.pptx --allow-local-files
```

That writes `docs/pitch/keynote-deck.pptx`.

## Import into Keynote

1. Double-click `docs/pitch/keynote-deck.pptx` — macOS opens it in Keynote automatically.
2. Keynote will say *"This presentation was created in PowerPoint. To edit it, save a copy as a Keynote document."* — click **Save as Keynote**.
3. Polish the visuals (drag screenshots into the marked slides, tighten line breaks, swap fonts).

Keynote imports PowerPoint at ~95% fidelity. Colors, layout, and structure transfer cleanly. You'll likely re-pick the fonts (SF Pro Display works well for both body and headings).

## Also useful

```bash
# PDF for sharing
npx @marp-team/marp-cli docs/pitch/keynote-deck.md --pdf --output docs/pitch/keynote-deck.pdf --allow-local-files

# HTML for previewing in the browser without Keynote
npx @marp-team/marp-cli docs/pitch/keynote-deck.md --html --output docs/pitch/keynote-deck.html --allow-local-files

# Live preview while editing
npx @marp-team/marp-cli docs/pitch/keynote-deck.md --server
```

## Before you present

Fill in the placeholders in `keynote-deck.md` (or directly in Keynote after import). See `slide-blueprints.md` for component-level spec.

| Placeholder | Where | What to put |
|---|---|---|
| `[Insert 3 product screenshots side-by-side in Keynote]` | Slide 7 | Drag `content-hub.png`, `my-agent.png`, and an Interactive Story screenshot from the repo root |
| `[Insert Content Hub magazine-spread screenshot in Keynote]` | Slide 8 | Drag `group-page-magazine.png` |
| `*Add real numbers here: pilot users · sessions/week · feedback quotes*` | Slide 9 | Real usage data, OR "Closed-beta launching <date> with N families" |
| ASCII architecture diagram | Slide 5 | **Rebuild with native Keynote shapes** after import — biggest visible polish win |

## 3-minute cut

If your slot is 3 minutes instead of 5, drop these slides:

- **Slide 3** (Today's AI fails kids) — useful but optional
- **Slide 6** (Why this is hard) — fold one bullet into Slide 5

That leaves 8 slides at ~22 seconds each.

## Why Marp instead of building in Keynote directly

- **Version-controlled** — the deck source lives in git; future you can diff what changed
- **Fast iteration** — edit text, recompile in 2 seconds, no Keynote restart
- **Consistent design** — the inline CSS at the top of the deck is the design system; every slide stays on-brand without manual styling
- **One source, many formats** — same `.md` compiles to PPTX, PDF, and HTML

The trade-off: complex visual tweaks (gradient overlays, custom shapes, animations) are easier in Keynote directly. Use Marp to set the structure and typography; finish the visuals in Keynote after import.
