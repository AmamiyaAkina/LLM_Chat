import base64
import mimetypes
import os
import requests
import asyncio
import re
from hoshino import Service

sv = Service('llm_chat', enable_on_default=True)

# ====== 配置 ======
CONFIG = {
    "BASE_URL": "http://macbook:1234",
    "MODEL": "qwen3-vl-8b",
    "MAX_HISTORY": 10,
    "REQUEST_TIMEOUT": 60
}

VISION_MODEL_KEYWORDS = (
    "vl",
    "vision",
    "multimodal",
    "multi-modal",
    "mm",
    "gemma-3-vision",
    "llama-3.2-vision",
    "qwen2.5-vl",
    "qwen3-vl",
)

sessions = {}

# ====== 工具函数 ======
def get_session_id(ev):
    if ev.detail_type == 'group':
        return f"group_{ev.group_id}"
    return f"user_{ev.user_id}"


def get_model_info():
    try:
        resp = requests.get(f"{CONFIG['BASE_URL']}/v1/models")
        data = resp.json()
        models = data.get("data", [])
        if models:
            return models[0].get("id", "未知模型")
        return "未加载模型"
    except Exception as e:
        return f"获取失败: {e}"


def safe_send_text(text: str) -> str:
    if not text:
        return "（模型没有返回内容）"

    text = str(text)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    text = text.replace("[", "【").replace("]", "】")
    return text[:1000].strip()


def extract_message_parts(message):
    text_parts = []
    image_parts = []

    for segment in message:
        if segment.type == "text":
            text_parts.append(segment.data.get("text", ""))
        elif segment.type == "image":
            image_parts.append(dict(segment.data))

    return "".join(text_parts).strip(), image_parts


def model_supports_images(model_name: str) -> bool:
    normalized = model_name.lower()
    return any(keyword in normalized for keyword in VISION_MODEL_KEYWORDS)


def bytes_to_data_url(content, mime_type):
    encoded = base64.b64encode(content).decode()
    return f"data:{mime_type};base64,{encoded}"


def fetch_url_to_data_url(image_url):
    resp = requests.get(image_url, timeout=CONFIG["REQUEST_TIMEOUT"])
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip() or "image/jpeg"
    return bytes_to_data_url(resp.content, content_type)


async def image_data_to_data_url(bot, image_data):
    image_url = image_data.get("url")
    if image_url:
        return fetch_url_to_data_url(image_url)

    image_file = image_data.get("file")
    if not image_file:
        raise RuntimeError("未能读取图片地址")

    if image_file.startswith("base64://"):
        content = base64.b64decode(image_file[len("base64://"):])
        mime_type = image_data.get("mime", "image/jpeg")
        return bytes_to_data_url(content, mime_type)

    if image_file.startswith("file://"):
        local_path = image_file[len("file://"):]
        with open(local_path, "rb") as file_handle:
            content = file_handle.read()
        mime_type = mimetypes.guess_type(local_path)[0] or image_data.get("mime") or "image/jpeg"
        return bytes_to_data_url(content, mime_type)

    try:
        image_info = await bot.get_image(file=image_file)
    except Exception:
        image_info = {}

    remote_url = image_info.get("url") if isinstance(image_info, dict) else None
    if remote_url:
        return fetch_url_to_data_url(remote_url)

    local_file = image_info.get("file") if isinstance(image_info, dict) else None
    if local_file and os.path.exists(local_file):
        with open(local_file, "rb") as file_handle:
            content = file_handle.read()
        mime_type = mimetypes.guess_type(local_file)[0] or image_data.get("mime") or "image/jpeg"
        return bytes_to_data_url(content, mime_type)

    raise RuntimeError("未能读取图片地址")


async def build_user_content(bot, text, image_parts):
    if not image_parts:
        return text

    content = []
    if text:
        content.append({"type": "text", "text": text})
    else:
        content.append({"type": "text", "text": "请识别这张图片，并结合图片内容回答。"})

    for image_data in image_parts:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": await image_data_to_data_url(bot, image_data)
            }
        })

    return content


# ====== LLM调用 ======
def call_llm_sync(messages):
    url = f"{CONFIG['BASE_URL']}/v1/chat/completions"

    data = {
        "model": CONFIG["MODEL"],
        "messages": messages,
        "temperature": 0.8,
        "max_tokens": 1500
    }

    resp = requests.post(url, json=data, timeout=CONFIG["REQUEST_TIMEOUT"])

    if not resp.ok:
        try:
            error_data = resp.json()
        except Exception:
            error_data = {}

        error_message = ""
        if isinstance(error_data, dict):
            error_value = error_data.get("error")
            if isinstance(error_value, dict):
                error_message = error_value.get("message") or error_value.get("type") or ""
            elif error_value:
                error_message = str(error_value)
            if not error_message:
                error_message = error_data.get("message") or error_data.get("detail") or ""

        if not error_message:
            error_message = resp.text

        error_lower = error_message.lower()
        if any(keyword in error_lower for keyword in ("image", "vision", "multimodal", "multimodal_input")):
            raise RuntimeError(f"当前模型 {CONFIG['MODEL']} 不支持识别图片，请切换视觉模型后重试")

        raise RuntimeError(f"LLM 请求失败：{resp.status_code} {error_message}".strip())

    result = resp.json()

    print("LLM原始返回：", result)

    msg = result['choices'][0].get('message', {})
    reply = msg.get('content') or msg.get('final') or msg.get('reasoning_content')

    return reply or "（模型没有返回内容）"


async def call_llm(messages):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, call_llm_sync, messages)

# 在此处输入你的系统提示词
SYSTEM_PROMPT =  """
                    
                 """


# ====== 主聊天逻辑 ======
@sv.on_prefix(('问', 'chat'), only_to_me=True)
async def chat(bot, ev):
    msg, image_parts = extract_message_parts(ev.message)
    if not msg and not image_parts:
        return

    if image_parts and not model_supports_images(CONFIG["MODEL"]):
        await bot.send(ev, f"当前模型 {CONFIG['MODEL']} 不支持识别图片，请切换视觉模型后重试")
        return

    session_id = get_session_id(ev)

    # ===== 初始化 =====
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = sessions[session_id]

    # ===== 加入用户输入 =====
    history.append({"role": "user", "content": await build_user_content(bot, msg, image_parts)})

    # ===== 控制上下文 =====
    max_len = CONFIG["MAX_HISTORY"] * 2
    if len(history) > max_len:
        sessions[session_id] = history[-max_len:]
        history = sessions[session_id]

    # await bot.send(ev, "思考中...") 不输出思考反应

    # ===== 调用 LLM =====
    try:
        reply = await call_llm(history)
    except Exception as e:
        await bot.send(ev, str(e))
        return

    reply = safe_send_text(reply)

    print("最终发送：", repr(reply))

    # ===== 保存上下文 =====
    history.append({"role": "assistant", "content": reply})

    # ===== 发送 =====
    try:
        await bot.send(ev, reply)
    except Exception as e:
        print("发送失败：", e)
        await bot.send(ev, "（发送失败）")


# ====== 清空对话 ======
@sv.on_fullmatch(('清空对话', 'reset'), only_to_me=True)
async def clear_session(bot, ev):
    session_id = get_session_id(ev)
    sessions.pop(session_id, None)
    await bot.send(ev, "对话已清空")


# ====== Debug指令（增强版） ======
@sv.on_fullmatch(('debug', '状态'), only_to_me=True)
async def debug(bot, ev):
    session_id = get_session_id(ev)
    history = sessions.get(session_id, [])

    model = get_model_info()

    info = "🛠 系统状态\n"
    info += f"模型: {model}\n"
    info += f"地址: {CONFIG['BASE_URL']}\n"
    info += f"总会话: {len(sessions)}\n"
    info += f"当前会话长度: {len(history)}\n\n"

    info += "最近对话:\n"
    for h in history[-3:]:
        role = h.get("role")
        content = h.get("content", "")[:30]
        info += f"{role}: {content}\n"

    await bot.send(ev, info[:1000])
