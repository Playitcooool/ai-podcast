from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "synthesize_episode.py"
)


def load_synthesis_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "emotional_podcast_natural_dialogue",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synth() -> ModuleType:
    return load_synthesis_module()


def dialogue_line(
    index: int,
    characters: int,
    *,
    pacing_exception: str | None = None,
) -> dict[str, object]:
    line: dict[str, object] = {
        "index": index,
        "speaker": "女声·感性" if index % 2 else "男声·理性",
        "segment": "讨论",
        "move": "深化" if index % 2 else "承接",
        "claim_type": "opinion",
        "text": "话" * characters,
    }
    if pacing_exception is not None:
        line["pacing_exception"] = pacing_exception
    return line


def full_script(*discussion_lines: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "index": 0,
            "speaker": "女声·感性",
            "segment": "导入语",
            "text": "这是一段不参与普通讨论回合长度统计的节目导入语。",
        },
        *discussion_lines,
    ]


def test_natural_dialogue_report_estimates_about_4_6_characters_per_second(
    synth: ModuleType,
) -> None:
    report = synth.natural_dialogue_report(
        full_script(dialogue_line(1, 46)),
        policy="strict",
    )
    turn = report["turns"][0]
    assert turn["characters"] == 46
    assert turn["estimated_seconds"] == pytest.approx(10.0, abs=0.1)
    assert report["target_turn_characters"] == 72
    assert report["hard_turn_characters"] == 96
    assert report["passed"] is True


@pytest.mark.parametrize("characters", [8, 46, 72, 96])
def test_strict_policy_accepts_turns_through_96_characters(
    synth: ModuleType,
    characters: int,
) -> None:
    report = synth.natural_dialogue_report(
        full_script(dialogue_line(1, characters)),
        policy="strict",
    )
    assert report["passed"] is True


def test_97_to_120_characters_requires_nonempty_pacing_exception(
    synth: ModuleType,
) -> None:
    with pytest.raises(ValueError, match="pacing_exception|97|96"):
        synth.natural_dialogue_report(
            full_script(dialogue_line(1, 97)),
            policy="strict",
        )

    report = synth.natural_dialogue_report(
        full_script(
            dialogue_line(
                1,
                97,
                pacing_exception="事实与限定条件不能再拆，否则会失去逻辑关系。",
            )
        ),
        policy="strict",
    )
    assert report["passed"] is True
    assert report["turns"][0]["pacing_exception"]


def test_pacing_exception_cannot_bypass_120_character_ceiling(
    synth: ModuleType,
) -> None:
    with pytest.raises(ValueError, match="120|characters|字"):
        synth.natural_dialogue_report(
            full_script(
                dialogue_line(
                    1,
                    121,
                    pacing_exception="即使有理由也不能超过最终上限。",
                )
            ),
            policy="strict",
        )


def test_strict_policy_allows_at_most_two_long_turns(
    synth: ModuleType,
) -> None:
    two_long = synth.natural_dialogue_report(
        full_script(dialogue_line(1, 73), dialogue_line(2, 80)),
        policy="strict",
    )
    assert two_long["long_turns"] == 2
    assert two_long["passed"] is True

    with pytest.raises(ValueError, match="long|长回合|2"):
        synth.natural_dialogue_report(
            full_script(
                dialogue_line(1, 73),
                dialogue_line(2, 80),
                dialogue_line(3, 90),
            ),
            policy="strict",
        )


def test_advisory_policy_reports_legacy_problems_without_raising(
    synth: ModuleType,
) -> None:
    legacy_lines = [
        dialogue_line(1, 97),
        dialogue_line(2, 105),
        dialogue_line(3, 121),
    ]
    report = synth.natural_dialogue_report(
        full_script(*legacy_lines),
        policy="advisory",
    )
    assert report["policy"] == "advisory"
    assert report["passed"] is False
    assert report["long_turns"] == 3
    assert report["violations"]


def test_natural_dialogue_report_rejects_unknown_policy(
    synth: ModuleType,
) -> None:
    with pytest.raises(ValueError, match="policy"):
        synth.natural_dialogue_report(
            full_script(dialogue_line(1, 46)),
            policy="ignore",
        )


def performance() -> dict[str, object]:
    return {
        "emotion": "克制的担忧",
        "intensity": 0.55,
        "pace": "slightly_slow",
        "energy": "medium_low",
        "pitch": "natural",
        "ending": "rising",
        "key_emphasis": ["真的安全吗"],
    }


def test_contextual_instruct_adds_previous_turn_response_and_move_direction(
    synth: ModuleType,
) -> None:
    previous = {
        "index": 4,
        "speaker": "男声·理性",
        "segment": "讨论",
        "move": "区分",
        "claim_type": "inference",
        "text": "限制风险，不等于替孩子决定一切。",
    }
    current = {
        "index": 5,
        "speaker": "女声·感性",
        "segment": "讨论",
        "move": "追问",
        "claim_type": "question",
        "text": "可如果风险来得很快，这样真的安全吗？",
        "performance": performance(),
        "voice_prompt": "真诚追问，不要质问。",
    }
    base = synth.build_performance_instruct(current)

    contextual = synth.contextual_performance_instruct(current, previous)

    assert base in contextual
    assert "上一句" in contextual or "承接" in contextual or "回应" in contextual
    assert "追问" in contextual or "问题" in contextual or "提问" in contextual
    assert "真诚追问，不要质问" in contextual


@pytest.mark.parametrize(
    ("move", "claim_type", "expected_words"),
    [
        ("修正", "opinion", ("修正", "停顿")),
        ("新事实", "fact", ("事实", "清楚")),
        ("反例", "example", ("反例", "转折")),
        ("综合", "inference", ("综合", "收束")),
    ],
)
def test_contextual_instruct_varies_with_dialogue_function(
    synth: ModuleType,
    move: str,
    claim_type: str,
    expected_words: tuple[str, str],
) -> None:
    previous = {
        "index": 1,
        "segment": "讨论",
        "move": "承接",
        "claim_type": "opinion",
        "text": "这是上一位主持人的观点。",
    }
    current = {
        "index": 2,
        "segment": "讨论",
        "move": move,
        "claim_type": claim_type,
        "text": "这是当前主持人需要自然说出的回应。",
        "performance": {
            "emotion": "专注",
            "intensity": 0.45,
            "pace": "natural",
            "energy": "medium",
            "pitch": "natural",
            "ending": "level",
            "key_emphasis": [],
        },
    }
    instruct = synth.contextual_performance_instruct(current, previous)
    assert any(word in instruct for word in expected_words)


def test_first_line_does_not_invent_previous_context(
    synth: ModuleType,
) -> None:
    first = {
        "index": 1,
        "segment": "导入语",
        "text": "今天我们从一个真实生活场景开始。",
        "voice_prompt": "平静开场。",
    }
    contextual = synth.contextual_performance_instruct(first, None)
    assert contextual == synth.build_performance_instruct(first)
    assert "上一句" not in contextual
    assert "回应前一位" not in contextual


def test_main_declares_strict_natural_dialogue_policy_as_default(
    synth: ModuleType,
) -> None:
    source = inspect.getsource(synth.main)
    assert "--natural-dialogue-policy" in source
    assert 'default="strict"' in source
