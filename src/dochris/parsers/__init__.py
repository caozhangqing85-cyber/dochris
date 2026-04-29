# 解析器模块

from .code_parser import detect_code_file, extract_from_code
from .doc_parser import detect_document_file, parse_document, parse_office_document
from .pdf_parser import parse_pdf

__all__ = [
    # pdf_parser
    "parse_pdf",
    # doc_parser
    "detect_document_file",
    "parse_document",
    "parse_office_document",
    # code_parser
    "detect_code_file",
    "extract_from_code",
]
