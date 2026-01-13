# Authored By Certified Coders © 2025
import asyncio
import os
import sys

def setup_uvloop():
    """
    وظيفـة هـذه الـدالـة هي تـفـعـيـل مـحـرك uvloop
    الـذي يـجـعـل الـبـوت أسـرع بـمـراحـل في الـمـعـالـجـة.
    """
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("✅ تـم تـفـعـيـل مـحـرك uvloop بـنـجـاح (أداء عـالـي).")
    except ImportError:
        print("⚠️ مـكـتـبـة uvloop غـيـر مـثـبـتـة، سـيـتـم الـعـمـل بـالـنـظـام الافـتـراضـي.")

# 1. تـفـعـيـل الـمـحـرك قـبـل اسـتـدعـاء أي كـود آخـر
setup_uvloop()

# 2. اسـتـدعـاء دالـة الـتـشـغـيـل الـرئـيـسـيـة مـن داخـل الـسـورس
# يـتـم هـذا بـعـد ضـبـط الـ Loop لـضـمـان عـدم حـدوث تـعـارض
from AnnieXMedia.__main__ import init

if __name__ == "__main__":
    print("🚀 جـاري بـدء تـشـغـيـل الـبـوت عـبـر مـلـف run.py ...")
    
    try:
        # 3. الـتـشـغـيـل الآمـن بـاسـتـخـدام asyncio.run
        # هـذه الـطـريـقـة تـنـشـئ Loop واحـد مـوحـد لـكـل عـمـلـيـات الـبـوت
        asyncio.run(init())
        
    except KeyboardInterrupt:
        print("❌ تـم إيـقـاف الـبـوت يـدويـاً (Ctrl+C).")
        
    except Exception as e:
        print(f"❌ حـدث خـطـأ قـاتـل أدى لـتـوقـف الـبـوت: {e}")
