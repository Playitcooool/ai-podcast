# Episode manifest schema

Read this reference before creating `00-manifest.json`. Keep the episode and
topic-history lifecycle aligned.

```json
{
  "episode_id": "2026-07-26-example-topic",
  "topic": "...",
  "slug": "example-topic",
  "status": "selected|in_production|complete|abandoned",
  "stage": "editorial|scripted|audio|rendered|publish_package",
  "created_at": "2026-07-26T00:00:00+08:00",
  "updated_at": "2026-07-26T00:00:00+08:00",
  "runtime_seconds": 0,
  "topic_fingerprint": {
    "topic_family": "...",
    "central_conflict": "...",
    "audience": "...",
    "angle": "..."
  },
  "selection": {
    "score": 0,
    "rank": 1,
    "duplicate_check": "passed",
    "forecast_uncertainty": "..."
  },
  "models": {
    "voice_design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "voice_clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "image": "imagegen"
  },
  "artifacts": {
    "editorial_brief": "01-editorial-brief.md",
    "evidence": "01-evidence.json",
    "script_markdown": "02-script.md",
    "script_json": "02-script.json",
    "editorial_review": "02-editorial-review.json",
    "voice_prompts": "03-voice-prompts.md",
    "timing": "03-timing.json",
    "audio_qc": "03-audio-qc.json",
    "voice_references": "audio/references/",
    "line_audio": "audio/line-*.wav",
    "audio": "audio/full-episode.wav",
    "theme_image": "04-theme-image.png",
    "image_prompt": "04-image-prompt.md",
    "delivery_mode": "video",
    "video": "05-ai-podcast.mp4",
    "render_report": "05-render-report.json",
    "render_command": "05-render-command.txt",
    "publishing": "06-bilibili-publish.md"
  },
  "source_urls": [],
  "quality_checks": {
    "history_duplicate_check": false,
    "semantic_duplicate_check": false,
    "selection_score_recorded": false,
    "selection_uncertainty_recorded": false,
    "evidence_traceability": false,
    "script": false,
    "editorial_review": false,
    "opening_intro": false,
    "opening_transition": false,
    "dialogue_pacing": false,
    "discussion_progression": false,
    "closing_structure": false,
    "audio_quality": false,
    "pronunciation_review": false,
    "stable_voice_strategy": false,
    "wav_readability": false,
    "wall_clock_timing": false,
    "runtime": false,
    "video_streams": false,
    "theme_originality": false,
    "theme_aspect_ratio": false,
    "theme_title": false,
    "publishing_sources": false,
    "publishing_disclosure": false,
    "manifest_history_alignment": false
  }
}
```

When GPT Image 2/imagegen is unavailable, set `delivery_mode` to `audio_only`,
omit `theme_image`, `video`, `render_report`, and `render_command`, and include
`image_unavailable` with the reason. Audio, script, timing, and audio QC remain
required.

Keep artifact paths relative to the episode folder. Use `in_production` throughout
production and update `stage` as gates pass. Set `complete` only after every final
quality check passes; set `abandoned` with a reason when production stops permanently.
Use the same top-level status in the matching `topic-history.json` entry.
