# 摄入文件

摄入是 dochris 工作流的第一步，将源文件链接到知识库工作区。

## 工作原理

```
materials/          ← 源目录
├── paper.pdf
├── notes.md
└── lecture.mp3

→ kb ingest →

workspace/
├── raw/
│   ├── paper.pdf → symlink
│   ├── notes.md → symlink
│   └── lecture.mp3 → symlink
└── manifests/
    ├── paper.json
    ├── notes.json
    └── lecture.json
```

## 支持的文件类型

| 类型 | 格式 |
|------|------|
| 文档 | PDF, Markdown, TXT, Word (.docx) |
| 音频 | MP3, WAV, M4A, FLAC |
| 代码 | Python, JavaScript, 等 |
| 电子书 | EPUB |
| 其他 | 图片（OCR） |

## Manifest 结构

每个文件生成一个 manifest：

```json
{
  "id": "SRC-0001",
  "filename": "paper.pdf",
  "source_path": "/path/to/materials/paper.pdf",
  "file_type": "pdf",
  "status": "pending",
  "created_at": "2026-05-01T12:00:00",
  "file_size": 1024000
}
```

## 状态流转

```
pending → compiled → promoted
              ↓
           failed → (retry) → compiled
```
