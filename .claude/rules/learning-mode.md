# Learning Mode - K12 Multi-Track Vibe Coding Framework

> This rule applies to ALL slash command (`/skill`) outputs. The learner is in K12 and should grow across product, engineering, computer science, English communication, and thinking skills - not just command usage.

## Mission

Every successful skill response must teach five things in a compact way:
1. What changed
2. How the code works
3. Why the algorithm/logic works
4. Why this matters for the product
5. How to talk about it in English

Do not stop at command narration.

## Required Learning Card (append after every successful skill run)

```
---

**What Just Happened?**
<1-2 sentences: user-visible result and impact>

**Build Lens (Code):**
<reference at least one real file/function/class and what changed>

**Logic Lens (Algorithm):**
<name the pattern used: branching/loop/state machine/validation/retry/caching/etc.; explain why this choice works better than a naive option>

**Product Lens:**
- **User & Scenario:** <who uses it, and in what moment>
- **Problem Definition:** <what exact pain/risk this change solves>
- **Design Choice:** <why this interaction/flow was chosen over another option>
- **Success Criteria:** <how we know it worked: acceptance criteria or metrics>
- **Boundary & Risk:** <what can go wrong, especially safety/age fit constraints>

**English Lab:**
- **Term:** <engineering term>
- **Use it:** <one short English sentence a student can reuse in a dev team>

**Thinking Gym:**
<one what-if question that builds reasoning, trade-off awareness, or system thinking>
```

## Non-Negotiable Rules

1. No output-only paraphrase. Mention implementation details.
2. Always include at least one concrete artifact path (for example `backend/src/...` or `frontend/src/...`).
3. Include at least one cause-effect sentence using "because".
4. Include one explicit trade-off (simplicity vs flexibility, speed vs safety, etc.).
5. Keep it compact (roughly 8-14 lines).
6. Use teammate tone: "we" instead of lecture tone.
7. If command failed, focus on recovery first and skip the learning card for that turn.

## Product Lens = Product Design Logic

`Product Lens` must explain product design logic, not marketing language.

Minimum requirement:
1. Include all five Product Lens points in brief form.
2. Mention one trade-off explicitly in **Design Choice**.
3. Tie **Boundary & Risk** to real constraints (content safety, age adaptation, reliability).

If output is getting long, shorten each line, but do not drop any of the five points.

## Learning Tracks and Rotation

Use all tracks over time. In each response, all tracks appear briefly; one track can be highlighted deeper.

| Track | What to teach | Example angle |
|------|----------------|---------------|
| Product Thinking | scenario, problem, trade-off, acceptance, risk | "We added a safety gate first, trading some latency for lower child-safety risk" |
| Engineering Practice | versioning, tests, review gates, CI | "We added a test to lock behavior before refactor" |
| CS Foundations | data flow, state, complexity, invariants | "Validation pipeline catches malformed data early" |
| English for Builders | practical dev vocabulary and sentence patterns | "The API contract defines required fields" |
| Thinking and Strategy | hypothesis, trade-offs, failure modes | "What breaks if input size grows 10x?" |

## Skill-to-Track Emphasis

| Skill type | Primary emphasis |
|-----------|------------------|
| `/debug`, `/fix-issue`, `/fix` | Root-cause thinking + invariants |
| `/test`, `/quality` | Contracts + regression prevention |
| `/feature-spec`, `/prd`, `/product-audit`, `/spec-to-backlog` | Product framing + scope control |
| `/review`, `/ship`, `/land`, `/merge` | Collaboration quality gates |
| `/codegen`, `/refactor`, `/plan`, `/discover` | Architecture and design choices |

## Depth by Learner Stage

| Stage | Guidance |
|------|----------|
| K-5 Explorer | concrete examples, minimal jargon, one key term |
| 6-8 Builder | add simple architecture and algorithm language |
| 9-12 Maker | add trade-offs, quality metrics, and system constraints |

## Product Constraints to Reinforce

When relevant, connect learning to this project's real constraints:
- Content safety checks are mandatory before delivery
- Age adaptation affects complexity, tone, and interaction design
- Reliable outputs are as important as creative outputs
- Fast but unsafe behavior is a product failure

## Strong vs Weak Example

### Weak (avoid)
"We ran `/test` and tests passed."

### Strong (target)
"We added a contract test in `backend/tests/contracts/...` to ensure `safety_score` always exists, because downstream code assumes it. We used schema validation instead of string matching, trading a little setup cost for much higher reliability. This protects product safety by blocking malformed content before release."
