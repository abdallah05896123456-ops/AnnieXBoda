# Authored By Certified Coders © 2025
import re
from typing import Union

import aiohttp
from bs4 import BeautifulSoup
# التعديل تم هنا
from youtubesearchpython.__future__ import VideosSearch


class RessoAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/m.resso.com\/)(.*)$"
        self.base = "https://m.resso.com/"

    async def valid(self, link: str):
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def track(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        
        # تعريف متغيرات مبدئية لتجنب الأخطاء
        title = None
        des = None

        for tag in soup.find_all("meta"):
            if tag.get("property", None) == "og:title":
                title = tag.get("content", None)
            if tag.get("property", None) == "og:description":
                des = tag.get("content", None)
                try:
                    des = des.split("·")[0]
                except:
                    pass
        
        # التأكد من وجود البيانات قبل البحث
        if not title:
            return None

        results = VideosSearch(title, limit=1)
        search_result = await results.next()
        
        if not search_result.get("result"):
            return None

        for result in search_result["result"]:
            title = result["title"]
            ytlink = result["link"]
            vidid = result["id"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            
        track_details = {
            "title": title,
            "link": ytlink,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid
