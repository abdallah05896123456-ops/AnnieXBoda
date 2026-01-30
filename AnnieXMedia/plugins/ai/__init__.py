# plugins/ai/__init__.py
# Authored By Certified Coders © 2026
# AI Plugin Package Initializer

"""
AI Plugin Package
-----------------
This package contains:
- prompts.py   : System & behavior prompts
- engine.py    : G4F streaming engine (Cloud-based)
- handlers.py  : Pyrogram handlers & callbacks

Importing this package automatically
registers all AI handlers.
"""

# تحميل البرومبتات أولا
from . import prompts  # noqa: F401

# تحميل محرك الذكاء (الـ API اللي باقي المشروع بيستخدمه)
from .engine import (
    AI,
    ENGINE,
    ask_ollama_stream,
    clear_all_memory,
    clear_user_memory,
    toggle_model,
    set_light_model,
    set_heavy_model,
    get_model,
    get_current_model,
)  # noqa: F401

# تحميل الهاندلرز (بيسجل الأوامر والكولباكس)
from . import handlers  # noqa: F401

__all__ = [
    "prompts",
    "AI",
    "ENGINE",
    "ask_ollama_stream",
    "clear_all_memory",
    "clear_user_memory",
    "toggle_model",
    "set_light_model",
    "set_heavy_model",
    "get_model",
    "get_current_model",
    "handlers",
]
