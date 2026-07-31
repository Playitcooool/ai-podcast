from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest


SKILL_DIR = Path(__file__).resolve().parents[1]
SYNTHESIS_PATH = SKILL_DIR / "scripts" / "synthesize_episode.py"
COMPARISON_PATH = SKILL_DIR / "scripts" / "compare_voice_backends.py"
FIXTURE_EPISODE = Path(
    "/tmp/ai-podcast-test-output/"
    "2026-07-30-shujia-haizi-shangwang-baohu-haishi-guankong"
)


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def comparison(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    synthesis = load_module(SYNTHESIS_PATH, "synthesize_episode")
    monkeypatch.setitem(sys.modules, "synthesize_episode", synthesis)
    return load_module(COMPARISON_PATH, "compare_voice_backends_under_test")


def test_default_comparison_uses_eight_unique_diagnostic_lines(
    comparison: ModuleType,
) -> None:
    assert len(comparison.DEFAULT_LINE_INDEXES) == 8
    assert len(set(comparison.DEFAULT_LINE_INDEXES)) == 8
    script = comparison.synthesis.load_script(
        FIXTURE_EPISODE / "02-script.json"
    )
    selected = comparison.selected_lines(
        script,
        list(comparison.DEFAULT_LINE_INDEXES),
    )
    assert [line["index"] for line in selected] == list(
        comparison.DEFAULT_LINE_INDEXES
    )
    # The default set should span both voices and several dialogue functions.
    assert {line["speaker"] for line in selected} == set(
        comparison.synthesis.SPEAKERS
    )
    assert len({line.get("move") for line in selected}) >= 4


def test_selected_lines_rejects_unknown_indexes(
    comparison: ModuleType,
) -> None:
    script = [{"index": 1, "text": "第一句"}]
    with pytest.raises(ValueError, match="unknown|index|未知"):
        comparison.selected_lines(script, [1, 99])


def test_selected_lines_rejects_duplicates(
    comparison: ModuleType,
) -> None:
    script = [{"index": 1, "text": "第一句"}]
    with pytest.raises(ValueError, match="unique|duplicate|重复"):
        comparison.selected_lines(script, [1, 1])


def install_fake_runtime(
    monkeypatch: pytest.MonkeyPatch,
    comparison: ModuleType,
) -> dict[str, Mock]:
    calls = {
        "custom": Mock(name="custom_generation"),
        "clone": Mock(name="clone_generation"),
        "prompt": Mock(name="clone_prompt"),
    }

    class FakeCustomModel:
        def generate_custom_voice(self, **kwargs: object):
            calls["custom"](**kwargs)
            return [np.full(800, 0.04, dtype=np.float32)], 8000

    class FakeCloneModel:
        def create_voice_clone_prompt(self, **kwargs: object):
            calls["prompt"](**kwargs)
            return object()

        def generate_voice_clone(self, **kwargs: object):
            calls["clone"](**kwargs)
            return [np.full(800, 0.04, dtype=np.float32)], 8000

    class FakeQwen3TTSModel:
        @staticmethod
        def from_pretrained(path: str, **kwargs: object):
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
    soundfile_module.write = (
        lambda path, wav, sample_rate: Path(path).write_bytes(b"fake-wav")
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
            "rms_dbfs": target_rms_dbfs,
            "active_rms_dbfs": target_rms_dbfs,
            "peak": 0.04,
            "clipping_ratio": 0.0,
            "silence_ratio": 0.0,
            "spoken_characters_per_second": 4.6,
        }
        return wavs[0], sample_rate, 0.01, [
            {"attempt": 1, "after": metrics, "issues": []}
        ]

    monkeypatch.setattr(
        comparison.synthesis,
        "synthesize_line_with_quality",
        fake_quality,
    )
    return calls


def test_fake_backends_generate_matched_pairs_and_manifest(
    comparison: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    episode = tmp_path / "episode"
    episode.mkdir()
    shutil.copyfile(
        FIXTURE_EPISODE / "02-script.json",
        episode / "02-script.json",
    )
    references = episode / "audio" / "references"
    references.mkdir(parents=True)
    (references / "female.wav").write_bytes(b"reference")
    (references / "male.wav").write_bytes(b"reference")
    custom_model = tmp_path / "Qwen3-TTS-12Hz-1.7B-CustomVoice"
    base_model = tmp_path / "Qwen3-TTS-12Hz-1.7B-Base"
    custom_model.mkdir()
    base_model.mkdir()
    output_dir = tmp_path / "comparison"
    calls = install_fake_runtime(monkeypatch, comparison)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(COMPARISON_PATH),
            "--episode-dir",
            str(episode),
            "--output-dir",
            str(output_dir),
            "--custom-voice-model",
            str(custom_model),
            "--base-model",
            str(base_model),
            "--line",
            "5",
            "--line",
            "9",
        ],
    )

    comparison.main()

    assert calls["custom"].call_count == 2
    assert calls["clone"].call_count == 2
    # Both fixed role prompts are prepared for clone identity stability.
    assert calls["prompt"].call_count == 2
    for call in calls["custom"].call_args_list:
        assert call.kwargs["instruct"]
        assert call.kwargs["speaker"] in {"Serena", "Dylan"}
    for call in calls["clone"].call_args_list:
        assert "instruct" not in call.kwargs
        assert "voice_clone_prompt" in call.kwargs

    manifest_path = output_dir / "comparison-manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["line_indexes"] == [5, 9]
    assert len(manifest["records"]) == 4
    pairs: dict[int, set[str]] = {}
    for record in manifest["records"]:
        pairs.setdefault(record["line"], set()).add(record["backend"])
        assert Path(record["path"]).exists()
        assert record["sha256"]
        assert record["metrics"]
    assert pairs == {5: {"custom", "clone"}, 9: {"custom", "clone"}}
    assert manifest["listening_dimensions"] == [
        "emotion_match",
        "context_response",
        "natural_pause",
        "emphasis_accuracy",
        "voice_identity_stability",
    ]


def test_skill_documents_every_new_voice_quality_contract() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    for field in (
        '"emotion"',
        '"intensity"',
        '"pace"',
        '"energy"',
        '"pitch"',
        '"ending"',
        '"key_emphasis"',
    ):
        assert field in text

    assert "72" in text and "96" in text and "120" in text
    assert "strict" in text
    assert "auto" in text and "CustomVoice" in text
    assert "Base does not support per-line instruction" in text
    assert "pause_after_ms" in text and "overlap_next_ms" in text
    assert "--expressive-candidates 1..3" in text
    assert "candidate" in text.lower()
    assert "70 Hz high-pass" in text
    assert "activity-weighted loudness gain" in text
    for option in (
        "--emotion-match",
        "--context-response",
        "--natural-pause",
        "--emphasis-accuracy",
    ):
        assert option in text
    assert "compare_voice_backends.py --episode-dir" in text
    assert "comparison-manifest.json" in text
