# Emotional Podcast Video

一个面向 Codex 的中文情绪播客生产 skill：从热点选题、证据核验、双人对话脚本，到稳定语音合成、音频审阅、主题图和 Bilibili 视频打包。

它特别适合定时任务：默认提供 `scheduled-safe` 音频配置，使用已验证的 Voice Clone 后端、单候选、有限解码长度，并把运行配置写入 timing manifest，降低 CustomVoice 在无人值守任务中长时间等待的风险。进程级超时和自动回退由外层 scheduler 负责。

## 安装

将本仓库克隆到 Codex 的 skills 目录：

```bash
git clone https://github.com/Playitcooool/emotional-podcast-video.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/emotional-podcast-video"
```

也可以直接把仓库中的整个目录复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`。

## 模型和路径配置

安装 Qwen3-TTS 模型后设置：

```bash
export EMOTIONAL_PODCAST_MODEL_ROOT=/path/to/qwen3-tts/models
export EMOTIONAL_PODCAST_OUTPUT_ROOT=/path/to/emotional-podcast-output
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

需要更强情绪控制时，可以在人工试听后使用 `--backend custom`；不要把它作为无人值守任务的默认后端。

## 能力

- last30days 选题与中文证据核验
- 话题历史和语义去重
- 1500–2800 字双人普通话对话脚本
- CustomVoice 情绪控制与 Voice Clone 稳定身份
- 候选音频、音频质量指标和人工审阅记录
- 动态停顿、房间底噪、母带处理
- 16:9 主题图、H.264/AAC 视频和 Bilibili 发布文案

## 开源协议

MIT。Qwen3-TTS 模型及其权利归原作者所有，使用时请遵守对应模型许可证，并确保声音克隆获得授权。

## 宣传文案

> Emotional Podcast Video：把“热点选题 → 双人情绪对谈 → 稳定语音 → Bilibili 成片”串成一个可复用的 Codex skill。支持中文证据核验、语义去重、情绪化 CustomVoice、稳定 Voice Clone，以及专为 scheduled task 设计的安全音频后端。适合做社会议题播客、情绪讨论和持续更新的视频栏目。
