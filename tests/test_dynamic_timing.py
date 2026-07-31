from __future__ import annotations

import importlib.util
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
        "emotional_podcast_dynamic_timing",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synth() -> ModuleType:
    # The production module imports model dependencies only inside main().
    return load_synthesis_module()


@pytest.mark.parametrize(
    ("timing", "expected"),
    [
        (None, {}),
        ({}, {}),
        ({"pause_after_ms": 0}, {"pause_after_ms": 0}),
        ({"pause_after_ms": 3000}, {"pause_after_ms": 3000}),
        ({"overlap_next_ms": 0}, {"overlap_next_ms": 0}),
        ({"overlap_next_ms": 150}, {"overlap_next_ms": 150}),
    ],
)
def test_validate_timing_accepts_supported_boundaries(
    synth: ModuleType,
    timing: dict[str, int] | None,
    expected: dict[str, int],
) -> None:
    line: dict[str, object] = {"index": 1, "text": "测试台词"}
    if timing is not None:
        line["timing"] = timing
    assert synth.validate_timing(line) == expected


def test_validate_timing_rejects_pause_and_overlap_together(
    synth: ModuleType,
) -> None:
    line = {
        "index": 1,
        "text": "测试台词",
        "timing": {"pause_after_ms": 200, "overlap_next_ms": 50},
    }
    with pytest.raises(ValueError, match="mutually exclusive|互斥|同时"):
        synth.validate_timing(line)


@pytest.mark.parametrize(
    "timing",
    [
        {"pause_after_ms": -1},
        {"pause_after_ms": 3001},
        {"overlap_next_ms": -1},
        {"overlap_next_ms": 151},
        {"overlap_next_ms": True},
        {"unknown": 100},
    ],
)
def test_validate_timing_rejects_invalid_values(
    synth: ModuleType,
    timing: dict[str, object],
) -> None:
    line = {"index": 1, "text": "测试台词", "timing": timing}
    with pytest.raises(ValueError, match="timing|pause_after_ms|overlap_next_ms"):
        synth.validate_timing(line)


def test_explicit_timing_has_priority_over_automatic_rhythm(
    synth: ModuleType,
) -> None:
    next_line = {"index": 2, "segment": "讨论", "text": "下一句"}
    intro = {
        "index": 1,
        "segment": "导入语",
        "text": "这是一段导入语。",
        "timing": {"pause_after_ms": 275},
    }
    short_reaction = {
        "index": 3,
        "segment": "讨论",
        "move": "修正",
        "text": "等一下。",
        "timing": {"overlap_next_ms": 80},
    }

    assert synth.transition_after_ms(intro, next_line, 450, 1200) == 275
    assert (
        synth.transition_after_ms(short_reaction, next_line, 450, 1200)
        == -80
    )


def test_transition_policy_gives_dialogue_functions_distinct_rhythms(
    synth: ModuleType,
) -> None:
    next_line = {"index": 99, "segment": "讨论", "text": "下一句"}
    intro = {
        "index": 1,
        "segment": "导入语",
        "text": "这是一段足够长的节目导入语。",
    }
    short_reaction = {
        "index": 2,
        "segment": "讨论",
        "move": "承接",
        "text": "嗯，我明白。",
    }
    ordinary = {
        "index": 3,
        "segment": "讨论",
        "move": "深化",
        "text": "这是一段长度正常、用于继续展开观点的普通讨论台词。",
    }
    revision = {
        "index": 4,
        "segment": "讨论",
        "move": "修正",
        "text": "等一下，我需要修正刚才的判断，再换一个角度看。",
    }
    ending = {
        "index": 5,
        "segment": "结尾",
        "move": "收束",
        "text": "还有一些问题，需要留给具体情境继续回答。",
    }

    intro_ms = synth.transition_after_ms(intro, next_line, 450, 1200)
    short_ms = synth.transition_after_ms(
        short_reaction, next_line, 450, 1200
    )
    ordinary_ms = synth.transition_after_ms(ordinary, next_line, 450, 1200)
    revision_ms = synth.transition_after_ms(revision, next_line, 450, 1200)
    ending_ms = synth.transition_after_ms(ending, next_line, 450, 1200)

    assert intro_ms == 1200
    assert 120 <= short_ms <= 220
    assert ordinary_ms == 450
    assert 450 <= revision_ms <= 700
    assert 600 <= ending_ms <= 1200
    assert len({intro_ms, short_ms, ordinary_ms, revision_ms, ending_ms}) >= 4


def test_ordinary_transitions_are_not_all_fixed_450ms(
    synth: ModuleType,
) -> None:
    lines = [
        {
            "index": 1,
            "segment": "讨论",
            "move": "承接",
            "text": "嗯，对。",
        },
        {
            "index": 2,
            "segment": "讨论",
            "move": "深化",
            "text": "这是一段长度正常、用于承接并展开观点的普通讨论台词。",
        },
        {
            "index": 3,
            "segment": "讨论",
            "move": "修正",
            "text": "等一下，我需要修正刚才的判断，再换一个角度看。",
        },
        {
            "index": 4,
            "segment": "结尾",
            "move": "收束",
            "text": "仍然没有解决的问题，要留给具体情境。",
        },
        {"index": 5, "segment": "结尾", "move": "邀请", "text": "你怎么看？"},
    ]
    durations = [
        synth.transition_after_ms(line, lines[position + 1], 450, 1200)
        for position, line in enumerate(lines[:-1])
    ]
    assert len(set(durations)) > 1
    assert any(duration != 450 for duration in durations)


def rms_dbfs(samples: np.ndarray) -> float:
    rms = math.sqrt(float(np.mean(np.square(samples.astype(np.float64)))))
    return 20.0 * math.log10(rms)


def test_room_tone_is_reproducible_nonzero_and_very_quiet(
    synth: ModuleType,
) -> None:
    first = synth.make_room_tone(48000, -54.0, seed=20260731)
    again = synth.make_room_tone(48000, -54.0, seed=20260731)
    different_seed = synth.make_room_tone(48000, -54.0, seed=20260732)

    assert isinstance(first, np.ndarray)
    assert first.shape == (48000,)
    np.testing.assert_array_equal(first, again)
    assert not np.array_equal(first, different_seed)
    assert np.any(first != 0)
    assert np.max(np.abs(first)) < 0.02
    assert -55.0 <= rms_dbfs(first) <= -53.0


def test_make_room_tone_supports_an_empty_transition(
    synth: ModuleType,
) -> None:
    tone = synth.make_room_tone(0, -54.0, seed=1)
    assert isinstance(tone, np.ndarray)
    assert tone.shape == (0,)


def transition_ms(record: dict[str, object]) -> int:
    assert "milliseconds" in record
    return int(record["milliseconds"])


def test_assemble_conversation_handles_pause_overlap_and_outro(
    synth: ModuleType,
) -> None:
    # A 1 kHz sample rate makes every millisecond exactly one sample.
    sample_rate = 1000
    wavs = [
        np.full(100, 0.10, dtype=np.float32),
        np.full(100, 0.20, dtype=np.float32),
        np.full(100, 0.30, dtype=np.float32),
        np.full(100, 0.40, dtype=np.float32),
    ]
    lines = [
        {
            "index": 1,
            "segment": "导入语",
            "text": "导入",
            "timing": {"pause_after_ms": 100},
        },
        {
            "index": 2,
            "segment": "讨论",
            "move": "承接",
            "text": "短反应",
            "timing": {"overlap_next_ms": 50},
        },
        {
            "index": 3,
            "segment": "讨论",
            "move": "深化",
            "text": "这是一段超过二十个字的普通承接台词，因此应该使用配置的默认停顿。",
        },
        {
            "index": 4,
            "segment": "结尾",
            "move": "邀请",
            "text": "最后一个问题？",
        },
    ]

    combined, records = synth.assemble_conversation(
        wavs=wavs,
        lines=lines,
        sample_rate=sample_rate,
        default_pause_seconds=0.45,
        intro_pause_seconds=1.2,
        outro_seconds=0.2,
        room_tone_dbfs=-54.0,
    )

    # 400 speech + 100 explicit pause - 50 overlap + 450 default + 200 outro.
    assert len(combined) == 1100
    assert len(records) == 4
    assert [transition_ms(record) for record in records] == [
        100,
        -50,
        450,
        200,
    ]
    assert [record["after_line"] for record in records] == [1, 2, 3, 4]
    assert records[0]["kind"] == "room_tone_pause"
    assert records[1]["kind"] == "crossfade_overlap"
    assert records[2]["kind"] == "room_tone_pause"
    assert records[3]["kind"] == "outro_room_tone"

    # Positive gaps use subtle room tone rather than exact digital zero.
    first_pause = combined[100:200]
    assert np.any(first_pause != 0)
    assert np.max(np.abs(first_pause)) < 0.02
    # During overlap, both adjacent speakers are present.
    overlap_start = 200 + 100 - 50
    assert np.all(combined[overlap_start + 1 : overlap_start + 50] > 0.20)


def test_assemble_conversation_rejects_shape_mismatches(
    synth: ModuleType,
) -> None:
    with pytest.raises(ValueError, match="wavs|lines|length|数量"):
        synth.assemble_conversation(
            wavs=[np.ones(10, dtype=np.float32)],
            lines=[],
            sample_rate=1000,
            default_pause_seconds=0.45,
            intro_pause_seconds=1.2,
            outro_seconds=0.2,
            room_tone_dbfs=-54.0,
        )
