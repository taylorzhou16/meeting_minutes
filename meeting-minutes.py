#!/usr/bin/env python3
"""
Zoom录音转录与会议纪要生成器
使用MLX-Whisper进行GPU加速转录，并保存到Google Docs（支持真正的表格）

关键：
1. 纪要必须完整、详细
2. 表格从后往前填充避免索引问题
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Google Docs API
try:
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# MLX-Whisper
try:
    import mlx_whisper
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

# Constants
SCOPES = ['https://www.googleapis.com/auth/documents']
CREDENTIALS_DIR = Path.home() / '.credentials'
CLIENT_SECRET_FILE = CREDENTIALS_DIR / 'google_client_secret.json'
TOKEN_FILE = CREDENTIALS_DIR / 'google_docs_token.pkl'

# 可用的MLX Whisper模型
MLX_MODELS = {
    'tiny': 'mlx-community/whisper-tiny',
    'base': 'mlx-community/whisper-base',
    'small': 'mlx-community/whisper-small',
    'medium': 'mlx-community/whisper-medium',
    'large': 'mlx-community/whisper-large-v3',
    'large-v3': 'mlx-community/whisper-large-v3',
    'turbo': 'mlx-community/whisper-large-v3-turbo',
    'large-v3-turbo': 'mlx-community/whisper-large-v3-turbo',
}


def log(message, level='INFO'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)


def output_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def check_dependencies():
    issues = []
    if not MLX_AVAILABLE:
        issues.append("mlx-whisper未安装，请运行: pip install mlx-whisper")
    return issues


def transcribe_audio(audio_path: str, model: str = 'turbo') -> dict:
    log(f"开始转录: {audio_path}")
    model_path = MLX_MODELS.get(model, MLX_MODELS['turbo'])
    result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=model_path)
    log(f"转录完成，检测语言: {result.get('language', 'unknown')}")
    return result


def get_google_credentials():
    if not GOOGLE_API_AVAILABLE:
        raise ImportError("Google API库未安装")

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    creds = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log("刷新Google认证token...")
            creds.refresh(Request())
        else:
            if CLIENT_SECRET_FILE.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRET_FILE), SCOPES)
            else:
                raise ValueError(
                    "未找到Google OAuth配置。\n"
                    "请将OAuth客户端JSON保存到: ~/.credentials/google_client_secret.json"
                )
            log("请在浏览器中完成Google账号授权...")
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)

    return creds


class GoogleDocsBuilder:
    """Google Docs文档构建器，支持真正的表格"""

    def __init__(self, title: str):
        self.service = build('docs', 'v1', credentials=get_google_credentials())
        self.doc = self.service.documents().create(body={'title': title}).execute()
        self.doc_id = self.doc['documentId']
        log(f"文档已创建，ID: {self.doc_id}")

    def insert_text_at_start(self, text: str):
        """在文档开头插入文本"""
        self.service.documents().batchUpdate(
            documentId=self.doc_id,
            body={'requests': [{'insertText': {'location': {'index': 1}, 'text': text}}]}
        ).execute()

    def append_text(self, text: str):
        """在文档末尾追加文本"""
        doc = self.service.documents().get(documentId=self.doc_id).execute()
        end_index = doc['body']['content'][-1]['endIndex']
        self.service.documents().batchUpdate(
            documentId=self.doc_id,
            body={'requests': [{'insertText': {'location': {'index': end_index - 1}, 'text': text}}]}
        ).execute()

    def append_table(self, data: list):
        """
        在文档末尾追加表格并填充数据
        关键：从后往前填充，使用最后一个表格
        """
        rows = len(data)
        cols = len(data[0]) if rows > 0 else 0

        # 创建空表格
        self.service.documents().batchUpdate(
            documentId=self.doc_id,
            body={'requests': [{
                'insertTable': {
                    'rows': rows,
                    'columns': cols,
                    'endOfSegmentLocation': {'segmentId': ''}
                }
            }]}
        ).execute()

        # 从后往前填充（关键！）
        for row_idx in range(rows - 1, -1, -1):
            # 每次重新获取文档，找到最后一个表格
            doc = self.service.documents().get(documentId=self.doc_id).execute()
            tables = [c for c in doc['body']['content'] if 'table' in c]
            table = tables[-1]['table']  # 使用最后一个表格
            row = table['tableRows'][row_idx]

            for col_idx in range(cols - 1, -1, -1):
                cell = row['tableCells'][col_idx]

                for cell_content in cell.get('content', []):
                    if 'paragraph' in cell_content:
                        para_elements = cell_content['paragraph'].get('elements', [])
                        para_start = para_elements[0]['startIndex'] if para_elements else cell_content['startIndex']

                        self.service.documents().batchUpdate(
                            documentId=self.doc_id,
                            body={'requests': [{
                                'insertText': {
                                    'location': {'index': para_start},
                                    'text': data[row_idx][col_idx]
                                }
                            }]}
                        ).execute()
                        break

        log(f"表格创建完成 ({rows}行 x {cols}列)")

    def get_url(self) -> str:
        return f'https://docs.google.com/document/d/{self.doc_id}/edit'


def main():
    parser = argparse.ArgumentParser(description='Zoom录音转录与会议纪要生成器')
    parser.add_argument('audio', help='音频文件路径')
    parser.add_argument('--notes', help='人工笔记文件路径')
    parser.add_argument('--model', default='turbo', choices=list(MLX_MODELS.keys()))
    parser.add_argument('--no-upload', action='store_true', help='不上传Google Docs')
    parser.add_argument('--output-dir', help='输出目录')

    args = parser.parse_args()

    # 检查依赖
    issues = check_dependencies()
    if issues:
        for issue in issues:
            log(issue, 'ERROR')
        sys.exit(1)

    # 检查文件
    audio_path = Path(args.audio)
    if not audio_path.exists():
        log(f"文件不存在: {audio_path}", 'ERROR')
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else audio_path.parent

    # 读取人工笔记（如有）
    notes_content = None
    if args.notes:
        notes_path = Path(args.notes)
        if notes_path.exists():
            with open(notes_path, 'r', encoding='utf-8') as f:
                notes_content = f.read()
            log(f"已读取人工笔记: {notes_path}")

    # 转录
    log("开始转录音频...")
    result = transcribe_audio(str(audio_path), args.model)
    transcript = result.get('text', '').strip()

    # 保存转录文件
    transcript_file = output_dir / f"{audio_path.stem}_transcript.txt"
    with open(transcript_file, 'w', encoding='utf-8') as f:
        f.write(transcript)
    log(f"转录文件已保存: {transcript_file}")

    # 输出结果
    output = {
        'status': 'success',
        'audio_file': str(audio_path),
        'transcript_file': str(transcript_file),
        'language': result.get('language', 'unknown'),
        'model': args.model,
        'transcript_length': len(transcript),
        'has_notes': notes_content is not None,
    }

    if not args.no_upload:
        try:
            title = f"会议纪要 - {audio_path.stem}"
            builder = GoogleDocsBuilder(title)

            # 先创建表格占位
            builder.append_table([
                ['说明', '内容'],
                ['状态', '初始模板，待Claude生成详细内容'],
                ['转录长度', f'{len(transcript)} 字符'],
            ])

            # 在表格前插入标题
            builder.insert_text_at_start(f'''会议纪要 - {audio_path.stem}

📅 日期：{datetime.now().strftime('%Y-%m-%d')}
🎯 音频文件：{audio_path.name}
⏱️ 语言：{result.get('language', 'unknown')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 说明

这是一个初始模板。请使用Claude生成详细的会议纪要，包括：
- 完整的议题讨论记录
- 详细的观点和分歧
- 明确的结论和决策
- 具体的待办事项

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

''')

            # 在末尾添加原始转录
            builder.append_text(f'''
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【原始转录】

{transcript}

---
🤖 Generated by Meeting Minutes Skill (MLX-Whisper)
''')

            output['google_doc_url'] = builder.get_url()
            output['google_doc_id'] = builder.doc_id
            log(f"Google Doc已创建: {builder.get_url()}")
        except Exception as e:
            log(f"创建Google Doc失败: {e}", 'ERROR')
            output['google_doc_error'] = str(e)

    output_json(output)


if __name__ == '__main__':
    main()