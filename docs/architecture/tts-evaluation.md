# TTS Provider Evaluation & Recommendation

> Decision document for Epic #45 — TTS & Audio Pipeline Upgrade

## 1. Providers Under Evaluation

| Provider | Model | Pricing (per 1M chars) | Latency Class | Expressiveness |
|----------|-------|----------------------|---------------|----------------|
| **OpenAI** | tts-1 | ~$15.00 | Low (~1-2s) | Limited (no emotion params) |
| **Replicate** | minimax/speech-02-turbo | ~$6.50 | Medium (~3-5s) | High (emotion, pitch, volume, language_boost) |
| **ElevenLabs** | eleven_flash_v2_5 | ~$11.00 | Low-Medium (~2-3s) | High (stability, similarity_boost, style) |

## 2. Evaluation Methodology

### Golden Story Set
- 15 stories total: 5 per age group (3-5, 6-8, 9-12)
- Genre coverage: bedtime, adventure, educational
- Stored in `data/eval/stories/`
- Word count range: ~60 words (3-5) to ~130 words (9-12)

### Objective Metrics
| Metric | How Measured |
|--------|-------------|
| P95 latency | `time.perf_counter()` around `generate_story_audio_file()` |
| Cost per minute | Characters × provider rate |
| File size | `os.stat()` on generated MP3 |
| Success rate | `result["success"]` boolean |
| Fallback rate | `result["fallback_used"]` boolean |

### Subjective Rubric (MOS-style, 1-5)
| Criterion | 1 (Poor) | 3 (Acceptable) | 5 (Excellent) |
|-----------|----------|-----------------|---------------|
| **Naturalness** | Robotic, unnatural pauses | Recognizably synthetic but clear | Indistinguishable from human |
| **Expressiveness** | Monotone, flat | Some variation in tone | Dynamic emotion, matches story mood |
| **Age-appropriateness** | Too fast/complex for target age | Acceptable pace and tone | Perfect pacing and warmth for age |
| **Clarity** | Words unclear or mispronounced | Mostly clear | Every word crisp and accurate |

### Running the Harness
```bash
# Full evaluation (all providers × all age groups)
python backend/scripts/tts_eval.py

# Single provider
python backend/scripts/tts_eval.py --provider openai

# Single age group
python backend/scripts/tts_eval.py --age-group 3-5

# Dry run (preview matrix)
python backend/scripts/tts_eval.py --dry-run
```

Output files:
- `data/eval/results/` — generated audio files (45 samples)
- `data/eval/eval_results.json` — raw metrics
- `data/eval/eval_summary.txt` — human-readable summary

## 3. Quality vs Latency vs Cost Matrix

### Expected Performance Profile

|  | OpenAI | Replicate | ElevenLabs |
|--|--------|-----------|------------|
| **Naturalness** | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| **Expressiveness** | ★★☆☆☆ | ★★★★★ | ★★★★☆ |
| **Latency** | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Cost** | ★★★☆☆ | ★★★★★ | ★★★★☆ |
| **Reliability** | ★★★★★ | ★★★☆☆ | ★★★★☆ |
| **Emotion controls** | None | emotion, pitch, volume | stability, style |

### Age-Group Fit

| Age Group | Best Fit | Rationale |
|-----------|----------|-----------|
| **3-5** | OpenAI (nova/shimmer) | Reliability and speed matter most; emotion subtlety is wasted on young children |
| **6-8** | ElevenLabs | Good balance of naturalness, expressiveness, and speed; children notice voice quality |
| **9-12** | ElevenLabs or Replicate | Older children benefit from expressive emotion; Replicate offers finer control but higher latency |

## 4. Default Provider Recommendation

### Primary: **OpenAI** (unchanged)

**Rationale:**
1. **Reliability** — No third-party SDK failures or API key requirements beyond what we already have
2. **Latency** — Fastest P95 latency, critical for streaming story generation
3. **Cost** — Moderate, but offset by universal reliability (zero fallback overhead)
4. **Simplicity** — Works for all age groups without tuning

### Upgrade Path: **ElevenLabs** as opt-in premium tier

When the user selects a voice from the VoicePicker that belongs to ElevenLabs, we use ElevenLabs. This preserves OpenAI as the safe default while offering premium quality for users who actively choose it.

### Replicate: **Specialist use only**

Best for scenarios requiring fine-grained emotion/pitch/volume control (e.g., Morning Show multi-speaker, interactive story with dynamic mood). Not recommended as a general default due to higher latency and less predictable availability.

## 5. Fallback Strategy (Current)

```
Selected provider → retry once (transient errors) → OpenAI fallback
```

This three-level chain ensures every audio request completes. The `fallback_used` metric tracks how often we fall back, serving as a provider reliability signal.

## 6. Scene Profile Integration

Scene profiles (`bedtime`, `adventure`, `spooky`, `educational`) are defined in `tts_service.py` and map to ElevenLabs voice settings. They are currently not wired into any endpoint — recommended as a follow-up to pass `scene_profile` from the story generation agent to the TTS call.

| Profile | Speed | Stability | Style | Notes |
|---------|-------|-----------|-------|-------|
| bedtime | 0.85 | 0.7 | 0.1 | Slow, calm, minimal expression |
| adventure | 1.1 | 0.3 | 0.5 | Fast, dynamic, high expression |
| spooky | 0.95 | 0.4 | 0.3 | Restricted to 9-12; younger → adventure |
| educational | 1.0 | 0.65 | 0.0 | Neutral, clear, steady |

## 7. Future Work

- [ ] Wire scene profiles into story generation agent output
- [ ] Add voice preview endpoint for VoicePicker (currently visual-only)
- [ ] Continuous evaluation in CI (blocked by API key cost — out of scope per #246)
- [ ] User-facing quality feedback collection (Phase 3)
- [ ] Voice cloning via Replicate (#150, Phase 3)
