# Authored By Certified Coders 2026
# Module: Action/Reaction Core Logic (Misc)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from nekosbest import Client as NekoClient
import config
from AnnieXMedia import app

neko_client = NekoClient()

# التأكد من تعريف المتغير لتجنب الأخطاء عند البدء
if not hasattr(config, "ANIMATION_MODE"):
    config.ANIMATION_MODE = False

# خريطة الأوامر
COMMANDS_MAP = {
    "لكم": {"api": "punch", "act": "لـكـم"},
    "بوكس": {"api": "punch", "act": "لـكـم"},
    "كف": {"api": "slap", "act": "صـفـع"},
    "صفع": {"api": "slap", "act": "صـفـع"},
    "حضن": {"api": "hug", "act": "احـتـضـان"},
    "عض": {"api": "bite", "act": "عـض"},
    "بوس": {"api": "kiss", "act": "تـقـبـيـل"},
    "كفك": {"api": "highfive", "act": "مـصـافـحـة"},
    "قتل": {"api": "shoot", "act": "اطـلاق الـنـار عـلـى"},
    "رقص": {"api": "dance", "act": "الـرقـص مـع"},
    "سعيد": {"api": "happy", "act": "سـعـيـد بـ"},
    "طبطب": {"api": "pat", "act": "الـطـبـطـبـة عـلـى"},
    "نعم": {"api": "nod", "act": "اواكـف"},
    "لا": {"api": "nope", "act": "ارفـض"},
    "اكل": {"api": "feed", "act": "اطـعـام"},
    "ملل": {"api": "bored", "act": "يـشـعـر بـالـمـلـل مـن"},
    "تفكير": {"api": "think", "act": "يـفـكـر فـي"},
    "خجل": {"api": "blush", "act": "خـجـل مـن"},
    "غمز": {"api": "wink", "act": "غـمـز لـ"},
    "باي": {"api": "wave", "act": "الـتـلـويـح لـ"},
    "نكز": {"api": "poke", "act": "نـكـز"},
    "نوم": {"api": "sleep", "act": "نـام بـجـانـب"},
    "ضحك": {"api": "laugh", "act": "ضـحـك عـلـى"}
}

def md_escape(text: str) -> str:
    return text.replace('[', '\\[').replace(']', '\\]')

async def get_animation(action: str):
    try:
        result = await neko_client.get_image(action)
        return result.url
    except Exception as e:
        print(f"NekoClient error: {e}")
        return None

# ─── معالجة أوامر التفاعل ───

@app.on_message(filters.command(list(COMMANDS_MAP.keys()), prefixes=["", "/", "!", "."]) & ~filters.forwarded & ~filters.via_bot)
async def animation_command(client: Client, message: Message):
    # التحقق من الحالة عبر ملف config المشترك
    if not config.ANIMATION_MODE:
        return await message.reply_text("الوضع متوقف مؤقتا .")

    command = message.command[0]

    if command not in COMMANDS_MAP:
        return 

    api_term = COMMANDS_MAP[command]["api"]
    action_text = COMMANDS_MAP[command]["act"]

    gif_url = await get_animation(api_term)
    if not gif_url:
        return await message.reply_text("حدث خطأ اثناء جلب الصورة المتحركة.")

    sender_name = md_escape(message.from_user.first_name)
    sender = f"[{sender_name}](tg://user?id={message.from_user.id})"

    if message.reply_to_message:
        target_name = md_escape(message.reply_to_message.from_user.first_name)
        target = f"[{target_name}](tg://user?id={message.reply_to_message.from_user.id})"
    else:
        target = "نـفـسـه"

    caption = f"**قـام {sender} بـ {action_text} {target}**"

    await message.reply_animation(
        animation=gif_url,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )
