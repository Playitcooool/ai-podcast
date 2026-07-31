# AI Podcast

An open-source Codex skill for producing evidence-backed Chinese AI podcasts:
from current-topic research and balanced two-host scripts to stable voice
synthesis, audio review, optional artwork, and Bilibili delivery.

It is designed for scheduled runs. The `scheduled-safe` profile uses the verified
Voice Clone backend, one candidate, bounded decoding, and runtime diagnostics. If
GPT Image 2/imagegen is unavailable, the workflow still delivers a complete
audio package instead of failing the episode.

## Install

```bash
git clone https://github.com/Playitcooool/ai-podcast.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/ai-podcast"
```

Chinese documentation is available in [README.zh-CN.md](README.zh-CN.md).

## Topic research dependency

Topic selection uses the Codex `last30days` skill to research real discussion
signals, recent activity, and source evidence from the last 30 days. `ai-podcast`
then adds Chinese-language evidence, semantic duplicate checks, and safety review.

Make sure `last30days` is installed, then use it during research:

```text
Use $last30days to find youth-relevant campus, dorm, friendship, dating, or online-culture topics discussed in the last 30 days. Return discussion signals, dates, visible engagement, and factual sources.
```

If `last30days` is unavailable, do not treat one article or model memory as proof
of popularity. Add accessible Chinese-platform signals and authoritative sources,
or pause automatic topic selection.

## Model and output paths

```bash
export AI_PODCAST_MODEL_ROOT=/path/to/qwen3-tts/models
export AI_PODCAST_OUTPUT_ROOT=/path/to/ai-podcast-output
```

The model directory should contain:

```text
Qwen3-TTS-12Hz-1.7B-VoiceDesign/
Qwen3-TTS-12Hz-1.7B-Base/
Qwen3-TTS-12Hz-1.7B-CustomVoice/
```

## Scheduled synthesis

```bash
python scripts/synthesize_episode.py \
  --episode-dir /path/to/episode \
  --backend clone \
  --expressive-candidates 1 \
  --max-line-attempts 1 \
  --scheduled-safe
```

Use `--backend custom` only after manual listening checks. For unattended jobs,
the outer scheduler/worker should provide a process timeout and retry with clone.

## Audio-only fallback

When GPT Image 2/imagegen is unavailable, skip image and video rendering and set
`delivery_mode` to `audio_only`. Deliver:

- `audio/full-episode.wav`
- the two-host script and evidence files
- timing and audio-quality reports
- Bilibili audio publishing copy

Do not create a fake placeholder image. Record `image_unavailable` in the
manifest.

## What it includes

- youth-oriented topic discovery and Chinese-language evidence checks
- semantic topic history and duplicate prevention
- 1,500–2,800 character Mandarin two-host dialogue scripts
- CustomVoice emotional control and stable Voice Clone identity
- candidate audio, acoustic metrics, and listening-review records
- dynamic pauses, room tone, mastering, and pronunciation checks
- optional 16:9 artwork, H.264/AAC video, and Bilibili publishing copy

## License

MIT. Qwen3-TTS models are governed by their own licenses. Obtain authorization
before cloning any real person's voice.

## Promotion

> AI Podcast connects “current topic → relatable two-host discussion → stable voice → Bilibili video or audio delivery” in one reusable Codex skill. It is built for youth-life topics such as dorms, roommates, group chats, friendship, dating, gaming, short-video culture, and AI tools.
