# AI Podcast

一个面向 Codex 的中文情绪播客生产 skill：从热点选题、证据核验、双人对话脚本，到稳定语音合成、音频审阅、主题图和 Bilibili 视频打包。

它特别适合定时任务：默认提供 `scheduled-safe` 音频配置，使用已验证的 Voice Clone 后端、单候选、有限解码长度，并把运行配置写入 timing manifest，降低 CustomVoice 在无人值守任务中长时间等待的风险。没有 GPT Image 2 时仍可生成完整音频交付包；进程级超时和自动回退由外层 scheduler 负责。

## 安装

将本仓库克隆到 Codex 的 skills 目录：

```bash
git clone https://github.com/Playitcooool/ai-podcast.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/ai-podcast"
```

也可以直接把仓库中的整个目录复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`。

## 选题研究依赖：last30days

选题阶段依赖 Codex 的 `last30days` skill，用来检索最近 30 天的真实讨论、平台信号和可核验来源。`ai-podcast` 会在它的基础上再补充中文互联网证据，并执行话题去重和安全检查。

请先确保 `last30days` 已安装，然后在 Codex 中使用：

```text
使用 $last30days 研究最近 30 天适合年轻人讨论的校园、寝室、社交或网络话题，返回讨论信号、来源日期、可见互动和事实来源。
```

如果 `last30days` 不可用，不能把单篇新闻或模型记忆当成热度证据；应降低候选可信度，补充可访问的中文平台讨论和权威来源，或暂缓自动选题。

## 模型和路径配置

安装 Qwen3-TTS 模型后设置：

```bash
export AI_PODCAST_MODEL_ROOT=/path/to/qwen3-tts/models
export AI_PODCAST_OUTPUT_ROOT=/path/to/ai-podcast-output
```

目录应包含：

```text
Qwen3-TTS-12Hz-1.7B-VoiceDesign/
Qwen3-TTS-12Hz-1.7B-Base/
Qwen3-TTS-12Hz-1.7B-CustomVoice/
```

## 定时任务推荐配置

```bash
python scripts/synthesize_episode.py \
  --episode-dir /path/to/episode \
  --backend clone \
  --expressive-candidates 1 \
  --max-line-attempts 1 \
  --scheduled-safe
```

需要更强情绪控制时，可以在人工试听后使用 `--backend custom`；不要把它作为无人值守任务的默认后端。没有 GPT Image 2 时跳过图片和视频步骤，保留 `audio/full-episode.wav`、脚本、证据和音频质检结果。

## 能力

- last30days 选题与中文证据核验
- 话题历史和语义去重
- 1500–2800 字双人普通话对话脚本
- CustomVoice 情绪控制与 Voice Clone 稳定身份
- 候选音频、音频质量指标和人工审阅记录
- 动态停顿、房间底噪、母带处理
- 可选的 16:9 主题图、H.264/AAC 视频和 Bilibili 发布文案

## 开源协议

MIT。Qwen3-TTS 模型及其权利归原作者所有，使用时请遵守对应模型许可证，并确保声音克隆获得授权。

## 宣传文案

> AI Podcast：把“热点选题 → 双人对谈 → 稳定语音 → Bilibili 成片或音频交付”串成一个可复用的 Codex skill。支持中文证据核验、语义去重、情绪化 CustomVoice、稳定 Voice Clone，以及没有 GPT Image 2 时的 audio-only fallback。适合做社会议题播客、AI 播客和持续更新的内容栏目。
