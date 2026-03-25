# backend/mcp/__init__.py
from .gdocs_tool import append_to_doc
from .gmail_tool import create_draft

__all__ = ["append_to_doc", "create_draft"]
