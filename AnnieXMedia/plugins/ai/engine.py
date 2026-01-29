# plugins/ai/engine.py
# Ollama AI Engine (Streaming) — Developed / Robust Version
# Authored By Certified Coders © 2026
"""
وظيفة الملف:
- يوفر دالة ask_ollama_stream القابلة للاستدعاء من handlers.py
- يدعم Streaming (مباشر) و Non-stream (طلب واحد)
- يقبل callback on_update ليعرض أجزاء الرد فور وصولها
- متوافق مع مسارات Ollama الشائعة (/api/chat و /api/generate)
- لا يغير واجهة الاستدعاء المتوقعة من بقية السورس (user_id, prompt, on_update)
"""

import aiohttp
import asyncio
import json
import os
import logging
from typing import Optional, Callable, Any

# إعدادات افتراضية — يمكن تغييرها عبر ENV
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
DEFAULT_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))  # ثانية

logger = logging.getLogger("AnnieX_AI_Engine")


def _extract_text_from_response(obj: Any) -> str:
    """
    محاولة موثوقة لاستخراج نص من أشكال JSON مختلفة قد تعيده خدمة Ollama.
    تعيد سلسلة فارغة إذا لم تعثر على نص واضح.
    """
    try:
        if obj is None:
            return ""

        # إذا كان سترينغ
        if isinstance(obj, str):
            return obj.strip()

        # dict محتمل
        if isinstance(obj, dict):
            # شكل شائع: { "message": { "content": "..." } }
            if "message" in obj and isinstance(obj["message"], dict):
                mc = obj["message"].get("content")
                if isinstance(mc, str) and mc.strip():
                    return mc.strip()
                # أحياناً content قائمة أجزاء
                if isinstance(mc, list):
                    parts = []
                    for p in mc:
                        if isinstance(p, str) and p.strip():
                            parts.append(p.strip())
                        elif isinstance(p, dict):
                            t = p.get("text") or p.get("content")
                            if isinstance(t, str) and t.strip():
                                parts.append(t.strip())
                    return " ".join(parts).strip()

            # شكل بديل: { "response": "..." }
            for key in ("response", "output", "text", "result"):
                if key in obj and isinstance(obj[key], str) and obj[key].strip():
                    return obj[key].strip()

            # choices -> [{ "text": "...", "message": {...} }]
            if "choices" in obj and isinstance(obj["choices"], list) and obj["choices"]:
                first = obj["choices"][0]
                if isinstance(first, dict):
                    txt = first.get("text")
                    if isinstance(txt, str) and txt.strip():
                        return txt.strip()
                    # nested message
                    msg = first.get("message") or first.get("delta") or first.get("output")
                    if isinstance(msg, dict):
                        cont = msg.get("content") or msg.get("text")
                        if isinstance(cont, str) and cont.strip():
                            return cont.strip()

            # كحل أخير: ابحث داخل القيم عن أول سترينغ
            def find_any_string(o):
                if isinstance(o, str) and o.strip():
                    return o.strip()
                if isinstance(o, dict):
                    for v in o.values():
                        s = find_any_string(v)
                        if s:
                            return s
                if isinstance(o, list):
                    for it in o:
                        s = find_any_string(it)
                        if s:
                            return s
                return None

            found = find_any_string(obj)
            return found or ""

    except Exception as e:
        logger.debug("extract_text error: %s", e, exc_info=True)

    return ""


async def ask_ollama_stream(
    user_id: int,
    prompt: str,
    on_update: Optional[Callable[[str], Any]] = None,
    system_prompt: Optional[str] = None,
    stream: bool = True,
    timeout: Optional[int] = None,
) -> str:
    """
    طلب للموديل عبر Ollama مع دعم الاستريم و callback للتحديثات الجزئية.

    واجهة الاستخدام (متوافقة مع handlers.py):
        reply = await ask_ollama_stream(user_id, prompt, on_update=on_update)

    المعاملات:
    - user_id: رقم المستخدم (يُمرَّر للتماشي مع الواجهة، لا يُستخدم داخلياً هنا)
    - prompt: نص المستخدم
    - on_update: دالة async تُستدعى مع نص جزئي كلما وصل (awaitable)
    - system_prompt: نص system (اختياري). إذا لم يُمرّر، ترسل طلب بسيط للموديل
    - stream: إذا True يحاول استخدام واجهة الاستريم، وإلا سيأخذ الرد الكامل
    - timeout: وقت المهلة بالثواني (افتراضي DEFAULT_TIMEOUT)

    ترجع النص النهائي (string).
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    # تهيئة مسار الـ API: نجرب /api/chat أولًا، ثم /api/generate كـ fallback
    host = OLLAMA_HOST.rstrip("/")
    endpoints = [f"{host}/api/chat", f"{host}/api/generate", f"{host}/api/create"]

    # بناء الـ payload بأسلوب مدروس (messages أو prompt)
    if system_prompt:
        use_messages = True
    else:
        # إذا لم يكن هناك system_prompt، بعض نسخ Ollama تقبل 'prompt' مباشرة
        use_messages = True  # نستخدم messages دائماً لثبات الشكل

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        # رسالة system افتراضية خفيفة لتشجيع الرد العربي (يمكن تغييره عبر env)
        default_sys = os.getenv("OLLAMA_SYSTEM_PROMPT", "").strip()
        if default_sys:
            messages.append({"role": "system", "content": default_sys})
    messages.append({"role": "user", "content": prompt})

    payload_messages = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": stream,
        # بعض إعدادات مساعدة (يمكن تعديلها عبر env)
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMP", "0.2")),
            "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", "2048")),
        },
    }

    payload_prompt = {
        "model": MODEL_NAME,
        "prompt": (system_prompt + "\n\n" if system_prompt else "") + prompt,
        "stream": stream,
        "options": payload_messages["options"],
    }

    client_timeout = aiohttp.ClientTimeout(total=timeout)

    last_text = ""
    final_text = ""

    # نحاول على مجموعة endpoints متوقعين حتى نحصل على رد
    for endpoint in endpoints:
        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                # نختار payload المناسب حسب endpoint (chat يتوقع messages عادة)
                body = payload_messages if endpoint.endswith("/api/chat") or endpoint.endswith("/api/create") else payload_prompt

                async with session.post(endpoint, json=body) as resp:
                    # حالة خطأ بسيطة
                    if resp.status >= 400:
                        # خذ نص الخطأ جزئياً ثم جرب endpoint آخر
                        try:
                            txt = await resp.text()
                        except Exception:
                            txt = f"HTTP {resp.status}"
                        logger.warning("Ollama returned status %s for %s: %s", resp.status, endpoint, txt[:200])
                        # جرب التالي
                        continue

                    # لو مطلوب الاستريم: اقرأ chunks
                    if stream:
                        # نجمع البافر لأن بعض الـ endpoints يرجعون خطوط JSON مفصولة بسطر جديد
                        buf = ""
                        async for chunk in resp.content.iter_any():
                            if not chunk:
                                continue
                            try:
                                decoded = chunk.decode("utf-8", errors="ignore")
                            except Exception:
                                decoded = str(chunk)
                            buf += decoded

                            # حاول تقسيم خطوط مكتملة
                            lines = buf.splitlines()
                            # إذا آخر جزء غير مكتمل نحتفظ به
                            if not buf.endswith("\n"):
                                buf = lines.pop() if lines else buf
                            else:
                                buf = ""

                            updated = False
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue
                                # أحياناً يأتي بتنسيق SSE: data: {...}
                                if line.startswith("data:"):
                                    line = line[len("data:"):].strip()
                                if line in ("[DONE]", ""):
                                    continue

                                # حاول تحليل JSON
                                extracted = ""
                                try:
                                    parsed = json.loads(line)
                                    extracted = _extract_text_from_response(parsed)
                                except Exception:
                                    # ليس JSON — اعتبر السطر نصًا خامًا
                                    extracted = line

                                if not extracted:
                                    continue

                                # Append smartly: تجنب التكرار
                                if final_text and extracted.startswith(final_text):
                                    new_part = extracted[len(final_text):]
                                else:
                                    # لو يبدو النص تكراري لكن ليس prefix، استبدل نهائيًا
                                    new_part = extracted if not final_text else (" " + extracted)

                                if new_part:
                                    final_text = (final_text + new_part).strip()
                                    updated = True

                            if updated and on_update:
                                # استدعاء callback — تجاهل أخطاء callback حتى لا يكسر البث
                                try:
                                    res = on_update(final_text)
                                    if asyncio.iscoroutine(res):
                                        await res
                                except Exception:
                                    logger.debug("on_update callback failed", exc_info=True)

                        # انتهاء الاستريم — إعادة النص النهائي
                        final_text = final_text.strip()
                        if final_text:
                            return final_text
                        # إن لم نحصل على شيء، جرب endpoint آخر
                        continue

                    else:
                        # non-stream: استلم الجسم كله مرة واحدة
                        try:
                            data = await resp.json(content_type=None)
                        except Exception:
                            text_body = await resp.text()
                            # نص خام
                            final_text = (text_body or "").strip()
                            if final_text:
                                return final_text
                            continue

                        final_text = _extract_text_from_response(data).strip()
                        if final_text:
                            return final_text
                        # إن فشلنا: جرب endpoint آخر
                        continue

        except aiohttp.ClientConnectorError as e:
            logger.warning("Connection error to Ollama %s: %s", endpoint, e)
            # حاول التالي
            continue
        except asyncio.TimeoutError:
            logger.warning("Timeout contacting Ollama at %s", endpoint)
            continue
        except Exception as e:
            logger.exception("Unexpected error while contacting Ollama at %s: %s", endpoint, e)
            continue

    # إذا فشل كل شيء: أعد نص فشل معقول لكي لا يكسر الـ caller
    logger.error("All Ollama endpoints failed or returned no usable content.")
    return "حصل خطأ في خدمة الذكاء الصناعي، حاول لاحقاً."
