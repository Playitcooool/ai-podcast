from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "synthesize_episode.py"
)
FIXTURE_EPISODE = Path(
    Path(__file__).resolve().parent / "fixtures" / "episode"
)


def load_synthesis_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "emotional_podcast_synthesize_episode",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synth() -> ModuleType:
    # qwen_tts and torch are imported inside main(), so importing the production
    # module itself must never load model code or weights.
    return load_synthesis_module()


@pytest.mark.parametrize(
    ("requested", "custom_exists", "expected"),
    [
        ("auto", True, "custom"),
        ("auto", False, "clone"),
        ("custom", True, "custom"),
        ("clone", True, "clone"),
        ("clone", False, "clone"),
    ],
)
def test_resolve_backend(
    synth: ModuleType,
    tmp_path: Path,
    requested: str,
    custom_exists: bool,
    expected: str,
) -> None:
    custom_model = tmp_path / "custom-model"
    if custom_exists:
        custom_model.mkdir()
    assert synth.resolve_backend(requested, custom_model) == expected


def test_resolve_backend_rejects_missing_explicit_custom(
    synth: ModuleType,
    tmp_path: Path,
) -> None:
    with pytest.raises((FileNotFoundError, ValueError), match="CustomVoice|custom"):
        synth.resolve_backend("custom", tmp_path / "missing-custom-model")


def test_resolve_backend_rejects_unknown_value(
    synth: ModuleType,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="backend"):
        synth.resolve_backend("other", tmp_path)


def complete_performance() -> dict[str, object]:
    return {
        "emotion": "担忧",
        "intensity": 0.55,
        "pace": "slightly_slow",
        "energy": "medium_low",
        "pitch": "slightly_high",
        "ending": "rising",
        "key_emphasis": ["多限制一点", "拿自己去试错"],
    }


def performance_line(**overrides: object) -> dict[str, object]:
    line: dict[str, object] = {
        "index": 5,
        "text": "那是不是宁可多限制一点，也不要让孩子拿自己去试错？",
        "performance": complete_performance(),
    }
    line.update(overrides)
    return line


def test_validate_performance_accepts_and_normalizes_complete_structure(
    synth: ModuleType,
) -> None:
    assert synth.validate_performance(performance_line()) == complete_performance()


def test_validate_performance_supplies_all_fields_for_legacy_line(
    synth: ModuleType,
) -> None:
    normalized = synth.validate_performance(
        {"index": 1, "text": "旧脚本台词", "voice_prompt": "克制、自然。"}
    )
    assert set(normalized) == {
        "emotion",
        "intensity",
        "pace",
        "energy",
        "pitch",
        "ending",
        "key_emphasis",
    }
    assert 0.0 <= normalized["intensity"] <= 1.0


@pytest.mark.parametrize("intensity", [-0.01, 1.01, "not-a-number", None])
def test_validate_performance_rejects_intensity_outside_zero_to_one(
    synth: ModuleType,
    intensity: object,
) -> None:
    performance = complete_performance()
    performance["intensity"] = intensity
    with pytest.raises(ValueError, match="intensity"):
        synth.validate_performance(
            performance_line(performance=performance)
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("emotion", ""),
        ("pace", "very_slow"),
        ("energy", "explosive"),
        ("pitch", "slightly_rising"),
        ("ending", "genuine_question"),
        ("key_emphasis", "重点"),
        ("key_emphasis", ["一", "二", "三", "四"]),
    ],
)
def test_validate_performance_rejects_invalid_structured_fields(
    synth: ModuleType,
    field: str,
    value: object,
) -> None:
    performance = complete_performance()
    performance[field] = value
    with pytest.raises(ValueError, match=field):
        synth.validate_performance(
            performance_line(performance=performance)
        )


def test_validate_performance_requires_emphasis_to_exist_in_spoken_text(
    synth: ModuleType,
) -> None:
    performance = complete_performance()
    performance["key_emphasis"] = ["台词中不存在"]
    with pytest.raises(ValueError, match="emphasis|key_emphasis"):
        synth.validate_performance(
            performance_line(performance=performance)
        )


def test_build_performance_instruct_translates_structure_to_executable_chinese(
    synth: ModuleType,
) -> None:
    line = performance_line(
        voice_prompt="真诚，不要把担心说成无知。",
    )

    instruct = synth.build_performance_instruct(line)

    assert "担忧" in instruct
    assert "语速略慢" in instruct
    assert "能量稍低" in instruct
    assert "音高略高" in instruct
    assert "句尾自然上扬" in instruct
    assert "多限制一点" in instruct
    assert "拿自己去试错" in instruct
    assert "真诚，不要把担心说成无知" in instruct
    # The model receives a Chinese performance direction, not raw enum/debug data.
    assert "slightly_slow" not in instruct
    assert "medium_low" not in instruct


def test_build_performance_instruct_supports_legacy_voice_prompt(
    synth: ModuleType,
) -> None:
    instruct = synth.build_performance_instruct(
        {
            "index": 9,
            "text": "等一下，我得修正一下。",
            "voice_prompt": "短促、自然，留出一点思考停顿。",
        }
    )
    assert "短促、自然，留出一点思考停顿" in instruct
    assert "不播报" in instruct


def test_role_personas_are_not_overridden_by_first_line_voice_prompt(
    synth: ModuleType,
) -> None:
    lines = [
        {
            "speaker": "女声·感性",
            "voice_prompt": "这是女声第一句的临时情绪，不是角色 persona。",
        },
        {
            "speaker": "男声·理性",
            "voice_prompt": "这是男声第一句的临时情绪，不是角色 persona。",
        },
    ]
    personas = synth.voice_prompts(lines)
    assert personas == synth.DEFAULT_PROMPTS
    assert "临时情绪" not in personas["女声·感性"]
    assert "临时情绪" not in personas["男声·理性"]


def test_custom_speaker_mapping_is_stable(synth: ModuleType) -> None:
    assert synth.CUSTOM_SPEAKERS == {
        "女声·感性": "Serena",
        "男声·理性": "Dylan",
    }


def test_clone_notes_explicitly_disclose_no_per_line_instruction_support(
    synth: ModuleType,
    tmp_path: Path,
) -> None:
    notes = tmp_path / "03-voice-prompts.md"
    synth.write_prompt_notes(
        notes,
        synth.DEFAULT_PROMPTS,
        Path("/models/voice-design"),
        Path("/models/base"),
        Path("/models/custom"),
        "clone",
        synth.CUSTOM_SPEAKERS,
    )
    text = notes.read_text(encoding="utf-8")
    assert "Base" in text
    assert "不支持逐句 instruct" in text


def copy_episode_inputs(target: Path) -> None:
    target.mkdir()
    for name in (
        "01-evidence.json",
        "02-script.json",
        "02-editorial-review.json",
    ):
        shutil.copyfile(FIXTURE_EPISODE / name, target / name)


def install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    synth: ModuleType,
) -> dict[str, Mock]:
    import numpy as np

    calls = {
        "design": Mock(name="generate_voice_design"),
        "clone": Mock(name="generate_voice_clone"),
        "custom": Mock(name="generate_custom_voice"),
    }

    class FakeDesignModel:
        def generate_voice_design(self, **kwargs: object):
            calls["design"](**kwargs)
            return [np.ones(2400, dtype=np.float32) * 0.05], 24000

    class FakeCloneModel:
        def create_voice_clone_prompt(self, **kwargs: object):
            return object()

        def generate_voice_clone(self, **kwargs: object):
            calls["clone"](**kwargs)
            return [np.ones(2400, dtype=np.float32) * 0.05], 24000

    class FakeCustomModel:
        def get_supported_speakers(self):
            # Real qwen_tts currently reports normalized lowercase IDs even
            # though generate_custom_voice accepts the configured display case.
            return ["serena", "dylan"]

        def generate_custom_voice(self, **kwargs: object):
            calls["custom"](**kwargs)
            return [np.ones(2400, dtype=np.float32) * 0.05], 24000

    class FakeQwen3TTSModel:
        @staticmethod
        def from_pretrained(path: str, **kwargs: object):
            if "VoiceDesign" in path:
                return FakeDesignModel()
            if "CustomVoice" in path:
                return FakeCustomModel()
            return FakeCloneModel()

    qwen_module = ModuleType("qwen_tts")
    qwen_module.Qwen3TTSModel = FakeQwen3TTSModel
    monkeypatch.setitem(sys.modules, "qwen_tts", qwen_module)

    torch_module = ModuleType("torch")
    torch_module.float16 = "float16"
    torch_module.bfloat16 = "bfloat16"
    torch_module.float32 = "float32"
    torch_module.backends = SimpleNamespace(
        mps=SimpleNamespace(is_available=lambda: False)
    )
    torch_module.cuda = SimpleNamespace(
        is_available=lambda: False,
        empty_cache=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "torch", torch_module)

    soundfile_module = ModuleType("soundfile")

    def fake_write(path: Path | str, wav: object, sample_rate: int) -> None:
        Path(path).write_bytes(b"fake-wav")

    soundfile_module.write = fake_write
    soundfile_module.read = lambda path: (
        np.ones(2400, dtype=np.float32) * 0.05,
        24000,
    )
    monkeypatch.setitem(sys.modules, "soundfile", soundfile_module)

    def fake_quality(
        generate,
        spoken_text: str,
        max_attempts: int,
        target_rms_dbfs: float,
    ):
        wavs, sample_rate = generate()
        metrics = {
            "duration_seconds": len(wavs[0]) / sample_rate,
            "rms_dbfs": -21.0,
            "peak": 0.05,
            "clipping_ratio": 0.0,
            "silence_ratio": 0.0,
            "spoken_characters_per_second": 3.0,
        }
        return wavs[0], sample_rate, 0.01, [
            {"attempt": 1, "before": metrics, "after": metrics, "issues": []}
        ]

    monkeypatch.setattr(synth, "synthesize_line_with_quality", fake_quality)
    return calls


@pytest.mark.parametrize("backend", ["custom", "clone"])
def test_backend_model_calls_without_loading_real_models(
    synth: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    backend: str,
) -> None:
    episode = tmp_path / f"episode-{backend}"
    copy_episode_inputs(episode)
    custom_model = tmp_path / "Qwen3-TTS-12Hz-1.7B-CustomVoice"
    custom_model.mkdir()
    design_model = tmp_path / "Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    base_model = tmp_path / "Qwen3-TTS-12Hz-1.7B-Base"
    design_model.mkdir()
    base_model.mkdir()
    calls = install_fake_runtime(monkeypatch, synth)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--episode-dir",
            str(episode),
            "--backend",
            backend,
            "--natural-dialogue-policy",
            "advisory",
            "--custom-voice-model",
            str(custom_model),
            "--voice-design-model",
            str(design_model),
            "--base-model",
            str(base_model),
        ],
    )

    synth.main()

    fixture_lines = json.loads(
        (episode / "02-script.json").read_text(encoding="utf-8")
    )
    expected_candidate_calls = sum(
        2 if synth.is_expressive_line(line) else 1 for line in fixture_lines
    )
    assert expected_candidate_calls > len(fixture_lines)
    assert expected_candidate_calls < len(fixture_lines) * 2

    if backend == "custom":
        assert calls["custom"].call_count == expected_candidate_calls
        assert calls["clone"].call_count == 0
        first = calls["custom"].call_args_list[0].kwargs
        assert first["speaker"] == "Serena"
        assert isinstance(first["instruct"], str)
        assert first["instruct"]
        assert "voice_clone_prompt" not in first
    else:
        assert calls["clone"].call_count == expected_candidate_calls
        assert calls["design"].call_count == 2
        assert calls["custom"].call_count == 0
        clone_prompt_ids = {
            id(call.kwargs["voice_clone_prompt"])
            for call in calls["clone"].call_args_list
        }
        # One fixed prompt per role, reused across all of that role's lines.
        assert len(clone_prompt_ids) == 2
        for call in calls["clone"].call_args_list:
            assert "instruct" not in call.kwargs
            assert "instruct_ids" not in call.kwargs
