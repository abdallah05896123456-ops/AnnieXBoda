# Authored By Certified Coders © 2026
# TITAN AI SYSTEM - SUPREME DETAILED EDITION
# Optimized for 16-Core Docker Environment | Multi-Provider Failover

import asyncio, os, time, re
from pyrogram import filters, enums
from pyrogram.types import Message
from g4f.client import AsyncClient
from g4f.Provider import DuckDuckGo, Blackbox, Bing, You, Liaobots

# استيراد كائن البوت والكونفنج لضمان الربط البرمجي الكامل
from AnnieXMedia import app
import config

# ==========================================================
# الإعـدادات الـتـقـنـيـة والـسـيـطـرة
# ==========================================================

# جلب أيدي المطور (يدعم القائمة أو الرقم المفرد)
OWNER_ID = config.OWNER_ID if isinstance(config.OWNER_ID, list) else [config.OWNER_ID]

AI_STATUS = True        # حالة النظام العامة
LIMIT_STATUS = True     # نظام القيود اليومية
DAILY_LIMIT = 100       # حد الاستخدام للسيرفرات القوية
AI_GROUP = 30           # مجموعة المعالجة (لتجنب التعارض مع الميوزك والحماية)

# مخازن البيانات الرقمية (تخزين لحظي في الرام لسرعة الوصول)
user_context = {}         # حفظ سياق المحادثات لضمان الفهم العميق
usage_counter = {}        # تتبع عدد الاستخدامات لكل مستخدم
permanent_users = set()   # قائمة المستخدمين في وضع الاستجابة الدائمة
unlocked_users = set()    # المستخدمين المستثنين من القيود

# تهيئة عميل الذكاء الاصطناعي
ai_client = AsyncClient()

# ==========================================================
# مـحـرك الـتـفـكـيـر والـمـعـالـجـة (Logic Core)
# ==========================================================

async def fetch_ai_logic(user_id, prompt, image_path=None):
    """المحرك الرئيسي: معالجة متوازية مع نظام تبديل الخوادم اللحظي"""
    if user_id not in user_context:
        user_context[user_id] = []
        
    # التعليمات البرمجية الصارمة لإجبار المحرك على التفصيل الممل
    system_instruction = (
        "أنت نظام ذكاء اصطناعي فائق التطور، العقل المدبر لسورس AnnieXMedia. "
        "قواعدك الصارمة: "
        "1. يجب أن تكون إجاباتك مطولة جداً، مفصلة، وشاملة لكل جوانب الموضوع. "
        "2. اشرح الأسباب والنتائج بأسلوب تقني وعلمي دقيق. "
        "3. استخدم لغة عربية قوية وفصحى، أو عامية مصرية ذكية إذا استدعى الأمر. "
        "4. في حال وجود صور، قم بتحليل كل سنتي فيها واستخرج أدق التفاصيل المخفية."
    )
    
    messages = [{"role": "system", "content": system_instruction}] + \
               user_context[user_id] + [{"role": "user", "content": prompt}]
    
    # قائمة المزودين: نظام Failover سداسي لضمان عدم الفشل أبداً
    providers = [DuckDuckGo, Blackbox, Bing, You, Liaobots]
    
    for provider in providers:
        try:
            response = await ai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                provider=provider,
                image=open(image_path, "rb") if image_path else None,
                timeout=20 # وقت كافٍ لتوليد الردود الضخمة
            )
            answer = response.choices[0].message.content.strip()
            
            # إدارة الذاكرة: حفظ آخر 10 تفاعلات لتعميق سياق الحوار
            user_context[user_id].append({"role": "user", "content": prompt})
            user_context[user_id].append({"role": "assistant", "content": answer})
            user_context[user_id] = user_context[user_id][-10:]
            
            return answer
        except:
            continue # الانتقال للمزود التالي في حال تعطل الحالي
    return None

# ==========================================================
# أوامـر الـتـحـكـم والـإدارة (لـلـمـطـور)
# ==========================================================

@app.on_message(filters.regex(r"^(قفل|فتح) الذكاء$") & filters.user(OWNER_ID))
async def toggle_ai_global(_, m: Message):
    global AI_STATUS
    AI_STATUS = "فتح" in m.text
    await m.reply_text(f"**تـم {'تـفـعـيـل' if AI_STATUS else 'تـعـطـيـل'} مـحـرك الـذكـاء الاصـطـنـاعـي.**")

@app.on_message(filters.regex(r"^ليمت (\d+)$") & filters.user(OWNER_ID))
async def change_limit_val(_, m: Message):
    global DAILY_LIMIT
    DAILY_LIMIT = int(m.matches[0].group(1))
    await m.reply_text(f"**تـم تـحـديـث الـلـيـمـت الـيـومـي لـيـصـبـح: {DAILY_LIMIT}**")

@app.on_message(filters.regex(r"^تنظيف الذاكرة$") & filters.user(OWNER_ID))
async def purge_all_context(_, m: Message):
    user_context.clear()
    await m.reply_text("**تـم تـطـهـيـر ذاكـرة الـنـظـام بـالـكـامـل.**")

@app.on_message(filters.regex(r"^(تصفير|مسح)$") & filters.private)
async def reset_user_chat(_, m: Message):
    user_context.pop(m.from_user.id, None)
    await m.reply_text("**تـم مـسـح سـجـل مـحـادثـاتـك بـنـجـاح.**")

# ==========================================================
# الـمـعـالـج الـمـركـزي والـتـفـاعـل الـفـوري
# ==========================================================

@app.on_message((filters.text | filters.photo) & ~filters.bot, group=AI_GROUP)
async def supreme_ai_handler(bot, m: Message):
    if not AI_STATUS and m.from_user.id not in OWNER_ID: return
    
    uid = m.from_user.id
    raw_text = m.text or m.caption or ""
    
    # نظام الكشف الذكي (يدعم ذكاء، ai، شات، بوت) بدون بادئة
    match = re.match(r"^(ذكاء|ai|شات|بوت|bot|يا ذكاء)(\s|$)", raw_text, re.IGNORECASE)
    if not match and uid not in permanent_users: return

    # فحص قيود الاستخدام اليومية
    now = time.time()
    usage_counter[uid] = [t for t in usage_counter.get(uid, []) if now - t < 86400]
    if LIMIT_STATUS and len(usage_counter[uid]) >= DAILY_LIMIT and uid not in OWNER_ID:
        return await m.reply_text(f"**انـتـهى حـدك الـيـومـي مـن الـأسـئـلـة ({DAILY_LIMIT}).**")

    # استخلاص نص السؤال
    prompt = raw_text[match.end():].strip() if match else raw_text
    if not prompt and not m.photo: return

    # تحميل الصور ومعالجتها (Vision)
    image_path = await m.download() if m.photo else None
    await bot.send_chat_action(m.chat.id, enums.ChatAction.TYPING)
    
    status_msg = await m.reply("**جـاري الـتـفـكـيـر بـعـمـق وتـولـيـد الـرد...**")
    start_time = time.time()
    
    # طلب الرد من المحرك
    response = await fetch_ai_logic(uid, prompt, image_path)
    
    if image_path: os.remove(image_path)
    
    if response:
        usage_counter[uid].append(time.time())
        speed = round(time.time() - start_time, 1)
        # تسليم الرد النهائي مع زمن المعالجة
        await status_msg.edit(f"{response}\n\n⏱ `{speed}s` | **AnnieX-Core Intelligence**")
    else:
        await status_msg.edit("**فـشـل الـمـحـرك فـي الـرد نـتـيـجـة ضـغـط الـطـلـبـات، كـرر سـؤالـك.**")
