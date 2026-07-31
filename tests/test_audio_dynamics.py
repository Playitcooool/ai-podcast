from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "synthesize_episode.py"
)


def load_synthesis_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "emotional_podcast_audio_dynamics",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synth() -> ModuleType:
    # Importing the synthesis module must not import qwen_tts or load weights.
    return load_synthesis_module()


def line(
    *,
    energy: str = "medium",
    segment: str = "讨论",
    ending: str = "level",
) -> dict[str, object]:
    return {
        "index": 1,
        "speaker": "女声·感性",
        "segment": segment,
        "text": "这是一句用于检查响度层次的自然口语。",
        "performance": {
            "emotion": "专注",
            "intensity": 0.45,
            "pace": "natural",
            "energy": energy,
            "pitch": "natural",
            "ending": ending,
            "key_emphasis": [],
        },
    }


def test_target_line_rms_preserves_two_to_four_db_energy_range(
    synth: ModuleType,
) -> None:
    low = synth.target_line_rms_dbfs(line(energy="low"))
    medium = synth.target_line_rms_dbfs(line(energy="medium"))
    high = synth.target_line_rms_dbfs(line(energy="high"))

    assert low < medium < high
    assert 2.0 <= high - low <= 4.0
    assert -22.0 <= medium <= -20.0


def test_intro_and_settling_lines_are_quieter_than_neutral_discussion(
    synth: ModuleType,
) -> None:
    neutral = synth.target_line_rms_dbfs(line())
    intro = synth.target_line_rms_dbfs(line(segment="导入语"))
    settling = synth.target_line_rms_dbfs(
        line(segment="结尾", ending="settling")
    )

    assert 0.5 <= neutral - intro <= 4.0
    assert 0.4 <= neutral - settling <= 4.0


def dbfs(samples: np.ndarray) -> float:
    samples64 = np.asarray(samples, dtype=np.float64)
    rms = math.sqrt(float(np.mean(np.square(samples64))))
    return 20.0 * math.log10(max(rms, 1e-12))


def alternating(count: int, amplitude: float) -> np.ndarray:
    values = np.full(count, amplitude, dtype=np.float32)
    values[1::2] *= -1
    return values


def test_trim_audio_preserves_soft_breath_and_natural_edge_padding(
    synth: ModuleType,
) -> None:
    sample_rate = 1000
    rng = np.random.default_rng(20260731)
    leading_silence = np.zeros(500, dtype=np.float32)
    inhale = rng.normal(0.0, 0.00045, 150).astype(np.float32)
    speech = alternating(400, 0.08)
    exhale = rng.normal(0.0, 0.00040, 180).astype(np.float32)
    trailing_silence = np.zeros(600, dtype=np.float32)
    raw = np.concatenate(
        (leading_silence, inhale, speech, exhale, trailing_silence)
    )

    trimmed = synth.trim_audio_preserving_breath(raw, sample_rate)

    assert isinstance(trimmed, np.ndarray)
    assert len(trimmed) < len(raw) - 400
    speech_positions = np.flatnonzero(np.abs(trimmed) > 0.02)
    assert speech_positions.size
    speech_start = int(speech_positions[0])
    speech_end = int(speech_positions[-1])
    assert speech_start >= 170  # approximately 180 ms leading context
    assert len(trimmed) - speech_end - 1 >= 210  # approximately 220 ms tail
    # The sub-threshold inhale and exhale must survive, not just digital silence.
    assert np.any(np.abs(trimmed[speech_start - 150 : speech_start]) > 0)
    assert np.any(np.abs(trimmed[speech_end + 1 : speech_end + 181]) > 0)


def test_normalize_audio_uses_active_speech_not_edge_silence(
    synth: ModuleType,
) -> None:
    sample_rate = 1000
    speech = alternating(1000, 0.03)
    short_edges = np.concatenate(
        (np.zeros(300, dtype=np.float32), speech, np.zeros(300, dtype=np.float32))
    )
    long_edges = np.concatenate(
        (
            np.zeros(2000, dtype=np.float32),
            speech,
            np.zeros(2000, dtype=np.float32),
        )
    )

    normalized_short = synth.normalize_audio(
        short_edges,
        sample_rate,
        target_rms_dbfs=-20.0,
    )
    normalized_long = synth.normalize_audio(
        long_edges,
        sample_rate,
        target_rms_dbfs=-20.0,
    )
    active_short = normalized_short[np.abs(normalized_short) > 0.01]
    active_long = normalized_long[np.abs(normalized_long) > 0.01]

    assert dbfs(active_short) == pytest.approx(-20.0, abs=0.6)
    assert dbfs(active_long) == pytest.approx(-20.0, abs=0.6)
    assert dbfs(active_short) == pytest.approx(dbfs(active_long), abs=0.2)


def test_normalize_audio_keeps_peak_protection(
    synth: ModuleType,
) -> None:
    audio = alternating(1000, 0.9)
    normalized = synth.normalize_audio(
        audio,
        1000,
        target_rms_dbfs=-1.0,
    )
    assert float(np.max(np.abs(normalized))) <= synth.MAX_PEAK + 1e-6


def test_master_episode_is_gentle_documented_and_clip_safe(
    synth: ModuleType,
) -> None:
    sample_rate = 8000
    rng = np.random.default_rng(31)
    room_tone = rng.normal(
        0.0,
        10 ** (-54.0 / 20.0),
        sample_rate // 2,
    ).astype(np.float32)
    time_axis = np.arange(sample_rate * 2, dtype=np.float32) / sample_rate
    speech = (
        0.075 * np.sin(2 * np.pi * 180 * time_axis)
        + 0.025 * np.sin(2 * np.pi * 3000 * time_axis)
        + 0.008
    ).astype(np.float32)
    episode = np.concatenate((room_tone, speech, room_tone))

    mastered, report = synth.master_episode(
        episode,
        sample_rate,
        target_active_rms_dbfs=-19.0,
    )

    assert isinstance(mastered, np.ndarray)
    assert mastered.shape == episode.shape
    assert np.isfinite(mastered).all()
    assert float(np.max(np.abs(mastered))) <= synth.MAX_PEAK + 1e-6
    assert float(np.mean(np.abs(mastered) >= 0.999)) == 0.0

    assert set(report) >= {"before", "after"}
    parameters = json.dumps(
        {key: value for key, value in report.items() if key not in {"before", "after"}},
        ensure_ascii=False,
    ).lower()
    for expected in ("high", "deess", "compress", "gain", "peak"):
        assert expected in parameters
    assert report["before"]
    assert report["after"]

    # Mastering may apply a small programme gain, but must not pull room tone
    # toward speech level.
    before_room_dbfs = dbfs(episode[: sample_rate // 2])
    after_room_dbfs = dbfs(mastered[: sample_rate // 2])
    assert after_room_dbfs <= before_room_dbfs + 3.0
    assert after_room_dbfs <= -48.0

    mastered_speech = mastered[sample_rate // 2 : -sample_rate // 2]
    assert dbfs(mastered_speech) == pytest.approx(-19.0, abs=1.5)
    assert abs(float(np.mean(mastered_speech))) < abs(float(np.mean(speech)))


def test_master_episode_rejects_empty_or_nonfinite_audio(
    synth: ModuleType,
) -> None:
    with pytest.raises(ValueError, match="empty|non-finite|finite"):
        synth.master_episode(np.zeros(0, dtype=np.float32), 8000)
    with pytest.raises(ValueError, match="non-finite|finite|invalid"):
        synth.master_episode(
            np.asarray([0.0, np.nan], dtype=np.float32),
            8000,
        )
