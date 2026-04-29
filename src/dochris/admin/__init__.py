#!/usr/bin/env python3
"""
Admin 脚本包 - 知识库维护和管理脚本

此包包含用于维护和管理知识库的脚本，通常由管理员或高级用户使用。

可用的脚本:
- batch_promote: 批量晋升知识库产物
- index_knowledge: 向量索引脚本
- ocr_failed_pdf: OCR 处理失败的 PDF
- recompile: 重新编译失败的文档
- recompile_missing_concepts: 重新编译缺失的概念
- sanitize_sensitive_words: 清理敏感词
- transcribe_failed_audio: 转录失败的音频

使用示例:
    from dochris.admin import batch_promote
    batch_promote.batch_promote_to_wiki(workspace, min_score=85)
"""

# 导出主要入口函数（可选，根据需要添加）
# from dochris.admin.batch_promote import batch_promote_to_wiki
# from dochris.admin.recompile import recompile

__all__ = []
