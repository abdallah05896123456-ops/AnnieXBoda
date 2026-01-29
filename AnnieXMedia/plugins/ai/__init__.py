# plugins/ai/__init__.py
# Authored By Certified Coders © 2026
# AI Plugin Package Initializer

"""
AI Plugin Package
-----------------
This package contains:
- prompts.py   : System & behavior prompts (personality / language / rules)
- engine.py    : Ollama streaming + performance logic
- handlers.py  : Pyrogram message handlers & callbacks

Importing this package will automatically
register all AI-related handlers.
"""

# تحميل البرومبتات (لازم قبل أي استخدام)
from . import prompts  # noqa: F401

# تحميل محرك الذكاء
from .engine import ask_ollama_stream  # noqa: F401

# تحميل الهاندلرز (ده اللي بيسجّل الأوامر فعلياً)
from . import handlers  # noqa: F401

__all__ = [
    "prompts",
    "ask_ollama_stream",
    "handlers",
]
