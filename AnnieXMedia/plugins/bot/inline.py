# Authored By Certified Coders © 2025
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
)
from youtubesearchpython import VideosSearch

from AnnieXMedia.utils.inlinequery import answer
from config import BANNED_USERS
from AnnieXMedia import app


@app.on_inline_query(~BANNED_USERS)
async def inline_query_handler(client, query):
    text = query.query.strip().lower()
    answers = []
    if text.strip() == "":
        try:
            await client.answer_inline_query(query.id, results=answer, cache_time=10)
        except:
            return
    else:
        # البحث بالنظام العادي (بدون aio/await)
        a = VideosSearch(text, limit=20)
        result = a.result().get("result")
        
        for x in range(15):
            try:
                title = (result[x]["title"]).title()
                duration = result[x]["duration"]
                views = result[x]["viewCount"]["short"]
                thumbnail = result[x]["thumbnails"][0]["url"].split("?")[0]
                channellink = result[x]["channel"]["link"]
                channel = result[x]["channel"]["name"]
                link = result[x]["link"]
                published = result[x]["publishedTime"]
                
                # وصف مختصر يظهر في قائمة الاختيارات
                description = f"{channel} | {duration} دقيقة | {views} مشاهدة"
                
                buttons = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="يـوتـيـوب 🍒",
                                url=link,
                            )
                        ],
                    ]
                )
                
                # الرسالة المطولة والمنسقة
                searched_text = f"""
☔ <b>الـعـنـوان :</b> <a href="{link}">{title}</a>

🤍 <b>الـمـدة :</b> {duration} دقـيـقـة
🍒 <b>الـمـشـاهـدات :</b> <code>{views}</code>
💞 <b>الـقـنـاة :</b> <a href="{channellink}">{channel}</a>
🫶 <b>تـاريـخ الـنـشـر :</b> {published}

<b>ـــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــــ</b>
<b>➻ بـواسـطـة : {app.name} </b>"""
                
                answers.append(
                    InlineQueryResultPhoto(
                        photo_url=thumbnail,
                        title=title,
                        thumb_url=thumbnail,
                        description=description,
                        caption=searched_text,
                        reply_markup=buttons,
                    )
                )
            except IndexError:
                break
            except Exception:
                continue
                
        try:
            return await client.answer_inline_query(query.id, results=answers)
        except:
            return
