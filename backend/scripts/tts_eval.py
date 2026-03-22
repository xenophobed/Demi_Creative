#!/usr/bin/env python3
"""
TTS Evaluation Harness (#246)

Generates audio from all providers for the golden story set and logs
objective metrics (latency, file size, cost estimate, success rate).

Usage:
    python backend/scripts/tts_eval.py                  # run all
    python backend/scripts/tts_eval.py --provider openai # one provider
    python backend/scripts/tts_eval.py --age-group 3-5   # one age group
    python backend/scripts/tts_eval.py --dry-run          # list stories only

Output:
    data/eval/results/          — generated audio files
    data/eval/eval_results.json — metrics log
    data/eval/eval_summary.txt  — human-readable summary
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.tts_service import generate_story_audio_file  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

STORIES_DIR = Path(__file__).resolve().parents[2] / "data" / "eval" / "stories"
RESULTS_DIR = Path(__file__).resolve().parents[2] / "data" / "eval" / "results"

PROVIDERS = ["openai", "replicate", "elevenlabs"]

# Representative voice per provider per age group
VOICE_MATRIX = {
    "openai": {"3-5": "nova", "6-8": "shimmer", "9-12": "echo"},
    "replicate": {"3-5": "Calm_Woman", "6-8": "Lively_Girl", "9-12": "Young_Knight"},
    "elevenlabs": {
        "3-5": "EXAVITQu4vr4xnSDxMaL",   # Sarah
        "6-8": "IKne3meq5aSn9XLyUdCD",     # Charlie
        "9-12": "CwhRBWXzGAHq8TQ4Fs17",    # Roger
    },
}

# Rough cost per 1 M characters (USD) — as of 2025
COST_PER_MILLION_CHARS = {
    "openai": 15.00,
    "replicate": 6.50,
    "elevenlabs": 11.00,
}

AGE_GROUPS = ["3-5", "6-8", "9-12"]


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    story_file: str
    age_group: str
    scene_type: str
    provider: str
    voice: str
    success: bool
    latency_ms: float = 0.0
    file_size_bytes: int = 0
    text_length: int = 0
    estimated_cost_usd: float = 0.0
    error: Optional[str] = None
    audio_path: Optional[str] = None
    fallback_used: bool = False


@dataclass
class ProviderSummary:
    provider: str
    total_runs: int = 0
    successes: int = 0
    failures: int = 0
    fallback_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    avg_file_size_kb: float = 0.0
    success_rate: float = 0.0


# ── Story discovery ───────────────────────────────────────────────────────

def discover_stories() -> list[dict]:
    """Find golden stories, return list of {path, age_group, scene_type}."""
    stories = []
    for path in sorted(STORIES_DIR.glob("*.txt")):
        name = path.stem  # e.g. age_3_5_bedtime
        parts = name.split("_")
        # Parse age group from filename: age_3_5_xxx → "3-5"
        if len(parts) >= 4 and parts[0] == "age":
            age_group = f"{parts[1]}-{parts[2]}"
            scene_type = "_".join(parts[3:])
        else:
            age_group = "unknown"
            scene_type = name
        stories.append({
            "path": str(path),
            "age_group": age_group,
            "scene_type": scene_type,
            "filename": path.name,
        })
    return stories


# ── Evaluation runner ─────────────────────────────────────────────────────

async def evaluate_single(
    story: dict,
    provider: str,
    output_dir: Path,
) -> EvalResult:
    """Generate audio for one story with one provider, return metrics."""
    text = Path(story["path"]).read_text(encoding="utf-8").strip()
    age_group = story["age_group"]
    voice = VOICE_MATRIX.get(provider, {}).get(age_group, "nova")

    out_label = f"{story['filename'].replace('.txt', '')}_{provider}"
    audio_path = str(output_dir / f"{out_label}.mp3")

    result = EvalResult(
        story_file=story["filename"],
        age_group=age_group,
        scene_type=story["scene_type"],
        provider=provider,
        voice=voice,
        success=False,
        text_length=len(text),
    )

    start = time.perf_counter()
    try:
        gen = await generate_story_audio_file(
            text=text,
            voice=voice,
            speed=None,
            provider=provider,
            age_group=age_group,
        )
        elapsed = (time.perf_counter() - start) * 1000

        result.success = gen.get("success", False)
        result.latency_ms = gen.get("latency_ms", elapsed)
        result.fallback_used = gen.get("fallback_used", False)
        result.error = gen.get("error")

        actual_path = gen.get("audio_path")
        if actual_path and Path(actual_path).exists():
            # Move to eval results dir
            dest = Path(audio_path)
            Path(actual_path).rename(dest)
            result.audio_path = str(dest)
            result.file_size_bytes = dest.stat().st_size
        elif actual_path:
            result.audio_path = actual_path
            try:
                result.file_size_bytes = Path(actual_path).stat().st_size
            except FileNotFoundError:
                pass

        # Estimate cost
        cost_per_char = COST_PER_MILLION_CHARS.get(provider, 0) / 1_000_000
        result.estimated_cost_usd = round(len(text) * cost_per_char, 6)

    except Exception as exc:
        result.latency_ms = (time.perf_counter() - start) * 1000
        result.error = str(exc)
        logger.error("Failed %s/%s: %s", story["filename"], provider, exc)

    return result


async def run_evaluation(
    providers: list[str],
    age_groups: list[str],
    dry_run: bool = False,
) -> list[EvalResult]:
    """Run full evaluation matrix."""
    stories = discover_stories()
    filtered = [s for s in stories if s["age_group"] in age_groups]

    logger.info(
        "Evaluation matrix: %d stories × %d providers = %d samples",
        len(filtered), len(providers), len(filtered) * len(providers),
    )

    if dry_run:
        for s in filtered:
            for p in providers:
                v = VOICE_MATRIX.get(p, {}).get(s["age_group"], "?")
                print(f"  {s['filename']:40s} {p:12s} voice={v}")
        return []

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[EvalResult] = []

    for story in filtered:
        for provider in providers:
            logger.info("Evaluating %s with %s...", story["filename"], provider)
            r = await evaluate_single(story, provider, RESULTS_DIR)
            status = "OK" if r.success else f"FAIL ({r.error})"
            logger.info(
                "  → %s  latency=%dms  size=%dB",
                status, r.latency_ms, r.file_size_bytes,
            )
            results.append(r)

    return results


# ── Summarization ─────────────────────────────────────────────────────────

def summarize(results: list[EvalResult]) -> list[ProviderSummary]:
    """Compute per-provider summary statistics."""
    from collections import defaultdict

    by_provider: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        by_provider[r.provider].append(r)

    summaries = []
    for prov, items in sorted(by_provider.items()):
        latencies = [r.latency_ms for r in items if r.success]
        sizes = [r.file_size_bytes for r in items if r.success and r.file_size_bytes > 0]

        s = ProviderSummary(provider=prov)
        s.total_runs = len(items)
        s.successes = sum(1 for r in items if r.success)
        s.failures = s.total_runs - s.successes
        s.fallback_count = sum(1 for r in items if r.fallback_used)
        s.success_rate = round(s.successes / s.total_runs, 3) if s.total_runs else 0
        s.total_cost_usd = round(sum(r.estimated_cost_usd for r in items), 4)

        if latencies:
            s.avg_latency_ms = round(sum(latencies) / len(latencies), 1)
            sorted_lat = sorted(latencies)
            p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
            s.p95_latency_ms = round(sorted_lat[p95_idx], 1)

        if sizes:
            s.avg_file_size_kb = round(sum(sizes) / len(sizes) / 1024, 1)

        summaries.append(s)
    return summaries


def write_results(results: list[EvalResult], summaries: list[ProviderSummary]):
    """Write JSON log and human-readable summary."""
    eval_dir = Path(__file__).resolve().parents[2] / "data" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # JSON log
    json_path = eval_dir / "eval_results.json"
    payload = {
        "results": [asdict(r) for r in results],
        "summaries": [asdict(s) for s in summaries],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Results written to %s", json_path)

    # Human-readable summary
    txt_path = eval_dir / "eval_summary.txt"
    lines = ["TTS Evaluation Summary", "=" * 60, ""]

    for s in summaries:
        lines.append(f"Provider: {s.provider}")
        lines.append(f"  Success rate:    {s.success_rate * 100:.1f}% ({s.successes}/{s.total_runs})")
        lines.append(f"  Fallbacks:       {s.fallback_count}")
        lines.append(f"  Avg latency:     {s.avg_latency_ms:.0f} ms")
        lines.append(f"  P95 latency:     {s.p95_latency_ms:.0f} ms")
        lines.append(f"  Avg file size:   {s.avg_file_size_kb:.1f} KB")
        lines.append(f"  Total cost:      ${s.total_cost_usd:.4f}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("Per-sample details in eval_results.json")
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Summary written to %s", txt_path)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TTS Evaluation Harness (#246)")
    parser.add_argument(
        "--provider", choices=PROVIDERS, action="append",
        help="Provider(s) to evaluate (default: all)",
    )
    parser.add_argument(
        "--age-group", choices=AGE_GROUPS, action="append",
        help="Age group(s) to evaluate (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List matrix without generating")
    args = parser.parse_args()

    providers = args.provider or PROVIDERS
    age_groups = args.age_group or AGE_GROUPS

    results = asyncio.run(run_evaluation(providers, age_groups, dry_run=args.dry_run))

    if results:
        summaries = summarize(results)
        write_results(results, summaries)

        print("\n" + "=" * 60)
        for s in summaries:
            print(f"{s.provider:12s}  success={s.success_rate*100:.0f}%  "
                  f"avg={s.avg_latency_ms:.0f}ms  p95={s.p95_latency_ms:.0f}ms  "
                  f"cost=${s.total_cost_usd:.4f}")
        print("=" * 60)


if __name__ == "__main__":
    main()
