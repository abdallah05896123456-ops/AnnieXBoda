from typing import Union
from pyrogram.types import Message
from AnnieXMedia.utils.youtube import YouTubeAPI

class YouTube:
    def __init__(self):
        self.yt = YouTubeAPI()

    async def valid(self, link: str):
        return await self.yt.exists(link)

    async def track(self, link: str, userid: str = None):
        return await self.yt.track(link, userid)

    async def playlist(self, link: str, limit: int, userid: int):
        return await self.yt.playlist(link, limit, userid)

    async def slider(self, link: str, query_type: int):
        return await self.yt.slider(link, query_type)

    async def download(self, link: str, mystic: Message, video: Union[bool, str] = None):
        return await self.yt.download(link, mystic, video=video)
