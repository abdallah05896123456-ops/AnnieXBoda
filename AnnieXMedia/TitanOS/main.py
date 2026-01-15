import sys
import os

# تصحيح مسار الاستيراد عشان يشتغل يدوي أو تلقائي
try:
    from . import web_srv
except ImportError:
    import web_srv

def init():
    # ... (باقي الكود زي ما هو)
