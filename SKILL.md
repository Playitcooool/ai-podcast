---
name: emotional-podcast-video
description: "Create publish-ready Bilibili two-voice discussion videos from current high-discussion social issues relevant to Chinese internet audiences. Use last30days plus Chinese-language evidence to research and score candidates, exclude previously selected or semantically similar topics through persistent history, automatically choose the strongest eligible topic, write a 6-12 minute balanced Mandarin dialogue, synthesize stable female and male voices, generate a titled 16:9 theme image, render and verify an H.264/AAC MP4, and package scripts, evidence, timing, manifests, and Bilibili publishing copy. Use for autonomous recurring social-issue podcasts, emotional discussions, and current-topic dialogue videos."
---

# Social Discussion Podcast Video

Produce one autonomous, two-voice Bilibili discussion episode at a time. Research,
score, select, and continue without asking the user to choose. Treat an explicitly
provided user topic as an override, but still run duplicate and safety checks.

## Required sequence

1. Check topic history.
2. Research and score at least 3 eligible candidates.
3. Select and reserve the highest-scoring non-duplicate topic.
4. Create the episode folder and editorial brief.
5. Write and validate the dialogue.
6. Generate stable two-voice audio.
7. Generate and inspect the titled theme image.
8. Render and verify the MP4.
9. Prepare Bilibili publishing materials.
10. Pass all quality gates, then mark the episode and history entry complete.

Do not pause for topic approval and do not wait for “继续”.

## Topic history and duplicate control

Use `${EMOTIONAL_PODCAST_OUTPUT_ROOT}/topic-history.json` as the persistent source
of truth. Resolve `scripts/topic_history.py` relative to this `SKILL.md`; use the
script instead of editing history JSON directly. If the variable is unset, the
script keeps its documented local-machine fallback.

Before research, run `bootstrap` and `validate`. For every candidate, run `check`
with its topic, topic family, central conflict, audience, and angle. Treat the
script's similarity result as deterministic evidence, then make a semantic judgment.
Reject a candidate when it repeats the same core question, conflict, audience
promise, or topic-family angle even if a new incident or title is used.

Reserve the selected topic with `reserve` before creating audio, images, or video.
The reservation is lock-protected and prevents concurrent exact or likely duplicate
selection. If reservation fails, choose the next eligible candidate. Update the
entry to `in_production` after creating the episode folder, `complete` only after
all final gates pass, or `abandoned` with a reason when production stops permanently.

If every candidate overlaps with history, research another batch. Reframe an old
topic only when the central conflict, affected audience, and episode promise are
materially different.

## Research and automatic selection

Read [references/topic-selection.md](references/topic-selection.md) before research.
Use the current date and the `last30days` skill for broad discovery. Supplement it
with Chinese-language discussion signals and authoritative sources for factual
verification. Do not infer Chinese popularity from global platforms alone.

Build at least 3 candidates. For each candidate record:

- working title, topic family, central conflict, target audience, and episode angle;
- why it is active now, source dates, cross-platform signals, and visible engagement
  when available;
- verified facts, unresolved claims, source URLs, safety concerns, and duplicate
  result;
- scores for heat, momentum, Chinese-internet fit, dialogue tension, and
  verifiability.

Calculate:

`total = heat*0.30 + momentum*0.20 + chinese_fit*0.20 + tension*0.15 + verifiability*0.15`

Choose the highest-scoring eligible topic. A score is the model's best current
forecast, not a guarantee. Downgrade single-post virality, circular reporting,
unverified allegations, rage bait, personal attacks, doxxing, and breaking events
whose facts are too unstable. Prefer a verified structural question over gossip
about a named person.

Announce the selected topic and continue production in the same turn. Save the full
candidate table, evidence, duplicate checks, selection reason, and uncertainty in
`01-editorial-brief.md`.

## Episode setup and manifest

Create a new folder under:

`${EMOTIONAL_PODCAST_OUTPUT_ROOT}/YYYY-MM-DD-slug/`

Never overwrite an existing folder; append a numeric suffix when needed. Read
[references/episode-manifest-schema.md](references/episode-manifest-schema.md) and
create `00-manifest.json`. Keep the manifest and topic-history status aligned.

The editorial brief must also include the thesis, central question, strongest
counter-position, 3–5 factual evidence points with URLs, audience promise, human
stakes, uncertainty, privacy/copyright/safety notes, and a 6–12 minute target.
Use sources as research inputs, not text to copy. Avoid professional diagnosis or
personalized legal, medical, financial, or mental-health advice.

Save the verified evidence points in `01-evidence.json` as an array of objects with
`id`, `claim`, `source_title`, `source_url`, and `source_date`. Use stable IDs such
as `E1`, `E2`, and cite those IDs from factual script turns. Include only sources
actually opened and checked.

## Dialogue

Save `02-script.md` and `02-script.json`. Alternate:

- `女声·感性`: validate lived experience, notice ambiguity, and ask emotionally
  precise questions;
- `男声·理性`: separate facts from assumptions, name trade-offs, test
  counterexamples, and offer frameworks rather than commands.

Begin with a dedicated spoken introduction before either host starts debating. The
first script item must:

- use `speaker: "女声·感性"` and `segment: "导入语"`;
- contain 70–180 characters including punctuation;
- calmly establish the real-life setting or recent social context, name why the
  issue matters now, and end by handing the central question to the discussion;
- sound like a natural programme introduction, not a slogan, position statement,
  answer, greeting, channel promotion, or request to like and subscribe.

Do not let the introduction argue either side. After it, leave a clearly audible
pause and let `男声·理性` begin with a transition turn marked
`move: "承接"`. This turn must respond to the introduction's central question,
explain why the question is difficult, and define what the episode will examine. It
must not jump directly to a verdict, list of arguments, or generic “我认为”. Use
this arc:
introduction; dilemma; strongest case for each side; useful example; surprising
distinction or counterexample; mutual revision; nuanced conclusion; comment-worthy
closing question.

Do not make the female voice irrational or the male voice automatically correct.
Give each speaker one strong insight and one moment of revision. Use a few natural
Mandarin discourse markers such as “嗯”“其实”“对”“等一下” only where they improve
spoken flow. Put intended spoken markers directly in `text`.

Keep ordinary discussion turns at 40–72 characters and use 8–39-character reactions
or follow-up questions to break up the rhythm, with no run of six discussion turns
lacking a short turn. A turn may contain 73–96 characters when natural phrasing
needs it. Only a necessary fact or qualification may contain 97–120 characters,
and it requires `pacing_exception`. Never exceed 120 characters in a strict
production script. Keep one main idea per turn and avoid speech-like essays built
from “首先、其次、最后”.

Mark every discussion turn with exactly one `move` from: `承接`, `新事实`,
`具体例子`, `反例`, `区分`, `追问`, `修正`, `深化`, `综合`, `建议`, `收束`,
`落点`, or `邀请`. Choose the move for what the turn adds, not its tone. Never use the same
move in adjacent turns. Across the episode include at least four distinct moves,
including one `修正`, one of `反例`/`区分`, and one of `新事实`/`具体例子`.
Rewrite or delete a turn that merely paraphrases an earlier turn; adjacent or
nearby turns must add a fact, example, counterexample, distinction, question,
revision, synthesis, or practical implication.

Mark every discussion turn with one `claim_type`: `fact`, `inference`, `opinion`,
`example`, `question`, `proposal`, or `uncertainty`. A `fact` turn must cite one or
more valid `source_ids` from `01-evidence.json`; non-fact turns must not borrow
source IDs to make an interpretation look verified. Include 2–4 factual turns backed
by at least two independent evidence records, at least one concrete `example`, and
at least one `uncertainty` turn that states what cannot currently be concluded.
Introduce factual material conversationally rather than reading a bibliography.
Never invent a personal anecdote. Mark a constructed scene as hypothetical in the
spoken text; cite a real case as fact.

Give every line a structured `performance` object. Keep the stable role persona
separate from the performance of the current sentence:

```json
{
  "emotion": "克制的担忧",
  "intensity": 0.55,
  "pace": "slightly_slow",
  "energy": "medium_low",
  "pitch": "natural",
  "ending": "rising",
  "key_emphasis": ["多限制一点", "拿自己去试错"]
}
```

- `intensity` must be from 0 to 1.
- `pace` must be `slow`, `slightly_slow`, `natural`, `slightly_fast`, or `fast`.
- `energy` must be `low`, `medium_low`, `medium`, `medium_high`, or `high`.
- `pitch` must be `low`, `slightly_low`, `natural`, `slightly_high`, or `high`.
- `ending` must be `settling`, `level`, `rising`, `falling`, or `open`.
- `key_emphasis` may contain at most three exact phrases from the spoken text.

Use acoustic directions, not editorial abstractions. Describe what should be
audible: restrained worry, a slightly slower pace, a real pause before revising,
or an open question ending. `voice_prompt` remains accepted for old scripts, but
new scripts must not use it as a substitute for `performance`.

Write Mandarin-friendly spoken forms before synthesis. When `text` contains Arabic
digits, percentages, Latin letters, abbreviations, uncommon names, or symbols whose
reading may be ambiguous, add `tts_text` with the intended fully spoken form and a
concise `pronunciation_note`. Preserve the meaning and numbers exactly.

Require 1,500–2,800 script characters. Most discussion turns should be no more than
72 spoken characters (about 15 seconds at 4.6 characters per second), no ordinary
turn may exceed 96, and a 97–120-character turn requires a specific
`pacing_exception` explaining why splitting would damage a necessary fact or
qualification. Never exceed two turns above 72 characters. Split written-style
paragraphs into reactions, questions, counterexamples, and revisions.

An optional `timing` object may declare either `pause_after_ms` from 0–3000 or
`overlap_next_ms` from 0–150, never both. Use explicit overlap sparingly and only
for a believable acknowledgement or pickup; derived timing handles normal turns.
Then use actual synthesized duration.
Expand with evidence, examples, or counterarguments when below 6 minutes; remove
repetition first when above 12 minutes.

End with exactly four turns marked `segment: "结尾"`:

1. `move: "综合"` with `claim_type: "inference"` — state what the episode has
   clarified without claiming a total answer;
2. `move: "收束"` with `claim_type: "uncertainty"` — name what remains unresolved
   or depends on circumstance;
3. `move: "落点"` with `claim_type: "proposal"` — offer one concrete, non-preachy
   thought for someone living through the issue;
4. `move: "邀请"` with `claim_type: "question"` — ask one specific open question,
   without a generic “欢迎评论” add-on.

Let both hosts contribute to the four-turn closing through normal alternation. End
the final audio with a short settling silence.

Use script JSON objects like:

```json
{"index":1,"speaker":"女声·感性","segment":"导入语","text":"...","performance":{"emotion":"平静观察","intensity":0.3,"pace":"slightly_slow","energy":"medium_low","pitch":"natural","ending":"open","key_emphasis":[]}}
{"index":2,"speaker":"男声·理性","segment":"讨论","move":"承接","claim_type":"question","text":"...","performance":{"emotion":"专注思考","intensity":0.4,"pace":"natural","energy":"medium","pitch":"natural","ending":"open","key_emphasis":[]}}
{"index":3,"speaker":"女声·感性","segment":"讨论","move":"新事实","claim_type":"fact","source_ids":["E1"],"text":"...","performance":{"emotion":"认真","intensity":0.3,"pace":"natural","energy":"medium","pitch":"natural","ending":"level","key_emphasis":[]}}
```

## Stable two-voice synthesis

### Scheduled-task reliability policy

Scheduled tasks are unattended and must use a bounded, resumable synthesis policy.
Do not run the bare command with `--backend auto` in a scheduled task. Before
synthesis, write the runtime environment to the manifest: Python executable,
package versions, model paths, selected backend, device, and the reliability
profile.

For scheduled production, run:

```text
python scripts/synthesize_episode.py --episode-dir <episode-folder> \
  --backend clone --expressive-candidates 1 --max-line-attempts 1 \
  --scheduled-safe
```

`--backend clone` is the unattended compatibility baseline because it has been
verified on the production machine and does not depend on CustomVoice instruction
decoding. Use CustomVoice in a scheduled task only as an explicitly requested,
non-default experiment. The bundled script does not supervise or kill its own
process; if CustomVoice is selected, wrap it in a scheduler/worker that enforces
a hard timeout and retries with clone after timeout, OOM, missing dependency, or
a non-readable WAV.

Never wait indefinitely for a TTS call. A scheduled run must:

- skip any canonical line WAV that matches the current script hash and record it as
  resumed;
- cap generation length (`max_new_tokens`) in the bundled script;
- have the outer scheduler checkpoint after every line, emit a heartbeat, enforce
  a process-level timeout, and restart the worker after a failed or timed-out line;
- preserve candidates and failure traces, then retry the failed line once with the
  fallback backend; record those orchestration fields alongside the script's
  `scheduled_safe`, backend, and sampling fields.

SoX is optional for this pipeline and its absence must not block synthesis. Do not
require `flash-attn` on Apple Silicon/MPS; it is a CUDA optimization and is not a
reliability prerequisite for the scheduled profile.

Resolve and run `scripts/synthesize_episode.py` relative to this `SKILL.md`:

```text
python scripts/synthesize_episode.py --episode-dir <episode-folder>
```

Interactive runs may use `auto`, which prefers Qwen3-TTS CustomVoice when its local
model is installed. It uses stable speakers `Serena` for `女声·感性` and `Dylan` for
`男声·理性`, then converts each line's structured performance and dialogue context
into a supported per-line `instruct`. This is the preferred path when emotional
control matters.

The compatible `clone` backend first creates one original VoiceDesign reference for
each role, then uses the Base model's fixed Voice Clone prompt for every line. It
preserves the designed identity, but Base does not support per-line instruction
control. Never pretend that a clone `voice_prompt` was applied. Do not replace the
fixed clone prompt with independent VoiceDesign generation for every line.

Use `--backend custom` to require emotional instruction control or `--backend clone`
to require the original designed voices. `auto` falls back to clone only when the
CustomVoice model is absent. Keep role persona and current-line performance separate.

Generate two alternatives for expressive lines by default: high-intensity lines and
turns marked `追问`, `反例`, `修正`, `综合`, or `邀请`. Generate one version for
ordinary fact delivery. Measure pace, active loudness, voiced dynamic range, energy
slope, pause count, and pitch movement; retain the highest-scoring technically valid
candidate. Save all alternatives and their selection reasons under
`audio/candidates/` and in `03-audio-qc.json`. Use `--expressive-candidates 1..3`
when a production constraint requires a different count.

The assembler derives different timing for the introduction, short reactions,
questions, revisions, ordinary handoffs, and the ending. It uses very low deterministic
room tone instead of hard digital silence and supports explicitly requested
crossfade overlap. Do not restore one fixed pause between every turn.

For every generated line, trim excessive edge silence while preserving soft breaths
and at least 180 ms of leading and 220 ms of trailing context. Remove DC offset and
normalize active speech to a performance-dependent target, preserving about 2–4 dB
of level difference between low- and high-energy delivery. Check duration, clipping,
silence ratio, level, and spoken-character rate. Retry a failed candidate up to three
total attempts; stop production if it still fails. Apply one light final master:
70 Hz high-pass, gentle de-essing, 1.6:1 compression, activity-weighted loudness gain,
peak protection, and short fades. Preserve the room-noise floor instead of amplifying
it with positive programme gain. Save before/after metrics, attempts, candidate
selection, mastering parameters, and issues in `03-audio-qc.json`. Review every line
flagged by names, numbers,
abbreviations, or awkward punctuation, and regenerate any line with a
mispronunciation, swallowed word, duplicated phrase, unnatural pause, or mismatched
emotion. Keep the introduction slightly slower and restrained, and let the closing
settle rather than accelerate.

After writing the script, complete `02-editorial-review.json` using
[references/editorial-review-schema.md](references/editorial-review-schema.md) and
run synthesis only after every semantic check passes. After synthesis, review the
rendered line audio and record results with `scripts/audio_review.py`; run its
`check` command before rendering video. A pending or regenerate result fails the
audio gate.

```text
python scripts/audio_review.py --episode-dir <episode-folder> record --line 3 --status passed --notes "数字、人名、停顿和情绪均正确" --emotion-match 4 --context-response 4 --natural-pause 4 --emphasis-accuracy 5
python scripts/audio_review.py --episode-dir <episode-folder> check
```

Every passed line requires four 1–5 listening scores: `emotion_match`,
`context_response`, `natural_pause`, and `emphasis_accuracy`. Any score below 3
forces regeneration. Treat `emphasis_accuracy` as including exact wording,
pronunciation, and intended stress. Do not mark a candidate passed from waveform
statistics alone.

Use `record --all` only after actually reviewing every line. A line marked
`regenerate` must be regenerated, reviewed again, and changed to `passed`.

For a backend or voice change, render the same eight emotionally diagnostic lines
through both CustomVoice and Voice Clone before changing the production default:

```text
python scripts/compare_voice_backends.py --episode-dir <episode-folder>
```

Review the matched clips for emotion, conversational response, pause naturalness,
emphasis/pronunciation, and identity stability. The script writes WAV pairs and
`comparison-manifest.json` under `audio/ab-voice-backends/`. Do not infer a listening
winner from waveform metrics alone.

Use local models rooted at `${EMOTIONAL_PODCAST_MODEL_ROOT}`:

- `${EMOTIONAL_PODCAST_MODEL_ROOT}/Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- `${EMOTIONAL_PODCAST_MODEL_ROOT}/Qwen3-TTS-12Hz-1.7B-Base`
- `${EMOTIONAL_PODCAST_MODEL_ROOT}/Qwen3-TTS-12Hz-1.7B-CustomVoice`

Prefer MPS on Apple Silicon. Never clone a real person's voice without authorization.
Voice generation remains stochastic; do not promise identical voices across episodes.
For scheduled runs, reproducibility means bounded completion and stable identity,
not identical waveforms.

Require `audio/references/`, per-line WAV files, `audio/full-episode.wav`,
`03-voice-prompts.md`, `03-timing.json`, and `03-audio-qc.json`. Timing must contain
actual per-line wall-clock measurements, audio duration, sample rate, device, and
real-time factor.

## Theme image

After topic selection, use the `imagegen` skill to create one original 16:9 image.
Display the exact selected Chinese episode title once, prominently and legibly in
the exact visual center. Keep every other text element out: no subtitle, source
label, logo, watermark, decorative word, or pseudo-text. Avoid celebrity likenesses
and recognizable private people.

Save `04-theme-image.png` and `04-image-prompt.md`. Inspect the generated image.
Regenerate it if any title character is malformed, missing, duplicated, illegible,
or off-center, or if extra text or visual artifacts appear.

## Render and verify

Resolve and run `scripts/build_video.py` relative to this `SKILL.md`. Create
`05-emotional-podcast.mp4`, `05-render-report.json`, and
`05-render-command.txt`.

The renderer must verify:

- one 1920×1080 H.264 video stream and one AAC audio stream;
- output duration between 6 and 12 minutes;
- output duration closely matches the source audio;
- a playable MP4 with fast-start metadata.

Treat a nonzero renderer exit or `validation.passed: false` as a failed gate and fix
the cause before continuing.

## Bilibili package

Save `06-bilibili-publish.md` with 3 title options, one recommendation, a 2–4
paragraph Chinese description, 8–12 tags, a pinned-comment question, AI-content
disclosure, source links, suggested category/audience, and short cover-copy options.
The generated image already contains the exact centered episode title; add no other
text to that image.

Do not imply professional counseling or diagnosis. Do not expose private identities
or repeat unverified accusations as facts.

## Required episode contents

```text
episode-folder/
├── 00-manifest.json
├── 01-editorial-brief.md
├── 01-evidence.json
├── 02-script.md
├── 02-script.json
├── 02-editorial-review.json
├── 03-voice-prompts.md
├── 03-timing.json
├── 03-audio-qc.json
├── audio/
│   ├── references/
│   ├── candidates/
│   ├── line-001-female.wav
│   └── full-episode.wav
├── 04-theme-image.png
├── 04-image-prompt.md
├── 05-emotional-podcast.mp4
├── 05-render-report.json
├── 05-render-command.txt
└── 06-bilibili-publish.md
```

## Final quality gate

Before completion, verify:

- the selected topic passed history and semantic duplicate checks;
- the evidence-backed score and uncertainty are recorded;
- the script has a thesis, strong counter-position, balanced revisions, and closing
  question;
- the script begins with a neutral 70–180-character `导入语`, followed by an audible
  transition into the discussion rather than an immediate debate;
- the first discussion turn is marked `move: "承接"` and frames the difficulty and
  scope without giving an immediate verdict;
- each discussion turn is 8–120 characters under the strict production policy,
  most ordinary turns are 40–72, and
  every six-turn window contains at least one short reaction or follow-up;
- strict natural-dialogue validation passes: most turns are at most 72 spoken
  characters, no ordinary turn exceeds 96, any 97–120-character exception has a
  specific reason, and no more than two turns exceed 72;
- every discussion turn declares a valid non-repeating `move`, the episode covers
  the required move mix, and no two turns substantially repeat the same wording;
- every discussion turn declares an accurate `claim_type`; 2–4 fact turns resolve
  to checked evidence, while example and uncertainty turns are present and clearly
  framed;
- the final four turns are the required `综合`/`收束`/`落点`/`邀请` closing sequence,
  end on a specific question, and are followed by settling silence;
- both voice identities remain recognizably stable and contribute meaningfully;
- CustomVoice is used when per-line emotional control is required, every new script
  line has a valid structured performance, and the report proves whether the
  instruction was actually applied;
- expressive lines have the configured number of candidates, every candidate and
  selection reason is recorded, and the selected version is the reviewed WAV;
- every generated line passes loudness, clipping, silence, duration, and speech-rate
  checks; pronunciation-sensitive lines use reviewed `tts_text`, and
  `03-audio-qc.json` records no unresolved issue;
- dynamic transition records contain no accidental uniform-pause pattern; room tone,
  overlaps, breath-preserving trim, per-line energy targets, and the final master are
  recorded and free of clipping;
- `02-editorial-review.json` proves all semantic checks passed, and
  `scripts/audio_review.py check` proves every rendered line was reviewed, all four
  performance ratings are at least 3, and every line passed;
- actual audio and video duration is 6–12 minutes;
- all WAV files are readable and the MP4 renderer validation passes;
- the image is original, 16:9, and displays the exact centered title once;
- timing uses actual wall-clock measurements;
- publishing copy includes sources and AI disclosure without unsupported claims;
- manifest and topic history both end in `complete`.

Fix failed gates before reporting completion. Return clickable links to the MP4,
full audio, theme image, script, timing report, editorial brief, and publishing
package.
