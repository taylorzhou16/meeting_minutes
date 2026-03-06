# Meeting Minutes

Zoom录音转录与会议纪要生成器。使用 MLX-Whisper 进行 GPU 加速转录，结合可选的人工笔记生成详细会议纪要，并保存到 Google Docs（支持真正的表格）。

## 功能特点

- 🚀 **GPU 加速转录**：使用 MLX-Whisper 利用 Apple M1/M2 的 Metal GPU，速度比 CPU 快 12-20 倍
- 📝 **详细会议纪要**：自动生成结构化的会议纪要，包含议题讨论、决策汇总、待办事项
- 📊 **Google Docs 表格**：支持真正的表格创建，从后往前填充避免索引问题
- 🔧 **可选人工笔记**：可结合人工笔记辅助生成更准确的纪要

## 安装

### 依赖

```bash
# 安装 MLX-Whisper
pip install mlx-whisper

# 安装 Google API 客户端（可选，用于 Google Docs 导出）
pip install google-api-python-client google-auth-oauthlib
```

### Google Docs API 配置（可选）

1. 访问 https://console.cloud.google.com/
2. 创建项目并启用 Google Docs API
3. 配置 OAuth 同意屏幕
4. 创建 OAuth 2.0 客户端 ID（桌面应用）
5. 下载 JSON 保存到 `~/.credentials/google_client_secret.json`

## 使用方法

### 作为 Claude Code Skill 使用

在 Claude Code 中：

```
/meeting-minutes /path/to/zoom_recording.m4a
/meeting-minutes /path/to/zoom_recording.m4a --notes /path/to/notes.md
```

### 命令行使用

```bash
python meeting_minutes.py /path/to/audio.m4a

# 指定模型
python meeting_minutes.py /path/to/audio.m4a --model large-v3

# 不上传 Google Docs
python meeting_minutes.py /path/to/audio.m4a --no-upload

# 指定输出目录
python meeting_minutes.py /path/to/audio.m4a --output-dir ./output
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `audio` | 音频文件路径 | 必填 |
| `--notes` | 人工笔记文件路径 | 可选 |
| `--model` | Whisper 模型 | turbo |
| `--no-upload` | 不上传 Google Docs | False |
| `--output-dir` | 输出目录 | 音频文件同目录 |

### 支持的音频格式

- `.m4a`（Zoom 默认格式）
- `.mp3`
- `.wav`
- `.mp4`

### 可用模型

| 模型 | 说明 |
|------|------|
| `tiny` | 最快，精度较低 |
| `base` | 快速，基础精度 |
| `small` | 平衡 |
| `medium` | 较好精度 |
| `large-v3` | 最佳精度 |
| `turbo` | 推荐：最佳质量 + 速度平衡 |

## 性能对比

| 对比项 | OpenAI Whisper (CPU) | MLX-Whisper (Metal GPU) |
|--------|---------------------|------------------------|
| 处理速度 | ~0.87x 实时 | ~10-20x 实时 |
| 56分钟音频耗时 | ~65 分钟 | ~3-6 分钟 |
| 加速比 | 基准 | **快 12-20 倍** |

## 输出示例

生成的会议纪要包含：

1. **会议背景与目的**
2. **核心议题讨论** - 详细记录各方观点和分歧
3. **关键决策汇总** - 表格形式
4. **待办事项（Action Items）**
5. **开放问题与后续讨论**
6. **会议小结**
7. **原始转录**

## 许可证

MIT License