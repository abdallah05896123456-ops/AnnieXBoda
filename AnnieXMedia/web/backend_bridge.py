# backend_bridge.py
from typing import Optional, List, Any
from fastapi import FastAPI, HTTPException, Body, Query
from pydantic import BaseModel
import traceback

# استيراد التحكم بالستريمز من سورس AnnieXMedia
from AnnieXMedia.core.call import StreamController, _clear_
from AnnieXMedia.utils.database import group_assistant
from AnnieXMedia.misc import db

app = FastAPI(title="AnnieXBoda - Backend Bridge", version="1.0.0")

# ---------- Request models ----------
class PlayRequest(BaseModel):
    chat_id: int
    # بعض الأماكن قد يحتاجوا علم إذا كان فيديو أو ستريم، ولكن play() بالـ Call يعتمد على الـ db داخلياً
    video: Optional[bool] = False

class SkipRequest(BaseModel):
    chat_id: int
    link: str
    video: Optional[bool] = False
    image: Optional[bool] = False

class SeekRequest(BaseModel):
    chat_id: int
    file_path: str
    to_seek: str         # المعامل في سورس: مثال "00:01:23"
    duration: str
    mode: str            # عادة "forward" / "backward" أو ما يقابله بالمشروع

class SpeedRequest(BaseModel):
    chat_id: int
    file_path: str
    speed: float
    playing: List[dict]

class VolumeRequest(BaseModel):
    chat_id: int
    volume: int  # نسبة أو قيمة مقبولة حسب pytgcalls (مثلاً 0-200)

class QueueClearRequest(BaseModel):
    chat_id: int

# ---------- Utilities ----------
def _format_exc(e: Exception) -> str:
    tb = traceback.format_exc()
    return f"{str(e)}\n{tb}"

# ---------- Endpoints ----------
@app.get("/bridge/ping")
async def ping():
    return {"status": "ok", "active_calls_count": len(getattr(StreamController, "active_calls", []))}

@app.get("/bridge/active")
async def active_calls():
    """
    إرجاع قائمة المحادثات التي فيها مكالمات فعّالة
    """
    active = list(getattr(StreamController, "active_calls", []))
    return {"active_calls": active}

@app.post("/bridge/play")
async def play(req: PlayRequest):
    """
    تشغيل المسار الحالي في صفّ التشغيل للمحادثة chat_id.
    يستدعي StreamController.play(assistant_instance, chat_id)
    """
    try:
        assistant = await group_assistant(StreamController, req.chat_id)
        # تمرير الـ assistant الذي ترجعها group_assistant (هو PyTgCalls wrapper في Call)
        await StreamController.play(assistant, req.chat_id)
        return {"status": "playing", "chat_id": req.chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/pause")
async def pause(chat_id: int = Body(..., embed=True)):
    try:
        await StreamController.pause_stream(chat_id)
        return {"status": "paused", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/resume")
async def resume(chat_id: int = Body(..., embed=True)):
    try:
        await StreamController.resume_stream(chat_id)
        return {"status": "resumed", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/mute")
async def mute(chat_id: int = Body(..., embed=True)):
    try:
        await StreamController.mute_stream(chat_id)
        return {"status": "muted", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/unmute")
async def unmute(chat_id: int = Body(..., embed=True)):
    try:
        await StreamController.unmute_stream(chat_id)
        return {"status": "unmuted", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/stop")
async def stop(chat_id: int = Body(..., embed=True)):
    try:
        await StreamController.stop_stream(chat_id)
        return {"status": "stopped", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/force_stop")
async def force_stop(chat_id: int = Body(..., embed=True)):
    try:
        await StreamController.force_stop_stream(chat_id)
        return {"status": "force_stopped", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/skip")
async def skip(req: SkipRequest):
    """
    تخطي العنصر الحالي واستبداله بـ link (إذا قدمته)
    """
    try:
        # واجهة Call.skip_stream(chat_id, link, video, image)
        await StreamController.skip_stream(req.chat_id, req.link, req.video, req.image)
        return {"status": "skipped", "chat_id": req.chat_id, "link": req.link}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/seek")
async def seek(req: SeekRequest):
    """
    تقديم/تأخير داخل ملف تشغيل
    """
    try:
        await StreamController.seek_stream(req.chat_id, req.file_path, req.to_seek, req.duration, req.mode)
        return {"status": "seeked", "chat_id": req.chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/speed")
async def speed(req: SpeedRequest):
    """
    تغيير السرعة. يحتاج قائمة 'playing' كما ينتظرها الدالة في السورس (قائمة dict).
    """
    try:
        await StreamController.speedup_stream(req.chat_id, req.file_path, req.speed, req.playing)
        return {"status": "speed_changed", "chat_id": req.chat_id, "speed": req.speed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.post("/bridge/volume")
async def volume(req: VolumeRequest):
    """
    تغيير مستوى الصوت لمكالمة المجموعة. يستعمل pytgcalls method change_volume_call.
    """
    try:
        assistant = await group_assistant(StreamController, req.chat_id)
        # PyTgCalls method: change_volume_call(chat_id, volume)
        # نستخدمه مباشرة على الـ assistant (الذي يُرجع instance متوافق)
        if not hasattr(assistant, "change_volume_call"):
            # محاولة أخرى: بعض إصدارات توفر method باسم change_volume_call على attribute calls
            try:
                await assistant.change_volume_call(req.chat_id, req.volume)
            except Exception:
                raise HTTPException(status_code=500, detail="Assistant does not expose change_volume_call method")
        else:
            await assistant.change_volume_call(req.chat_id, req.volume)
        return {"status": "volume_set", "chat_id": req.chat_id, "volume": req.volume}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.get("/bridge/queue")
async def get_queue(chat_id: int = Query(..., description="chat id")):
    """
    إعادة قائمة الانتظار (db) الخاصة بالمحادثة.
    """
    try:
        q = db.get(chat_id, [])
        return {"chat_id": chat_id, "queue": q}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))

@app.delete("/bridge/queue")
async def clear_queue(chat_id: int = Query(...)):
    """
    مسح صف التشغيل واستدعاء _clear_ من السورس.
    """
    try:
        await _clear_(chat_id)
        return {"status": "queue_cleared", "chat_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_exc(e))
