#!/usr/bin/env python3
"""Create stable two-voice Mandarin podcast audio with Qwen3-TTS."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import gc
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _package_version(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return "unavailable"


MODEL_ROOT = Path(
    os.environ.get(
        "EMOTIONAL_PODCAST_MODEL_ROOT",
        "/Volumes/Samsung/Projects/qwen3-tts-voice-design-sample/models",
    )
)
DEFAULT_VOICE_DESIGN_MODEL = MODEL_ROOT / "Qwen3-TTS-12Hz-1.7B-VoiceDesign"
DEFAULT_BASE_MODEL = MODEL_ROOT / "Qwen3-TTS-12Hz-1.7B-Base"
DEFAULT_CUSTOM_VOICE_MODEL = MODEL_ROOT / "Qwen3-TTS-12Hz-1.7B-CustomVoice"
SPEAKERS = ("女声·感性", "男声·理性")
INTRO_SEGMENT = "导入语"
DISCUSSION_SEGMENT = "讨论"
ENDING_SEGMENT = "结尾"
TRANSITION_MOVE = "承接"
MIN_INTRO_CHARACTERS = 70
MAX_INTRO_CHARACTERS = 180
MIN_TURN_CHARACTERS = 8
STANDARD_TURN_MIN = 40
STANDARD_TURN_MAX = 120
MAX_TURN_CHARACTERS = 180
MAX_TURNS_WITHOUT_SHORT = 5
ALLOWED_MOVES = {
    "承接",
    "新事实",
    "具体例子",
    "反例",
    "区分",
    "追问",
    "修正",
    "深化",
    "综合",
    "建议",
    "收束",
    "落点",
    "邀请",
}
MIN_DISTINCT_MOVES = 4
MAX_TEXT_SIMILARITY = 0.78
ALLOWED_CLAIM_TYPES = {
    "fact",
    "inference",
    "opinion",
    "example",
    "question",
    "proposal",
    "uncertainty",
}
MIN_FACT_TURNS = 2
MAX_FACT_TURNS = 4
PRONUNCIATION_SENSITIVE_PATTERN = re.compile(r"[A-Za-z0-9%％]")
TARGET_RMS_DBFS = -21.0
MASTER_TARGET_ACTIVE_RMS_DBFS = -19.0
MIN_RMS_DBFS = -28.0
MAX_RMS_DBFS = -14.0
MIN_AUDIO_DURATION = 0.4
MAX_AUDIO_DURATION = 45.0
MIN_PEAK = 0.01
MAX_PEAK = 0.98
MAX_CLIPPING_RATIO = 0.001
MAX_SILENCE_RATIO = 0.68
MIN_SPEECH_RATE = 1.2
MAX_SPEECH_RATE = 8.5
ENDING_MOVES = ("综合", "收束", "落点", "邀请")
ENDING_CLAIM_TYPES = ("inference", "uncertainty", "proposal", "question")
MIN_SCRIPT_CHARACTERS = 1500
MAX_SCRIPT_CHARACTERS = 2800
EDITORIAL_REVIEW_CHECKS = (
    "opening_transition_semantics",
    "turn_length_exceptions",
    "semantic_progression",
    "fact_source_alignment",
    "tts_text_accuracy",
    "closing_language",
)
REFERENCE_TEXTS = {
    "女声·感性": (
        "我想先把那种说不清楚的感受放在这里。很多时候，人真正需要的，"
        "不是一个标准答案，而是有人愿意认真听完。"
    ),
    "男声·理性": (
        "我们可以把情绪和事实分开来看，但不必否定任何真实感受。"
        "先确认问题，再比较选择，答案通常会清楚一些。"
    ),
}
DEFAULT_PROMPTS = {
    "女声·感性": (
        "Expressive Mandarin female podcast host; warm, intimate and emotionally "
        "responsive. Use clearly varied pitch, dynamic emphasis, natural breath, "
        "short reflective pauses, and lively conversational timing. Sound tender "
        "when validating feelings, quietly surprised when noticing ambiguity, and "
        "firm but not aggressive when challenging an idea. Keep the emotion "
        "believable and nuanced; never flat, theatrical, sing-song, or melodramatic."
    ),
    "男声·理性": (
        "Expressive Mandarin male podcast host; intelligent, grounded and warm. "
        "Use noticeable but natural pitch movement, purposeful emphasis, varied "
        "speech energy, and conversational pauses. Begin measured, become more "
        "animated when testing a counterexample, sound precise when separating "
        "facts from assumptions, and soften during mutual revision. Stay human, "
        "clear and non-preachy; never flat, monotone, theatrical, or aggressive."
    ),
}

DEFAULT_TEMPERATURE = 0.55
DEFAULT_TOP_P = 0.9
DEFAULT_ROOM_TONE_DBFS = -58.0
MAX_OVERLAP_MS = 150
ESTIMATED_SPOKEN_CHARACTERS_PER_SECOND = 4.6
TARGET_TURN_CHARACTERS = 72
NATURAL_HARD_TURN_CHARACTERS = 96
MAX_EXCEPTION_TURN_CHARACTERS = 120
MAX_LONG_TURNS = 2
EXPRESSIVE_MOVES = {"追问", "反例", "修正", "综合", "邀请"}
BACKENDS = {"auto", "clone", "custom"}
CUSTOM_SPEAKERS = {
    "女声·感性": "Serena",
    "男声·理性": "Dylan",
}
ALLOWED_PACES = {"slow", "slightly_slow", "natural", "slightly_fast", "fast"}
ALLOWED_ENERGIES = {"low", "medium_low", "medium", "medium_high", "high"}
ALLOWED_PITCHES = {"low", "slightly_low", "natural", "slightly_high", "high"}
ALLOWED_ENDINGS = {"settling", "level", "rising", "falling", "open"}
DEFAULT_PERFORMANCE = {
    "emotion": "平静专注",
    "intensity": 0.35,
    "pace": "natural",
    "energy": "medium",
    "pitch": "natural",
    "ending": "level",
    "key_emphasis": [],
}
PERFORMANCE_LABELS = {
    "pace": {
        "slow": "语速慢",
        "slightly_slow": "语速略慢",
        "natural": "自然语速",
        "slightly_fast": "语速略快",
        "fast": "语速快",
    },
    "energy": {
        "low": "低能量",
        "medium_low": "能量稍低",
        "medium": "中等能量",
        "medium_high": "能量稍高",
        "high": "高能量",
    },
    "pitch": {
        "low": "音高偏低",
        "slightly_low": "音高略低",
        "natural": "自然音高",
        "slightly_high": "音高略高",
        "high": "音高偏高",
    },
    "ending": {
        "settling": "句尾自然放松并留白",
        "level": "句尾平稳",
        "rising": "句尾自然上扬",
        "falling": "句尾自然下落",
        "open": "句尾保持开放感",
    },
}


def normalized_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE).lower()


def text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(
        None,
        normalized_text(left),
        normalized_text(right),
        autojunk=False,
    ).ratio()


def resolve_backend(requested: str, custom_model: Path) -> str:
    if requested not in BACKENDS:
        raise ValueError(f"unsupported synthesis backend: {requested}")
    if requested == "auto":
        return "custom" if custom_model.exists() else "clone"
    if requested == "custom" and not custom_model.exists():
        raise FileNotFoundError(
            f"CustomVoice model is required for --backend custom: {custom_model}"
        )
    return requested


def validate_performance(line: dict[str, Any]) -> dict[str, Any]:
    raw = line.get("performance")
    if raw is None:
        performance = dict(DEFAULT_PERFORMANCE)
    elif not isinstance(raw, dict):
        raise ValueError(f"line {line['index']} performance must be an object")
    else:
        performance = {**DEFAULT_PERFORMANCE, **raw}

    emotion = str(performance.get("emotion", "")).strip()
    if not emotion or len(emotion) > 24:
        raise ValueError(
            f"line {line['index']} performance.emotion must contain 1-24 characters"
        )
    try:
        intensity = float(performance["intensity"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"line {line['index']} performance.intensity must be numeric"
        ) from exc
    if not 0.0 <= intensity <= 1.0:
        raise ValueError(
            f"line {line['index']} performance.intensity must be between 0 and 1"
        )

    allowed_fields = {
        "pace": ALLOWED_PACES,
        "energy": ALLOWED_ENERGIES,
        "pitch": ALLOWED_PITCHES,
        "ending": ALLOWED_ENDINGS,
    }
    for field, allowed in allowed_fields.items():
        value = performance[field]
        if value not in allowed:
            choices = "、".join(sorted(allowed))
            raise ValueError(
                f"line {line['index']} performance.{field} must be one of: {choices}"
            )

    emphasis = performance.get("key_emphasis", [])
    if not isinstance(emphasis, list) or len(emphasis) > 3:
        raise ValueError(
            f"line {line['index']} performance.key_emphasis must be a list "
            "with at most three items"
        )
    normalized_emphasis: list[str] = []
    spoken_text = str(line.get("tts_text", line.get("text", "")))
    for phrase in emphasis:
        normalized = str(phrase).strip()
        if not normalized:
            raise ValueError(
                f"line {line['index']} performance.key_emphasis contains an empty item"
            )
        if normalized not in spoken_text:
            raise ValueError(
                f"line {line['index']} emphasis phrase is absent from spoken text: "
                f"{normalized}"
            )
        normalized_emphasis.append(normalized)

    return {
        "emotion": emotion,
        "intensity": round(intensity, 3),
        "pace": performance["pace"],
        "energy": performance["energy"],
        "pitch": performance["pitch"],
        "ending": performance["ending"],
        "key_emphasis": normalized_emphasis,
    }


def build_performance_instruct(line: dict[str, Any]) -> str:
    performance = validate_performance(line)
    intensity = performance["intensity"]
    if intensity < 0.25:
        intensity_label = "情绪非常克制"
    elif intensity < 0.5:
        intensity_label = "情绪克制但可感知"
    elif intensity < 0.75:
        intensity_label = "情绪清晰但不过度"
    else:
        intensity_label = "情绪鲜明但不要戏剧化"
    parts = [
        f"以{performance['emotion']}的状态说话",
        intensity_label,
        PERFORMANCE_LABELS["pace"][performance["pace"]],
        PERFORMANCE_LABELS["energy"][performance["energy"]],
        PERFORMANCE_LABELS["pitch"][performance["pitch"]],
        PERFORMANCE_LABELS["ending"][performance["ending"]],
    ]
    if performance["key_emphasis"]:
        quoted = "、".join(f"“{phrase}”" for phrase in performance["key_emphasis"])
        parts.append(f"自然重读{quoted}")
    legacy = str(line.get("voice_prompt", "")).strip()
    if legacy:
        parts.append(legacy)
    parts.append("保持真实对谈感，不播报、不夸张、不拖腔")
    return "；".join(parts) + "。"


def contextual_performance_instruct(
    line: dict[str, Any],
    previous_line: dict[str, Any] | None,
) -> str:
    base = build_performance_instruct(line)
    if previous_line is None:
        return base
    previous_type = previous_line.get("claim_type")
    current_move = line.get("move")
    if current_move == "修正":
        context = "这是听完上一位后发生的真实修正，先有短暂思考停顿再开口"
    elif current_move == "新事实" or line.get("claim_type") == "fact":
        context = "承接上一位后补充新事实，事实部分说得清楚、准确而不播报"
    elif current_move == "反例":
        context = "这是针对上一位观点给出的反例，让反例和转折关系自然可听见"
    elif current_move == "综合":
        context = "把双方刚才的观点综合起来并自然收束，不要突然变成总结播报"
    elif previous_type == "question":
        context = "这是对上一位问题的即时回应，先接住问题再展开"
    elif previous_line.get("move") in {"反例", "区分"}:
        context = "上一位刚提出反例或区别，回应时要让转折关系可听见"
    elif current_move == "追问":
        context = "承接上一位的最后落点再追问或挑战，不要像另起一段"
    elif current_move in {"承接", "深化"}:
        context = "自然接续上一位的语气和观点，像同一场正在发生的对谈"
    else:
        context = "这是紧接上一位的现场回应，不要读成孤立旁白"
    return f"{context}；{base}"


def natural_dialogue_report(
    lines: list[dict[str, Any]],
    policy: str = "strict",
) -> dict[str, Any]:
    if policy not in {"strict", "advisory"}:
        raise ValueError("natural dialogue policy must be strict or advisory")
    turn_records: list[dict[str, Any]] = []
    violations: list[str] = []
    long_turns = 0
    for line in lines[1:]:
        spoken_text = str(line.get("tts_text", line["text"])).strip()
        characters = len(spoken_text)
        estimated_seconds = characters / ESTIMATED_SPOKEN_CHARACTERS_PER_SECOND
        is_long = characters > TARGET_TURN_CHARACTERS
        if is_long:
            long_turns += 1
        exception = str(line.get("pacing_exception", "")).strip()
        status = "target"
        if characters > MAX_EXCEPTION_TURN_CHARACTERS:
            status = "too_long"
            violations.append(
                f"line {line['index']} exceeds the {MAX_EXCEPTION_TURN_CHARACTERS}"
                "-character natural dialogue ceiling"
            )
        elif characters > NATURAL_HARD_TURN_CHARACTERS:
            if len(exception) < 8:
                status = "missing_exception"
                violations.append(
                    f"line {line['index']} contains {characters} characters and "
                    "requires a specific pacing_exception"
                )
            else:
                status = "approved_exception"
        elif is_long:
            status = "long"
        turn_records.append(
            {
                "index": line["index"],
                "characters": characters,
                "estimated_seconds": round(estimated_seconds, 3),
                "status": status,
                "pacing_exception": exception or None,
            }
        )
    if long_turns > MAX_LONG_TURNS:
        violations.append(
            f"discussion contains {long_turns} long turns; maximum is {MAX_LONG_TURNS}"
        )
    report = {
        "policy": policy,
        "passed": not violations,
        "estimated_characters_per_second": ESTIMATED_SPOKEN_CHARACTERS_PER_SECOND,
        "target_turn_characters": TARGET_TURN_CHARACTERS,
        "hard_turn_characters": NATURAL_HARD_TURN_CHARACTERS,
        "maximum_exception_characters": MAX_EXCEPTION_TURN_CHARACTERS,
        "maximum_long_turns": MAX_LONG_TURNS,
        "long_turns": long_turns,
        "turns": turn_records,
        "violations": violations,
    }
    if violations and policy == "strict":
        raise ValueError("natural dialogue pacing failed: " + "; ".join(violations))
    return report


def is_expressive_line(line: dict[str, Any]) -> bool:
    if line.get("claim_type") == "fact" and not line.get("performance"):
        return False
    performance = validate_performance(line)
    return (
        performance["intensity"] >= 0.55
        or line.get("move") in EXPRESSIVE_MOVES
    )


def prosody_metrics(wav: Any, sample_rate: int) -> dict[str, float | int | None]:
    import numpy as np

    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    frame_size = max(1, int(sample_rate * 0.04))
    hop = max(1, int(sample_rate * 0.02))
    if audio.size < frame_size:
        audio = np.pad(audio, (0, frame_size - audio.size))
    starts = np.arange(0, audio.size - frame_size + 1, hop)
    frames = np.stack([audio[start : start + frame_size] for start in starts])
    frame_rms = np.sqrt(np.mean(np.square(frames), axis=1, dtype=np.float64))
    voiced_threshold = max(0.001, float(np.percentile(frame_rms, 35)) * 0.5)
    voiced = frame_rms >= voiced_threshold
    voiced_rms = frame_rms[voiced]
    voiced_db = 20.0 * np.log10(np.maximum(voiced_rms, 1e-9))
    dynamic_range = (
        float(np.percentile(voiced_db, 90) - np.percentile(voiced_db, 10))
        if voiced_db.size
        else 0.0
    )
    voiced_indexes = np.flatnonzero(voiced)
    if voiced_indexes.size >= 2:
        times = voiced_indexes * hop / sample_rate
        slope = float(np.polyfit(times, voiced_db, 1)[0])
    else:
        slope = 0.0

    silent = ~voiced
    pause_count = 0
    run = 0
    minimum_pause_frames = max(2, round(0.12 / (hop / sample_rate)))
    for is_silent in silent:
        if is_silent:
            run += 1
        else:
            if run >= minimum_pause_frames:
                pause_count += 1
            run = 0
    if run >= minimum_pause_frames:
        pause_count += 1

    pitch_values: list[float] = []
    candidate_indexes = voiced_indexes
    if candidate_indexes.size > 48:
        positions = np.linspace(0, candidate_indexes.size - 1, 48).astype(int)
        candidate_indexes = candidate_indexes[positions]
    min_lag = max(1, int(sample_rate / 350))
    max_lag = min(frame_size - 2, int(sample_rate / 70))
    for frame_index in candidate_indexes:
        frame = frames[frame_index] - float(np.mean(frames[frame_index]))
        energy = float(np.dot(frame, frame))
        if energy <= 1e-8:
            continue
        correlation = np.correlate(frame, frame, mode="full")[frame_size - 1 :]
        region = correlation[min_lag : max_lag + 1]
        if not region.size:
            continue
        lag = int(np.argmax(region)) + min_lag
        confidence = float(correlation[lag] / max(correlation[0], 1e-9))
        if confidence >= 0.25:
            pitch_values.append(sample_rate / lag)
    pitch_median = float(np.median(pitch_values)) if pitch_values else None
    pitch_range = (
        float(np.percentile(pitch_values, 90) - np.percentile(pitch_values, 10))
        if len(pitch_values) >= 2
        else 0.0
    )
    return {
        "voiced_dynamic_range_db": round(dynamic_range, 3),
        "energy_slope_db_per_second": round(slope, 3),
        "pause_count": pause_count,
        "pitch_median_hz": round(pitch_median, 3) if pitch_median else None,
        "pitch_range_hz": round(pitch_range, 3),
    }


def score_candidate(
    metrics: dict[str, Any],
    line: dict[str, Any],
    target_rms_dbfs: float,
) -> dict[str, Any]:
    performance = validate_performance(line)
    pace_targets = {
        "slow": 3.2,
        "slightly_slow": 3.8,
        "natural": 4.6,
        "slightly_fast": 5.3,
        "fast": 6.0,
    }
    reasons: list[str] = []
    score = 100.0
    issues = list(metrics.get("quality_issues", []))
    if issues:
        score -= 40.0 + 5.0 * len(issues)
        reasons.append("存在自动质量问题：" + "、".join(issues))
    speech_rate = float(metrics.get("spoken_characters_per_second", 0.0))
    rate_error = abs(speech_rate - pace_targets[performance["pace"]])
    score -= min(24.0, rate_error * 6.0)
    reasons.append(f"语速与目标偏差 {rate_error:.2f} 字/秒")
    active_rms = float(metrics.get("active_rms_dbfs", -120.0))
    loudness_error = abs(active_rms - target_rms_dbfs)
    score -= min(12.0, loudness_error * 2.0)
    reasons.append(f"有效语音响度偏差 {loudness_error:.2f} dB")
    desired_dynamic = 3.0 + performance["intensity"] * 5.0
    dynamic = float(metrics.get("voiced_dynamic_range_db", 0.0))
    dynamic_error = abs(dynamic - desired_dynamic)
    score -= min(12.0, dynamic_error * 1.5)
    reasons.append(f"动态范围与表演强度偏差 {dynamic_error:.2f} dB")
    pitch_range = float(metrics.get("pitch_range_hz", 0.0))
    if performance["intensity"] >= 0.55 and pitch_range < 18.0:
        score -= 8.0
        reasons.append("高情绪句音高变化偏小")
    if float(metrics.get("clipping_ratio", 0.0)) > MAX_CLIPPING_RATIO:
        score -= 30.0
        reasons.append("存在削波")
    return {"score": round(max(0.0, score), 3), "reasons": reasons}


def select_best_candidate(
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not candidates:
        raise ValueError("candidate selection requires at least one candidate")
    ranked = sorted(
        candidates,
        key=lambda item: (-float(item["evaluation"]["score"]), int(item["candidate"])),
    )
    selected = ranked[0]
    report_candidates = []
    for item in sorted(candidates, key=lambda candidate: int(candidate["candidate"])):
        report_candidates.append(
            {
                key: value
                for key, value in item.items()
                if key not in {"wav"}
            }
            | {"selected": item is selected}
        )
    return selected, {
        "selected_candidate": selected["candidate"],
        "candidate_count": len(candidates),
        "candidates": report_candidates,
    }


def validate_timing(line: dict[str, Any]) -> dict[str, int]:
    raw = line.get("timing")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"line {line['index']} timing must be an object")
    allowed = {"pause_after_ms", "overlap_next_ms"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(
            f"line {line['index']} timing has unsupported fields: "
            + "、".join(sorted(unknown))
        )
    if len(raw) > 1:
        raise ValueError(
            f"line {line['index']} timing pause and overlap are mutually exclusive"
        )
    if not raw:
        return {}
    field, raw_value = next(iter(raw.items()))
    if isinstance(raw_value, bool):
        raise ValueError(f"line {line['index']} timing.{field} must be numeric")
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"line {line['index']} timing.{field} must be numeric"
        ) from exc
    maximum = 3000 if field == "pause_after_ms" else MAX_OVERLAP_MS
    if not 0 <= value <= maximum:
        raise ValueError(
            f"line {line['index']} timing.{field} must be between 0 and {maximum}"
        )
    return {field: value}


def transition_after_ms(
    line: dict[str, Any],
    next_line: dict[str, Any],
    default_ms: int,
    intro_ms: int,
) -> int:
    timing = validate_timing(line)
    if "pause_after_ms" in timing:
        return timing["pause_after_ms"]
    if "overlap_next_ms" in timing:
        return -timing["overlap_next_ms"]
    if line.get("segment") == INTRO_SEGMENT:
        return intro_ms
    text_length = len(str(line.get("tts_text", line["text"])).strip())
    if text_length < 20:
        return 180
    if line.get("segment") == ENDING_SEGMENT:
        return 650
    if line.get("move") in {"修正", "收束"}:
        return 520
    if next_line.get("move") in {"反例", "区分", "修正"}:
        return 420
    if line.get("claim_type") == "question":
        return 280
    return default_ms


def make_room_tone(
    sample_count: int,
    level_dbfs: float = DEFAULT_ROOM_TONE_DBFS,
    seed: int = 0,
) -> Any:
    import numpy as np

    if sample_count <= 0:
        return np.zeros(0, dtype=np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(sample_count + 6).astype(np.float32)
    kernel = np.asarray([1, 2, 3, 3, 2, 1], dtype=np.float32)
    kernel /= float(np.sum(kernel))
    tone = np.convolve(noise, kernel, mode="valid")[:sample_count]
    rms = float(np.sqrt(np.mean(np.square(tone), dtype=np.float64)))
    target_rms = 10 ** (level_dbfs / 20)
    if rms > 0:
        tone = tone * (target_rms / rms)
    return np.asarray(tone, dtype=np.float32)


def assemble_conversation(
    wavs: list[Any],
    lines: list[dict[str, Any]],
    sample_rate: int,
    default_pause_seconds: float,
    intro_pause_seconds: float,
    outro_seconds: float,
    room_tone_dbfs: float = DEFAULT_ROOM_TONE_DBFS,
) -> tuple[Any, list[dict[str, Any]]]:
    import numpy as np

    if len(wavs) != len(lines) or not wavs:
        raise ValueError("wavs and lines must be non-empty and have matching lengths")
    combined = np.asarray(wavs[0], dtype=np.float32).reshape(-1).copy()
    transitions: list[dict[str, Any]] = []
    default_ms = round(default_pause_seconds * 1000)
    intro_ms = round(intro_pause_seconds * 1000)
    for position, next_wav in enumerate(wavs[1:]):
        current_line = lines[position]
        next_line = lines[position + 1]
        transition_ms = transition_after_ms(
            current_line, next_line, default_ms, intro_ms
        )
        next_audio = np.asarray(next_wav, dtype=np.float32).reshape(-1)
        if transition_ms >= 0:
            transition_samples = round(sample_rate * transition_ms / 1000)
            tone = make_room_tone(
                transition_samples,
                level_dbfs=room_tone_dbfs,
                seed=position + 1,
            )
            combined = np.concatenate((combined, tone, next_audio))
            kind = "room_tone_pause"
        else:
            requested_samples = round(sample_rate * abs(transition_ms) / 1000)
            transition_samples = min(
                requested_samples, combined.size, next_audio.size
            )
            if transition_samples:
                ramp = np.linspace(
                    0.0, 1.0, transition_samples, endpoint=False, dtype=np.float32
                )
                combined[-transition_samples:] = (
                    combined[-transition_samples:] * (1.0 - ramp)
                    + next_audio[:transition_samples] * ramp
                )
                combined = np.concatenate((combined, next_audio[transition_samples:]))
            else:
                combined = np.concatenate((combined, next_audio))
            kind = "crossfade_overlap"
        transitions.append(
            {
                "after_line": current_line["index"],
                "before_line": next_line["index"],
                "milliseconds": transition_ms,
                "samples": transition_samples,
                "kind": kind,
                "source": "explicit" if current_line.get("timing") else "derived",
            }
        )
    outro_samples = round(sample_rate * outro_seconds)
    combined = np.concatenate(
        (
            combined,
            make_room_tone(
                outro_samples,
                level_dbfs=room_tone_dbfs,
                seed=len(lines) + 1,
            ),
        )
    )
    transitions.append(
        {
            "after_line": lines[-1]["index"],
            "before_line": None,
            "milliseconds": round(outro_seconds * 1000),
            "samples": outro_samples,
            "kind": "outro_room_tone",
            "source": "configured",
        }
    )
    return np.asarray(combined, dtype=np.float32), transitions


def load_evidence(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"missing required evidence file: {path.name}")
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("01-evidence.json must contain a non-empty array")
    evidence: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    required = ("id", "claim", "source_title", "source_url", "source_date")
    for position, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"evidence item {position} must be an object")
        for field in required:
            if not str(record.get(field, "")).strip():
                raise ValueError(f"evidence item {position} missing {field}")
        evidence_id = str(record["id"]).strip()
        if evidence_id in evidence:
            raise ValueError(f"duplicate evidence id: {evidence_id}")
        source_url = str(record["source_url"]).strip()
        parsed_url = urlparse(source_url)
        if (
            parsed_url.scheme not in {"https", "http"}
            or not parsed_url.netloc
            or "." not in parsed_url.netloc
        ):
            raise ValueError(f"evidence {evidence_id} has invalid source_url")
        normalized_url = source_url.rstrip("/")
        if normalized_url in seen_urls:
            raise ValueError(f"duplicate evidence source_url: {source_url}")
        seen_urls.add(normalized_url)
        evidence[evidence_id] = record
    return evidence


def validate_claims(
    lines: list[dict[str, Any]], evidence: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    fact_turns: list[dict[str, Any]] = []
    cited_ids: set[str] = set()
    claim_counts = {claim_type: 0 for claim_type in sorted(ALLOWED_CLAIM_TYPES)}
    for line in lines[1:]:
        claim_type = line.get("claim_type")
        if claim_type not in ALLOWED_CLAIM_TYPES:
            allowed = "、".join(sorted(ALLOWED_CLAIM_TYPES))
            raise ValueError(
                f"discussion line {line['index']} must declare one claim_type: {allowed}"
            )
        claim_counts[claim_type] += 1
        source_ids = line.get("source_ids", [])
        if not isinstance(source_ids, list):
            raise ValueError(f"discussion line {line['index']} source_ids must be a list")
        if claim_type == "fact":
            if not source_ids:
                raise ValueError(
                    f"fact line {line['index']} must cite at least one source_id"
                )
            for source_id in source_ids:
                if source_id not in evidence:
                    raise ValueError(
                        f"fact line {line['index']} cites unknown source_id: {source_id}"
                    )
                cited_ids.add(source_id)
            fact_turns.append(line)
        elif source_ids:
            raise ValueError(
                f"non-fact line {line['index']} must not cite source_ids"
            )
    if not MIN_FACT_TURNS <= len(fact_turns) <= MAX_FACT_TURNS:
        raise ValueError(
            f"discussion must contain {MIN_FACT_TURNS}-{MAX_FACT_TURNS} fact turns; "
            f"found {len(fact_turns)}"
        )
    if len(cited_ids) < 2:
        raise ValueError("fact turns must cite at least two independent evidence records")
    cited_urls = {
        str(evidence[evidence_id]["source_url"]).rstrip("/")
        for evidence_id in cited_ids
    }
    if len(cited_urls) < 2:
        raise ValueError("fact turns must cite at least two distinct source URLs")
    if claim_counts["example"] < 1:
        raise ValueError("discussion must include at least one claim_type: example")
    if claim_counts["uncertainty"] < 1:
        raise ValueError("discussion must include at least one claim_type: uncertainty")
    return {
        "counts": claim_counts,
        "fact_turns": len(fact_turns),
        "cited_evidence_ids": sorted(cited_ids),
    }


def validate_pronunciation_fields(lines: list[dict[str, Any]]) -> list[int]:
    sensitive_lines: list[int] = []
    for line in lines:
        text = str(line["text"])
        if not PRONUNCIATION_SENSITIVE_PATTERN.search(text):
            continue
        sensitive_lines.append(line["index"])
        if not str(line.get("tts_text", "")).strip():
            raise ValueError(
                f"pronunciation-sensitive line {line['index']} requires tts_text"
            )
        if not str(line.get("pronunciation_note", "")).strip():
            raise ValueError(
                f"pronunciation-sensitive line {line['index']} requires "
                "pronunciation_note"
            )
    return sensitive_lines


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_editorial_review(
    path: Path, script_path: Path, evidence_path: Path
) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing required editorial review: {path.name}")
    review = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(review, dict) or not str(review.get("reviewed_at", "")).strip():
        raise ValueError("02-editorial-review.json requires reviewed_at")
    if review.get("review_schema_version") != 1:
        raise ValueError("02-editorial-review.json requires review_schema_version: 1")
    expected_hashes = {
        "script_sha256": sha256_file(script_path),
        "evidence_sha256": sha256_file(evidence_path),
    }
    for field, expected in expected_hashes.items():
        if review.get(field) != expected:
            raise ValueError(
                f"editorial review {field} does not match the reviewed file"
            )
    checks = review.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("02-editorial-review.json requires checks object")
    for check_name in EDITORIAL_REVIEW_CHECKS:
        check = checks.get(check_name)
        if not isinstance(check, dict):
            raise ValueError(f"editorial review missing check: {check_name}")
        if check.get("status") != "passed":
            raise ValueError(f"editorial review check not passed: {check_name}")
        if len(str(check.get("notes", "")).strip()) < 8:
            raise ValueError(
                f"editorial review check needs specific notes: {check_name}"
            )
    return {
        "reviewed_at": review["reviewed_at"],
        "script_sha256": expected_hashes["script_sha256"],
        "evidence_sha256": expected_hashes["evidence_sha256"],
        "checks_passed": list(EDITORIAL_REVIEW_CHECKS),
    }


def active_audio_mask(audio: Any) -> Any:
    import numpy as np

    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not samples.size:
        return np.zeros(0, dtype=bool)
    floor = float(np.percentile(np.abs(samples), 20))
    threshold = max(0.001, floor * 3.0)
    return np.abs(samples) >= threshold


def trim_audio_preserving_breath(wav: Any, sample_rate: int) -> Any:
    import numpy as np

    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        return audio
    active = np.flatnonzero(active_audio_mask(audio))
    if not active.size:
        return audio
    leading = int(sample_rate * 0.18)
    trailing = int(sample_rate * 0.22)
    start = max(0, int(active[0]) - leading)
    end = min(audio.size, int(active[-1]) + trailing + 1)
    return np.asarray(audio[start:end], dtype=np.float32)


def target_line_rms_dbfs(line: dict[str, Any]) -> float:
    performance = validate_performance(line)
    targets = {
        "low": -23.0,
        "medium_low": -22.0,
        "medium": -21.0,
        "medium_high": -20.0,
        "high": -19.0,
    }
    target = targets[performance["energy"]]
    if line.get("segment") == INTRO_SEGMENT:
        target -= 0.75
    if performance["ending"] == "settling":
        target -= 0.5
    return max(-24.0, min(-18.5, target))


def normalize_audio(
    wav: Any,
    sample_rate: int,
    target_rms_dbfs: float = TARGET_RMS_DBFS,
) -> Any:
    import numpy as np

    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError("generated audio is empty or contains non-finite samples")
    audio = audio - float(np.mean(audio))
    audio = trim_audio_preserving_breath(audio, sample_rate)
    mask = active_audio_mask(audio)
    active = audio[mask] if np.any(mask) else audio
    rms = float(np.sqrt(np.mean(np.square(active), dtype=np.float64)))
    if rms > 0:
        target_rms = 10 ** (target_rms_dbfs / 20)
        audio = audio * (target_rms / rms)
    peak = float(np.max(np.abs(audio), initial=0.0))
    if peak > MAX_PEAK:
        audio = audio * (MAX_PEAK / peak)
    return np.asarray(audio, dtype=np.float32)


def mastering_metrics(wav: Any) -> dict[str, float]:
    import numpy as np

    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    mask = active_audio_mask(audio)
    active = audio[mask] if np.any(mask) else audio
    rms = (
        float(np.sqrt(np.mean(np.square(active), dtype=np.float64)))
        if active.size
        else 0.0
    )
    peak = float(np.max(np.abs(audio), initial=0.0))
    return {
        "active_rms_dbfs": round(float(20 * np.log10(max(rms, 1e-12))), 3),
        "peak": round(peak, 6),
        "clipping_ratio": round(
            float(np.mean(np.abs(audio) >= 0.999)) if audio.size else 1.0, 6
        ),
    }


def master_episode(
    wav: Any,
    sample_rate: int,
    target_active_rms_dbfs: float = MASTER_TARGET_ACTIVE_RMS_DBFS,
) -> tuple[Any, dict[str, Any]]:
    import numpy as np

    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    if not audio.size or not np.isfinite(audio).all():
        raise ValueError("episode audio is empty or invalid")
    before = mastering_metrics(audio)
    processed = audio.copy()

    highpass_engine = "scipy-butterworth"
    try:
        from scipy.signal import butter, sosfilt

        sos = butter(2, 70.0, btype="highpass", fs=sample_rate, output="sos")
        processed = sosfilt(sos, processed).astype(np.float32)
    except ImportError:
        highpass_engine = "one-pole-fallback"
        cutoff = 70.0
        dt = 1.0 / sample_rate
        rc = 1.0 / (2.0 * np.pi * cutoff)
        alpha = rc / (rc + dt)
        filtered = np.empty_like(processed, dtype=np.float32)
        filtered[0] = 0.0
        for index in range(1, processed.size):
            filtered[index] = alpha * (
                filtered[index - 1] + processed[index] - processed[index - 1]
            )
        processed = filtered

    padded = np.pad(processed, (1, 1), mode="edge")
    low_band = (
        padded[:-2] + 2.0 * padded[1:-1] + padded[2:]
    ) / 4.0
    high_band = processed - low_band
    deess_threshold = 10 ** (-24.0 / 20)
    deess_strength = np.clip(
        (np.abs(high_band) - deess_threshold) / max(deess_threshold, 1e-9),
        0.0,
        1.0,
    )
    processed = low_band + high_band * (1.0 - 0.22 * deess_strength)

    magnitude = np.abs(processed)
    threshold = 10 ** (-14.0 / 20)
    safe_magnitude = np.maximum(magnitude, 1e-9)
    input_db = 20.0 * np.log10(safe_magnitude)
    threshold_db = -14.0
    compressed_db = np.where(
        input_db > threshold_db,
        threshold_db + (input_db - threshold_db) / 1.6,
        input_db,
    )
    compressor_gain = 10 ** ((compressed_db - input_db) / 20.0)
    processed = processed * compressor_gain

    mask = active_audio_mask(processed)
    active = processed[mask] if np.any(mask) else processed
    active_rms = float(np.sqrt(np.mean(np.square(active), dtype=np.float64)))
    loudness_gain = 1.0
    gain_mode = "uniform"
    if active_rms > 0:
        target = 10 ** (target_active_rms_dbfs / 20)
        loudness_gain = target / active_rms
        if loudness_gain > 1.0:
            gain_mode = "activity_weighted"
            magnitude = np.abs(processed)
            activity_weight = np.clip(
                (magnitude - 0.002) / (0.010 - 0.002), 0.0, 1.0
            )
            sample_gain = 1.0 + (loudness_gain - 1.0) * activity_weight
            processed = processed * sample_gain
        else:
            processed = processed * loudness_gain
    peak = float(np.max(np.abs(processed), initial=0.0))
    peak_protection_gain = 1.0
    if peak > 0.95:
        peak_protection_gain = 0.95 / peak
        processed = processed * peak_protection_gain

    fade_samples = min(int(sample_rate * 0.01), processed.size // 2)
    if fade_samples:
        fade = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        processed[:fade_samples] *= fade
        processed[-fade_samples:] *= fade[::-1]
    processed = np.asarray(processed, dtype=np.float32)
    report = {
        "before": before,
        "after": mastering_metrics(processed),
        "highpass_hz": 70.0,
        "highpass_applied": True,
        "highpass_engine": highpass_engine,
        "deesser": {"threshold_dbfs": -24.0, "maximum_reduction": 0.22},
        "compressor": {"threshold_dbfs": -14.0, "ratio": 1.6},
        "target_active_rms_dbfs": target_active_rms_dbfs,
        "gain": {
            "loudness_gain_db": round(
                float(20 * np.log10(max(loudness_gain, 1e-12))), 3
            ),
            "peak_protection_gain_db": round(
                float(20 * np.log10(max(peak_protection_gain, 1e-12))), 3
            ),
            "total_gain_db": round(
                float(
                    20
                    * np.log10(
                        max(loudness_gain * peak_protection_gain, 1e-12)
                    )
                ),
                3,
            ),
            "mode": gain_mode,
            "activity_floor": 0.002,
            "activity_full_gain": 0.010,
        },
        "maximum_peak": 0.95,
        "fade_milliseconds": 10,
    }
    return processed, report


def audio_metrics(wav: Any, sample_rate: int, spoken_text: str) -> dict[str, float]:
    import numpy as np

    audio = np.asarray(wav, dtype=np.float32).reshape(-1)
    duration = audio.size / sample_rate if sample_rate > 0 else 0.0
    peak = float(np.max(np.abs(audio), initial=0.0))
    rms = (
        float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
        if audio.size
        else 0.0
    )
    rms_dbfs = 20 * np.log10(max(rms, 1e-12))
    mask = active_audio_mask(audio)
    active = audio[mask] if np.any(mask) else audio
    active_rms = (
        float(np.sqrt(np.mean(np.square(active), dtype=np.float64)))
        if active.size
        else 0.0
    )
    clipping_ratio = (
        float(np.mean(np.abs(audio) >= 0.999)) if audio.size else 1.0
    )
    silence_ratio = (
        float(np.mean(np.abs(audio) < 0.003)) if audio.size else 1.0
    )
    spoken_characters = len(normalized_text(spoken_text))
    speech_rate = spoken_characters / duration if duration > 0 else 0.0
    return {
        "duration_seconds": round(duration, 3),
        "peak": round(peak, 6),
        "rms_dbfs": round(float(rms_dbfs), 3),
        "active_rms_dbfs": round(
            float(20 * np.log10(max(active_rms, 1e-12))), 3
        ),
        "clipping_ratio": round(clipping_ratio, 6),
        "silence_ratio": round(silence_ratio, 6),
        "spoken_characters_per_second": round(speech_rate, 3),
    }


def audio_quality_issues(metrics: dict[str, float]) -> list[str]:
    issues: list[str] = []
    if metrics["duration_seconds"] < MIN_AUDIO_DURATION:
        issues.append("duration_too_short")
    if metrics["duration_seconds"] > MAX_AUDIO_DURATION:
        issues.append("duration_too_long")
    if metrics["peak"] <= MIN_PEAK:
        issues.append("level_too_low")
    if metrics["peak"] > MAX_PEAK:
        issues.append("peak_too_high")
    if not MIN_RMS_DBFS <= metrics["rms_dbfs"] <= MAX_RMS_DBFS:
        issues.append("rms_out_of_range")
    if metrics["clipping_ratio"] > MAX_CLIPPING_RATIO:
        issues.append("clipping")
    if metrics["silence_ratio"] > MAX_SILENCE_RATIO:
        issues.append("excessive_silence")
    if not MIN_SPEECH_RATE <= metrics["spoken_characters_per_second"] <= MAX_SPEECH_RATE:
        issues.append("speech_rate_out_of_range")
    return issues


def synthesize_line_with_quality(
    generate: Any,
    spoken_text: str,
    max_attempts: int,
    target_rms_dbfs: float = TARGET_RMS_DBFS,
) -> tuple[Any, int, float, list[dict[str, Any]]]:
    import numpy as np

    attempts: list[dict[str, Any]] = []
    elapsed = 0.0
    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        wavs, sample_rate = generate()
        attempt_elapsed = time.perf_counter() - started
        elapsed += attempt_elapsed
        raw_wav = np.asarray(wavs[0], dtype=np.float32)
        before = audio_metrics(raw_wav, sample_rate, spoken_text)
        normalized_wav = normalize_audio(
            raw_wav, sample_rate, target_rms_dbfs=target_rms_dbfs
        )
        after = audio_metrics(normalized_wav, sample_rate, spoken_text)
        raw_issues = []
        if before["clipping_ratio"] > MAX_CLIPPING_RATIO:
            raw_issues.append("raw_audio_clipping")
        issues = raw_issues + audio_quality_issues(after)
        attempts.append(
            {
                "attempt": attempt,
                "generation_seconds": round(attempt_elapsed, 3),
                "before": before,
                "after": after,
                "issues": issues,
            }
        )
        if not issues:
            return normalized_wav, sample_rate, elapsed, attempts
    raise ValueError(
        f"audio quality failed after {max_attempts} attempts: "
        f"{attempts[-1]['issues']}"
    )


def load_script(path: Path) -> list[dict[str, Any]]:
    lines = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(lines, list) or not lines:
        raise ValueError("02-script.json must contain a non-empty array")
    seen: set[int] = set()
    previous_speaker: str | None = None
    for expected_index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            raise ValueError(f"script item {expected_index} must be an object")
        for field in ("index", "speaker", "text"):
            if field not in line:
                raise ValueError(f"script item {expected_index} missing {field}")
        if line["index"] in seen:
            raise ValueError(f"duplicate line index: {line['index']}")
        if line["index"] != expected_index:
            raise ValueError(
                f"line index {line['index']} is out of sequence; expected {expected_index}"
            )
        seen.add(line["index"])
        if line["speaker"] not in SPEAKERS:
            raise ValueError(f"unsupported speaker: {line['speaker']}")
        if line["speaker"] == previous_speaker:
            if line["index"] == 2:
                raise ValueError(
                    "the transition into discussion must use speaker: 男声·理性"
                )
            raise ValueError(
                f"line {line['index']} repeats speaker {line['speaker']}; "
                "dialogue must alternate"
            )
        previous_speaker = line["speaker"]
        if not str(line["text"]).strip():
            raise ValueError(f"line {line['index']} has empty text")
        validate_performance(line)
        validate_timing(line)
    intro = lines[0]
    if intro.get("segment") != INTRO_SEGMENT:
        raise ValueError(f"line 1 must use segment: {INTRO_SEGMENT}")
    if intro["speaker"] != "女声·感性":
        raise ValueError("the opening introduction must use speaker: 女声·感性")
    intro_length = len(str(intro["text"]).strip())
    if not MIN_INTRO_CHARACTERS <= intro_length <= MAX_INTRO_CHARACTERS:
        raise ValueError(
            "the opening introduction must contain "
            f"{MIN_INTRO_CHARACTERS}-{MAX_INTRO_CHARACTERS} characters; "
            f"got {intro_length}"
        )
    for line in lines[1:]:
        if line.get("segment", DISCUSSION_SEGMENT) == INTRO_SEGMENT:
            raise ValueError("only line 1 may use segment: 导入语")
    if len(lines) < 2:
        raise ValueError("script must continue from the introduction into discussion")
    transition = lines[1]
    if transition.get("segment") != DISCUSSION_SEGMENT:
        raise ValueError("line 2 must use segment: 讨论")
    if transition.get("move") != TRANSITION_MOVE:
        raise ValueError(f"line 2 must use move: {TRANSITION_MOVE}")
    if transition["speaker"] != "男声·理性":
        raise ValueError("the transition into discussion must use speaker: 男声·理性")
    discussion_lengths = [
        len(str(line["text"]).strip())
        for line in lines[1:]
    ]
    for line, length in zip(lines[1:], discussion_lengths):
        if not MIN_TURN_CHARACTERS <= length <= MAX_TURN_CHARACTERS:
            raise ValueError(
                f"discussion line {line['index']} must contain "
                f"{MIN_TURN_CHARACTERS}-{MAX_TURN_CHARACTERS} characters; got {length}"
            )
    for start in range(0, len(discussion_lengths) - MAX_TURNS_WITHOUT_SHORT):
        window = discussion_lengths[start : start + MAX_TURNS_WITHOUT_SHORT + 1]
        if all(length >= STANDARD_TURN_MIN for length in window):
            first_index = start + 2
            last_index = first_index + MAX_TURNS_WITHOUT_SHORT
            raise ValueError(
                f"discussion lines {first_index}-{last_index} need a "
                f"{MIN_TURN_CHARACTERS}-{STANDARD_TURN_MIN - 1}-character "
                "reaction or follow-up to vary the rhythm"
            )
    discussion_moves: list[str] = []
    for line in lines[1:]:
        move = line.get("move")
        if move not in ALLOWED_MOVES:
            allowed = "、".join(sorted(ALLOWED_MOVES))
            raise ValueError(
                f"discussion line {line['index']} must declare one valid move: {allowed}"
            )
        if discussion_moves and move == discussion_moves[-1]:
            raise ValueError(
                f"discussion line {line['index']} repeats adjacent move: {move}"
            )
        discussion_moves.append(move)
    distinct_moves = set(discussion_moves)
    if len(distinct_moves) < MIN_DISTINCT_MOVES:
        raise ValueError(
            f"discussion needs at least {MIN_DISTINCT_MOVES} distinct moves; "
            f"found {len(distinct_moves)}"
        )
    if "修正" not in distinct_moves:
        raise ValueError("discussion must include at least one move: 修正")
    if not distinct_moves.intersection({"反例", "区分"}):
        raise ValueError("discussion must include at least one move: 反例 or 区分")
    if not distinct_moves.intersection({"新事实", "具体例子"}):
        raise ValueError("discussion must include at least one move: 新事实 or 具体例子")
    for right_position, right in enumerate(lines[1:], start=1):
        for left in lines[1:right_position]:
            similarity = text_similarity(str(left["text"]), str(right["text"]))
            if similarity > MAX_TEXT_SIMILARITY:
                raise ValueError(
                    f"discussion lines {left['index']} and {right['index']} are "
                    f"too similar ({similarity:.2f} > {MAX_TEXT_SIMILARITY:.2f})"
                )
    if len(lines) < 6:
        raise ValueError("script is too short to contain the required four-turn ending")
    for line in lines[1:-4]:
        if line.get("segment") != DISCUSSION_SEGMENT:
            raise ValueError(
                f"line {line['index']} must use segment: {DISCUSSION_SEGMENT}"
            )
    ending = lines[-4:]
    for line, expected_move, expected_claim_type in zip(
        ending, ENDING_MOVES, ENDING_CLAIM_TYPES
    ):
        if line.get("segment") != ENDING_SEGMENT:
            raise ValueError(
                f"ending line {line['index']} must use segment: {ENDING_SEGMENT}"
            )
        if line.get("move") != expected_move:
            raise ValueError(
                f"ending line {line['index']} must use move: {expected_move}"
            )
        if line.get("claim_type") != expected_claim_type:
            raise ValueError(
                f"ending line {line['index']} must use claim_type: "
                f"{expected_claim_type}"
            )
    if set(line["speaker"] for line in lines) != set(SPEAKERS):
        raise ValueError("script must contain both speakers")
    return lines


def role_name(speaker: str) -> str:
    return "female" if speaker == "女声·感性" else "male"


def choose_device(torch: Any) -> tuple[str, Any]:
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    if torch.cuda.is_available():
        return "cuda:0", torch.bfloat16
    return "cpu", torch.float32


def model_kwargs(torch: Any, device: str, dtype: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"device_map": device, "dtype": dtype}
    if device.startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"
    return kwargs


def clear_device_cache(torch: Any) -> None:
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def voice_prompts(lines: list[dict[str, Any]]) -> dict[str, str]:
    """Return stable role personas; per-line directions belong to performance."""
    if not lines:
        raise ValueError("cannot build voice personas for an empty script")
    return dict(DEFAULT_PROMPTS)


def write_prompt_notes(
    path: Path,
    prompts: dict[str, str],
    design_model: Path,
    clone_model: Path,
    custom_model: Path,
    backend: str,
    custom_speakers: dict[str, str],
) -> None:
    backend_note = (
        "本期使用 CustomVoice 固定角色 speaker，并把每句 performance 与 "
        "voice_prompt 合成为逐句 instruct。"
        if backend == "custom"
        else
        "本期使用 VoiceDesign 原创参考音色与 Base Voice Clone。Base 后端不支持"
        "逐句 instruct；逐句表演信息仍记录在 QC 中，供兼容、评审和迁移使用。"
    )
    path.write_text(
        "# Voice prompts and identity strategy\n\n"
        f"- 女声·感性：{prompts['女声·感性']}\n"
        f"- 男声·理性：{prompts['男声·理性']}\n\n"
        f"- Backend: `{backend}`\n"
        f"- CustomVoice speakers: `{custom_speakers}`\n\n"
        f"{backend_note}\n\n"
        "角色 persona 与逐句 performance 分离，避免开场语气锁死整期。"
        "生成过程仍具有随机性，不保证跨期完全一致。\n\n"
        f"- VoiceDesign model: `{design_model}`\n"
        f"- Voice Clone model: `{clone_model}`\n"
        f"- CustomVoice model: `{custom_model}`\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument(
        "--voice-design-model", type=Path, default=DEFAULT_VOICE_DESIGN_MODEL
    )
    parser.add_argument("--base-model", type=Path, default=DEFAULT_BASE_MODEL)
    parser.add_argument(
        "--custom-voice-model", type=Path, default=DEFAULT_CUSTOM_VOICE_MODEL
    )
    parser.add_argument(
        "--backend",
        choices=sorted(BACKENDS),
        default="auto",
        help="auto prefers CustomVoice when installed; clone preserves original voices.",
    )
    parser.add_argument(
        "--scheduled-safe",
        action="store_true",
        help="Use the bounded unattended profile: clone backend, one candidate, one attempt.",
    )
    parser.add_argument("--female-custom-speaker", default=CUSTOM_SPEAKERS["女声·感性"])
    parser.add_argument("--male-custom-speaker", default=CUSTOM_SPEAKERS["男声·理性"])
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Sampling temperature for more varied prosody and expression.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=DEFAULT_TOP_P,
        help="Nucleus sampling threshold for expressive variation.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=2048,
        help="Hard upper bound for acoustic token decoding per attempt.",
    )
    parser.add_argument("--pause-seconds", type=float, default=0.45)
    parser.add_argument("--intro-pause-seconds", type=float, default=1.2)
    parser.add_argument("--outro-silence-seconds", type=float, default=1.5)
    parser.add_argument("--room-tone-dbfs", type=float, default=DEFAULT_ROOM_TONE_DBFS)
    parser.add_argument(
        "--natural-dialogue-policy",
        choices=("strict", "advisory"),
        default="strict",
        help="strict blocks written-style long turns; advisory supports old episodes.",
    )
    parser.add_argument("--max-line-attempts", type=int, default=3)
    parser.add_argument(
        "--expressive-candidates",
        type=int,
        default=2,
        help="Generate 2-3 alternatives for emotionally important lines.",
    )
    parser.add_argument("--regenerate-references", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    # The unattended profile intentionally avoids CustomVoice's unbounded,
    # stochastic instruction decode.  It is explicit so interactive runs keep
    # their expressive defaults while scheduled runs have a deterministic policy.
    if args.scheduled_safe:
        if args.backend == "custom":
            raise ValueError("--scheduled-safe cannot be combined with --backend custom")
        args.backend = "clone"
        args.expressive_candidates = 1
        args.max_line_attempts = 1
        args.temperature = min(args.temperature, 0.35)
        args.top_p = min(args.top_p, 0.85)
        args.max_new_tokens = min(args.max_new_tokens, 1024)

    episode_dir = args.episode_dir.resolve()
    script_path = episode_dir / "02-script.json"
    lines = load_script(script_path)
    dialogue_pacing = natural_dialogue_report(
        lines, policy=args.natural_dialogue_policy
    )
    backend = resolve_backend(args.backend, args.custom_voice_model)
    custom_speakers = {
        "女声·感性": args.female_custom_speaker,
        "男声·理性": args.male_custom_speaker,
    }
    evidence = load_evidence(episode_dir / "01-evidence.json")
    claim_report = validate_claims(lines, evidence)
    pronunciation_sensitive_lines = validate_pronunciation_fields(lines)
    editorial_review = load_editorial_review(
        episode_dir / "02-editorial-review.json",
        script_path,
        episode_dir / "01-evidence.json",
    )
    discussion_lengths = [
        len(str(line["text"]).strip())
        for line in lines[1:]
    ]
    prompts = voice_prompts(lines)
    plan = {
        "valid": True,
        "line_count": len(lines),
        "spoken_characters": sum(len(str(line["text"])) for line in lines),
        "recommended_character_range": [1500, 2800],
        "speakers": list(SPEAKERS),
        "synthesis_backend": backend,
        "scheduled_safe": args.scheduled_safe,
        "custom_voice_model": str(args.custom_voice_model),
        "custom_speakers": custom_speakers,
        "per_line_instruction_control": backend == "custom",
        "performances": [
            {
                "index": line["index"],
                "performance": validate_performance(line),
                "instruct": contextual_performance_instruct(
                    line, lines[position - 1] if position else None
                ),
            }
            for position, line in enumerate(lines)
        ],
        "natural_dialogue": dialogue_pacing,
        "candidate_strategy": {
            "expressive_candidates": args.expressive_candidates,
            "max_line_attempts": args.max_line_attempts,
            "expressive_line_indexes": [
                line["index"] for line in lines if is_expressive_line(line)
            ],
        },
        "conversation_timing": [
            {
                "after_line": line["index"],
                "before_line": lines[position + 1]["index"],
                "milliseconds": transition_after_ms(
                    line,
                    lines[position + 1],
                    round(args.pause_seconds * 1000),
                    round(args.intro_pause_seconds * 1000),
                ),
                "timing": validate_timing(line),
            }
            for position, line in enumerate(lines[:-1])
        ],
        "opening_intro": {
            "speaker": lines[0]["speaker"],
            "characters": len(str(lines[0]["text"]).strip()),
            "pause_seconds": args.intro_pause_seconds,
        },
        "opening_transition": {
            "speaker": lines[1]["speaker"],
            "move": lines[1]["move"],
        },
        "turn_pacing": {
            "minimum_characters": min(discussion_lengths),
            "maximum_characters": max(discussion_lengths),
            "short_turns": sum(
                length < STANDARD_TURN_MIN for length in discussion_lengths
            ),
            "standard_turns": sum(
                STANDARD_TURN_MIN <= length <= STANDARD_TURN_MAX
                for length in discussion_lengths
            ),
            "extended_turns": sum(
                STANDARD_TURN_MAX < length <= MAX_TURN_CHARACTERS
                for length in discussion_lengths
            ),
        },
        "discussion_moves": {
            "distinct": sorted(set(line["move"] for line in lines[1:])),
            "count": len(set(line["move"] for line in lines[1:])),
            "maximum_text_similarity": max(
                (
                    text_similarity(str(left["text"]), str(right["text"]))
                    for position, right in enumerate(lines[1:], start=1)
                    for left in lines[1:position]
                ),
                default=0.0,
            ),
        },
        "claim_types": claim_report,
        "pronunciation_sensitive_lines": pronunciation_sensitive_lines,
        "editorial_review": editorial_review,
        "ending": {
            "line_indexes": [line["index"] for line in lines[-4:]],
            "moves": [line["move"] for line in lines[-4:]],
            "outro_silence_seconds": args.outro_silence_seconds,
        },
        "episode_dir": str(episode_dir),
    }
    plan["recommended_character_range_passed"] = (
        MIN_SCRIPT_CHARACTERS
        <= plan["spoken_characters"]
        <= MAX_SCRIPT_CHARACTERS
    )
    if not plan["recommended_character_range_passed"]:
        raise ValueError(
            f"script must contain {MIN_SCRIPT_CHARACTERS}-{MAX_SCRIPT_CHARACTERS} "
            f"characters; got {plan['spoken_characters']}"
        )
    standard_turns = plan["turn_pacing"]["standard_turns"]
    if standard_turns * 2 < len(discussion_lengths):
        raise ValueError(
            "at least half of discussion turns must contain 40-120 characters; "
            f"found {standard_turns} of {len(discussion_lengths)}"
        )
    if args.pause_seconds < 0 or args.pause_seconds > 3:
        raise ValueError("--pause-seconds must be between 0 and 3")
    if args.intro_pause_seconds < 0.5 or args.intro_pause_seconds > 5:
        raise ValueError("--intro-pause-seconds must be between 0.5 and 5")
    if args.outro_silence_seconds < 0.5 or args.outro_silence_seconds > 5:
        raise ValueError("--outro-silence-seconds must be between 0.5 and 5")
    if not -90.0 <= args.room_tone_dbfs <= -40.0:
        raise ValueError("--room-tone-dbfs must be between -90 and -40")
    if args.max_line_attempts < 1 or args.max_line_attempts > 3:
        raise ValueError("--max-line-attempts must be between 1 and 3")
    if args.expressive_candidates < 1 or args.expressive_candidates > 3:
        raise ValueError("--expressive-candidates must be between 1 and 3")
    if args.temperature < 0 or args.temperature > 1.5:
        raise ValueError("--temperature must be between 0 and 1.5")
    if args.top_p <= 0 or args.top_p > 1:
        raise ValueError("--top-p must be greater than 0 and at most 1")
    if args.max_new_tokens < 128 or args.max_new_tokens > 8192:
        raise ValueError("--max-new-tokens must be between 128 and 8192")
    if args.validate_only:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    required_models = (
        (args.custom_voice_model,)
        if backend == "custom"
        else (args.voice_design_model, args.base_model)
    )
    for model_path in required_models:
        if not model_path.exists():
            raise FileNotFoundError(model_path)

    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    audio_dir = episode_dir / "audio"
    refs_dir = audio_dir / "references"
    audio_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)
    device, dtype = choose_device(torch)
    kwargs = model_kwargs(torch, device, dtype)

    reference_records: list[dict[str, Any]] = []
    clone_prompts: dict[str, Any] = {}
    synthesis_model: Any
    if backend == "clone":
        need_references = args.regenerate_references or any(
            not (refs_dir / f"{role_name(speaker)}.wav").exists()
            for speaker in SPEAKERS
        )
        if need_references:
            design_model = Qwen3TTSModel.from_pretrained(
                str(args.voice_design_model), **kwargs
            )
            for speaker in SPEAKERS:
                started = time.perf_counter()
                wavs, reference_rate = design_model.generate_voice_design(
                    text=REFERENCE_TEXTS[speaker],
                    language="Chinese",
                    instruct=prompts[speaker],
                )
                elapsed = time.perf_counter() - started
                output = refs_dir / f"{role_name(speaker)}.wav"
                sf.write(output, wavs[0], reference_rate)
                reference_records.append(
                    {
                        "speaker": speaker,
                        "path": str(output),
                        "text": REFERENCE_TEXTS[speaker],
                        "generation_seconds": round(elapsed, 3),
                        "duration_seconds": round(
                            len(wavs[0]) / reference_rate, 3
                        ),
                        "sample_rate": reference_rate,
                    }
                )
            del design_model
            clear_device_cache(torch)
        else:
            for speaker in SPEAKERS:
                output = refs_dir / f"{role_name(speaker)}.wav"
                reference_wav, reference_rate = sf.read(output)
                reference_records.append(
                    {
                        "speaker": speaker,
                        "path": str(output),
                        "text": REFERENCE_TEXTS[speaker],
                        "generation_seconds": 0.0,
                        "duration_seconds": round(
                            len(reference_wav) / reference_rate, 3
                        ),
                        "sample_rate": reference_rate,
                        "reused": True,
                    }
                )
        synthesis_model = Qwen3TTSModel.from_pretrained(str(args.base_model), **kwargs)
        for record in reference_records:
            clone_prompts[record["speaker"]] = (
                synthesis_model.create_voice_clone_prompt(
                    ref_audio=record["path"], ref_text=record["text"]
                )
            )
    else:
        synthesis_model = Qwen3TTSModel.from_pretrained(
            str(args.custom_voice_model), **kwargs
        )
        supported_speakers = synthesis_model.get_supported_speakers()
        if supported_speakers is not None:
            normalized_supported = {
                str(speaker).casefold() for speaker in supported_speakers
            }
            unknown_speakers = sorted(
                speaker
                for speaker in set(custom_speakers.values())
                if speaker.casefold() not in normalized_supported
            )
            if unknown_speakers:
                raise ValueError(
                    "unsupported CustomVoice speaker(s): "
                    + "、".join(unknown_speakers)
                )

    rendered: list[dict[str, Any]] = []
    line_wavs: list[Any] = []
    candidates_dir = audio_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    sample_rate: int | None = None
    total_synthesis = 0.0
    for position, line in enumerate(lines):
        spoken_text = str(line.get("tts_text", line["text"])).strip()
        performance = validate_performance(line)
        performance_instruct = contextual_performance_instruct(
            line, lines[position - 1] if position else None
        )
        line_target_rms_dbfs = target_line_rms_dbfs(line)
        if backend == "custom":
            generate = lambda: synthesis_model.generate_custom_voice(
                text=spoken_text,
                language="Chinese",
                speaker=custom_speakers[line["speaker"]],
                instruct=performance_instruct,
                do_sample=True,
                temperature=args.temperature,
                top_p=args.top_p,
                max_new_tokens=args.max_new_tokens,
                non_streaming_mode=True,
            )
        else:
            generate = lambda: synthesis_model.generate_voice_clone(
                text=spoken_text,
                language="Chinese",
                voice_clone_prompt=clone_prompts[line["speaker"]],
                do_sample=True,
                temperature=args.temperature,
                top_p=args.top_p,
                max_new_tokens=args.max_new_tokens,
                non_streaming_mode=True,
            )
        requested_candidates = (
            args.expressive_candidates if is_expressive_line(line) else 1
        )
        candidate_items: list[dict[str, Any]] = []
        for candidate_number in range(1, requested_candidates + 1):
            try:
                candidate_wav, candidate_rate, elapsed, attempts = (
                    synthesize_line_with_quality(
                        generate,
                        spoken_text,
                        args.max_line_attempts,
                        line_target_rms_dbfs,
                    )
                )
            except ValueError as exc:
                raise ValueError(
                    f"line {line['index']} candidate {candidate_number} {exc}"
                ) from exc
            quality = dict(attempts[-1]["after"])
            quality.update(prosody_metrics(candidate_wav, candidate_rate))
            quality["quality_issues"] = list(attempts[-1]["issues"])
            evaluation = score_candidate(quality, line, line_target_rms_dbfs)
            candidate_path = candidates_dir / (
                f"line-{line['index']:03d}-candidate-{candidate_number}.wav"
            )
            sf.write(candidate_path, candidate_wav, candidate_rate)
            candidate_items.append(
                {
                    "candidate": candidate_number,
                    "wav": candidate_wav,
                    "path": str(candidate_path),
                    "wav_sha256": sha256_file(candidate_path),
                    "sample_rate": candidate_rate,
                    "synthesis_seconds": round(elapsed, 3),
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                    "metrics": quality,
                    "evaluation": evaluation,
                }
            )
        selected, candidate_selection = select_best_candidate(candidate_items)
        wav = selected["wav"]
        current_rate = int(selected["sample_rate"])
        attempts = selected["attempts"]
        elapsed = sum(float(item["synthesis_seconds"]) for item in candidate_items)
        sample_rate = current_rate if sample_rate is None else sample_rate
        if current_rate != sample_rate:
            raise ValueError(
                f"sample-rate changed from {sample_rate} to {current_rate}"
            )
        output = audio_dir / (
            f"line-{line['index']:03d}-{role_name(line['speaker'])}.wav"
        )
        sf.write(output, wav, current_rate)
        wav_sha256 = sha256_file(output)
        line_wavs.append(wav)
        total_synthesis += elapsed
        rendered.append(
            {
                "index": line["index"],
                "speaker": line["speaker"],
                "path": str(output),
                "wav_sha256": wav_sha256,
                "synthesis_seconds": round(elapsed, 3),
                "attempt_count": len(attempts),
                "attempts": attempts,
                "audio_duration_seconds": round(len(wav) / current_rate, 3),
                "sample_rate": current_rate,
                "quality": attempts[-1]["after"],
                "quality_issues": attempts[-1]["issues"],
                "advanced_metrics": {
                    key: selected["metrics"][key]
                    for key in (
                        "voiced_dynamic_range_db",
                        "energy_slope_db_per_second",
                        "pause_count",
                        "pitch_median_hz",
                        "pitch_range_hz",
                    )
                },
                "candidate_selection": candidate_selection,
                "target_active_rms_dbfs": line_target_rms_dbfs,
                "performance": performance,
                "performance_instruct": performance_instruct,
                "instruction_applied": backend == "custom",
                "pronunciation_sensitive": line["index"]
                in pronunciation_sensitive_lines,
            }
        )

    assert sample_rate is not None
    combined, transition_records = assemble_conversation(
        line_wavs,
        lines,
        sample_rate,
        args.pause_seconds,
        args.intro_pause_seconds,
        args.outro_silence_seconds,
        args.room_tone_dbfs,
    )
    combined, mastering_report = master_episode(
        combined,
        sample_rate,
        target_active_rms_dbfs=MASTER_TARGET_ACTIVE_RMS_DBFS,
    )
    full_audio = audio_dir / "full-episode.wav"
    sf.write(full_audio, combined, sample_rate)
    audio_duration = len(combined) / sample_rate
    timing = {
        "strategy": (
            "custom-voice-with-per-line-instructions"
            if backend == "custom"
            else "voice-design-references-then-voice-clone"
        ),
        "backend": backend,
        "scheduled_safe": args.scheduled_safe,
        "voice_design_model": str(args.voice_design_model),
        "voice_clone_model": str(args.base_model),
        "custom_voice_model": str(args.custom_voice_model),
        "custom_speakers": custom_speakers,
        "per_line_instruction_control": backend == "custom",
        "sampling": {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_new_tokens": args.max_new_tokens,
            "max_line_attempts": args.max_line_attempts,
            "expressive_candidates": args.expressive_candidates,
        },
        "device": device,
        "dtype": str(dtype),
        "python_executable": sys.executable,
        "package_versions": {
            name: _package_version(name)
            for name in ("torch", "qwen-tts", "torchaudio", "soundfile")
        },
        "reliability_profile": "scheduled-safe" if args.scheduled_safe else "interactive",
        "sample_rate": sample_rate,
        "line_count": len(rendered),
        "reference_generation_seconds": round(
            sum(record["generation_seconds"] for record in reference_records), 3
        ),
        "total_synthesis_seconds": round(total_synthesis, 3),
        "audio_duration_seconds": round(audio_duration, 3),
        "inter_line_pause_seconds": args.pause_seconds,
        "intro_pause_seconds": args.intro_pause_seconds,
        "outro_silence_seconds": args.outro_silence_seconds,
        "room_tone_dbfs": args.room_tone_dbfs,
        "transitions": transition_records,
        "mastering": mastering_report,
        "real_time_factor": round(total_synthesis / audio_duration, 3),
        "combined_audio_path": str(full_audio),
        "references": reference_records,
        "lines": rendered,
    }
    automated_passed = all(not line["quality_issues"] for line in rendered)
    script_sha256 = sha256_file(script_path)
    previous_rejected_hashes: dict[int, set[str]] = {}
    audio_qc_path = episode_dir / "03-audio-qc.json"
    if audio_qc_path.exists():
        try:
            previous_qc = json.loads(audio_qc_path.read_text(encoding="utf-8"))
            if previous_qc.get("script_sha256") == script_sha256:
                for old_line in previous_qc.get("lines", []):
                    review = old_line.get("manual_review", {})
                    hashes = set(review.get("rejected_audio_hashes", []))
                    if review.get("rejected_sha256"):
                        hashes.add(review["rejected_sha256"])
                    previous_rejected_hashes[int(old_line["index"])] = hashes
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            previous_rejected_hashes = {}
    audio_qc = {
        "passed": False,
        "automated_passed": automated_passed,
        "manual_review_passed": False,
        "script_sha256": script_sha256,
        "line_count": len(rendered),
        "target_rms_dbfs": TARGET_RMS_DBFS,
        "mastering": mastering_report,
        "limits": {
            "duration_seconds": [MIN_AUDIO_DURATION, MAX_AUDIO_DURATION],
            "minimum_peak": MIN_PEAK,
            "rms_dbfs": [MIN_RMS_DBFS, MAX_RMS_DBFS],
            "maximum_peak": MAX_PEAK,
            "maximum_clipping_ratio": MAX_CLIPPING_RATIO,
            "maximum_silence_ratio": MAX_SILENCE_RATIO,
            "spoken_characters_per_second": [MIN_SPEECH_RATE, MAX_SPEECH_RATE],
        },
        "pronunciation_sensitive_lines": pronunciation_sensitive_lines,
        "lines": [
            {
                "index": line["index"],
                "speaker": line["speaker"],
                "path": str(Path(line["path"]).relative_to(episode_dir)),
                "wav_sha256": line["wav_sha256"],
                "attempt_count": line["attempt_count"],
                "attempts": line["attempts"],
                "metrics": line["quality"],
                "advanced_metrics": line["advanced_metrics"],
                "candidate_selection": line["candidate_selection"],
                "issues": line["quality_issues"],
                "target_active_rms_dbfs": line["target_active_rms_dbfs"],
                "performance": line["performance"],
                "performance_instruct": line["performance_instruct"],
                "instruction_applied": line["instruction_applied"],
                "pronunciation_sensitive": line["pronunciation_sensitive"],
                "manual_review": {
                    "status": "pending",
                    "reviewed_at": None,
                    "notes": "",
                    "ratings": {
                        "emotion_match": None,
                        "context_response": None,
                        "natural_pause": None,
                        "emphasis_accuracy": None,
                    },
                    "rejected_audio_hashes": sorted(
                        previous_rejected_hashes.get(line["index"], set())
                    ),
                },
            }
            for line in rendered
        ],
    }
    (episode_dir / "03-timing.json").write_text(
        json.dumps(timing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audio_qc_path.write_text(
        json.dumps(audio_qc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_prompt_notes(
        episode_dir / "03-voice-prompts.md",
        prompts,
        args.voice_design_model,
        args.base_model,
        args.custom_voice_model,
        backend,
        custom_speakers,
    )
    print(json.dumps(timing, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
