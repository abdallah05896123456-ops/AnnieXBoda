# Authored By Certified Coders © 2025
from pyrogram import Client

import config

from ..logging import LOGGER

assistants = []
assistantids = []

GROUPS_TO_JOIN = [
    "CertifiedDiscussion",
    "CertifiedCoders",
    "CertifiedCodes",
    "CertifiedDevs",
    "CertifiedNetwork",
]

class Userbot:
    def __init__(self):
        # 🔥 تم إزالة no_updates=True للسماح للمساعد برؤية المكالمات
        self.one = Client(
            "AnnieAssis1",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.two = Client(
            "AnnieAssis2",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.three = Client(
            "AnnieAssis3",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.four = Client(
            "AnnieAssis4",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.five = Client(
            "AnnieAssis5",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING5),
        )

    async def start_assistant(self, client: Client, index: int):
        string_attr = [
            config.STRING1,
            config.STRING2,
            config.STRING3,
            config.STRING4,
            config.STRING5,
        ][index - 1]
        if not string_attr:
            return

        try:
            await client.start()
            for group in GROUPS_TO_JOIN:
                try:
                    await client.join_chat(group)
                except Exception:
                    pass

            assistants.append(index)

            try:
                await client.send_message(
                    config.LOGGER_ID, f"☔ تـم بـدء تـشـغـيـل الـمـسـاعـد {index} بـنـجـاح"
                )
            except Exception:
                LOGGER(__name__).error(
                    f"💝 الـمـسـاعـد {index} لا يـمـكـنـه الـوصـول لـجـروب الـسـجـل.. تـحـقـق مـن الـأذونـات!"
                )
                exit()

            me = await client.get_me()
            client.id, client.name, client.username = me.id, me.first_name, me.username
            assistantids.append(me.id)

            LOGGER(__name__).info(f"☔ تـم تـشـغـيـل الـمـسـاعـد {index} بـهـويـة: {client.name}")

        except Exception as e:
            LOGGER(__name__).error(f"💝 فـشـل فـي بـدء الـمـسـاعـد {index}.. الـخـطـأ: {e}")

    async def start(self):
        LOGGER(__name__).info("💝 جـارٍ بـدء تـشـغـيـل حـسـابـات الـمـسـاعـد...")
        await self.start_assistant(self.one, 1)
        await self.start_assistant(self.two, 2)
        await self.start_assistant(self.three, 3)
        await self.start_assistant(self.four, 4)
        await self.start_assistant(self.five, 5)

    async def stop(self):
        LOGGER(__name__).info("☔ جـارٍ إيـقـاف الـمـسـاعـد...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
            if config.STRING3:
                await self.three.stop()
            if config.STRING4:
                await self.four.stop()
            if config.STRING5:
                await self.five.stop()
        except Exception as e:
            LOGGER(__name__).error(f"💝 خـطـأ أثـنـاء إيـقـاف الـمـسـاعـد: {e}")
