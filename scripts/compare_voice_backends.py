#!/usr/bin/env python3
"""Render matched CustomVoice and Voice Clone clips for listening comparison."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import time
from typing import Any

import synthesize_episode as synthesis


DEFAULT_LINE_INDEXES = (5, 6, 8, 9, 15, 16, 22, 24)


def selected_lines(
    script: list[dict[str, Any]], indexes: list[int]
) -> list[dict[str, Any]]:
    by_index = {int(line["index"]): line for line in script}
    missing = sorted(set(indexes) - set(by_index))
    if missing:
        raise ValueError(f"unknown script line indexes: {missing}")
    if len(indexes) != len(set(indexes)):
        raise ValueError("line indexes must be unique")
    return [by_index[index] for index in indexes]


def render_backend(
    backend: str,
    model: Any,
    lines: list[dict[str, Any]],
    all_lines: list[dict[str, Any]],
    output_dir: Path,
    speakers: dict[str, str],
    clone_prompts: dict[str, Any],
    temperature: float,
    top_p: float,
) -> list[dict[str, Any]]:
    import soundfile as sf

    records: list[dict[str, Any]] = []
    for line in lines:
        spoken_text = str(line.get("tts_text", line["text"])).strip()
        position = int(line["index"]) - 1
        instruct = synthesis.contextual_performance_instruct(
            line, all_lines[position - 1] if position else None
        )
        if backend == "custom":
            generate = lambda: model.generate_custom_voice(
                text=spoken_text,
                language="Chinese",
                speaker=speakers[line["speaker"]],
                instruct=instruct,
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                non_streaming_mode=True,
            )
        else:
            generate = lambda: model.generate_voice_clone(
                text=spoken_text,
                language="Chinese",
                voice_clone_prompt=clone_prompts[line["speaker"]],
                do_sample=True,
                temperature=temperature,
                top_p=top_p,
                non_streaming_mode=True,
            )
        started = time.perf_counter()
        wav, sample_rate, _, attempts = synthesis.synthesize_line_with_quality(
            generate,
            spoken_text,
            3,
            synthesis.target_line_rms_dbfs(line),
        )
        elapsed = time.perf_counter() - started
        output = output_dir / (
            f"line-{line['index']:03d}-{backend}-{synthesis.role_name(line['speaker'])}.wav"
        )
        sf.write(output, wav, sample_rate)
        records.append(
            {
                "line": line["index"],
                "speaker": line["speaker"],
                "backend": backend,
                "path": str(output),
                "sha256": synthesis.sha256_file(output),
                "duration_seconds": round(len(wav) / sample_rate, 3),
                "generation_seconds": round(elapsed, 3),
                "performance_instruct": instruct,
                "metrics": attempts[-1]["after"]
                | synthesis.prosody_metrics(wav, sample_rate),
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--line", type=int, action="append")
    parser.add_argument(
        "--custom-voice-model",
        type=Path,
        default=synthesis.DEFAULT_CUSTOM_VOICE_MODEL,
    )
    parser.add_argument("--base-model", type=Path, default=synthesis.DEFAULT_BASE_MODEL)
    parser.add_argument("--temperature", type=float, default=synthesis.DEFAULT_TEMPERATURE)
    parser.add_argument("--top-p", type=float, default=synthesis.DEFAULT_TOP_P)
    args = parser.parse_args()

    episode_dir = args.episode_dir.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else episode_dir / "audio" / "ab-voice-backends"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    indexes = args.line or list(DEFAULT_LINE_INDEXES)
    script = synthesis.load_script(episode_dir / "02-script.json")
    lines = selected_lines(script, indexes)
    for model_path in (args.custom_voice_model, args.base_model):
        if not model_path.exists():
            raise FileNotFoundError(model_path)

    import torch
    from qwen_tts import Qwen3TTSModel

    device, dtype = synthesis.choose_device(torch)
    kwargs = synthesis.model_kwargs(torch, device, dtype)
    speakers = dict(synthesis.CUSTOM_SPEAKERS)
    records: list[dict[str, Any]] = []

    custom_model = Qwen3TTSModel.from_pretrained(
        str(args.custom_voice_model), **kwargs
    )
    records.extend(
        render_backend(
            "custom",
            custom_model,
            lines,
            script,
            output_dir,
            speakers,
            {},
            args.temperature,
            args.top_p,
        )
    )
    del custom_model
    synthesis.clear_device_cache(torch)
    gc.collect()

    clone_model = Qwen3TTSModel.from_pretrained(str(args.base_model), **kwargs)
    clone_prompts: dict[str, Any] = {}
    for speaker in synthesis.SPEAKERS:
        reference = (
            episode_dir
            / "audio"
            / "references"
            / f"{synthesis.role_name(speaker)}.wav"
        )
        if not reference.exists():
            raise FileNotFoundError(
                f"clone comparison requires the existing reference: {reference}"
            )
        clone_prompts[speaker] = clone_model.create_voice_clone_prompt(
            ref_audio=str(reference),
            ref_text=synthesis.REFERENCE_TEXTS[speaker],
        )
    records.extend(
        render_backend(
            "clone",
            clone_model,
            lines,
            script,
            output_dir,
            speakers,
            clone_prompts,
            args.temperature,
            args.top_p,
        )
    )
    manifest = {
        "episode_dir": str(episode_dir),
        "line_indexes": indexes,
        "device": device,
        "dtype": str(dtype),
        "temperature": args.temperature,
        "top_p": args.top_p,
        "custom_voice_model": str(args.custom_voice_model),
        "base_model": str(args.base_model),
        "records": records,
        "listening_dimensions": [
            "emotion_match",
            "context_response",
            "natural_pause",
            "emphasis_accuracy",
            "voice_identity_stability",
        ],
    }
    manifest_path = output_dir / "comparison-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
