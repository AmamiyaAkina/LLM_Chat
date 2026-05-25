import requests
import asyncio
import re
from hoshino import Service

sv = Service('llm_chat', enable_on_default=True)

# ====== 配置 ======
CONFIG = {
    "BASE_URL": "",    # 在此处配置你运行LLM的服务器地址
    "MODEL": "",       # 在次数配置你运行的LLM模型
    "MAX_HISTORY": 10  # 上下文长度
}

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


# ====== LLM调用 ======
def call_llm_sync(messages):
    url = f"{CONFIG['BASE_URL']}/v1/chat/completions"

    data = {
        "model": CONFIG["MODEL"],
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1500
    }

    resp = requests.post(url, json=data)
    result = resp.json()

    print("LLM原始返回：", result)

    msg = result['choices'][0].get('message', {})
    reply = msg.get('content') or msg.get('final') or msg.get('reasoning_content')

    return reply or "（模型没有返回内容）"


async def call_llm(messages):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, call_llm_sync, messages)


SYSTEM_PROMPT =  """
                 
                 """
# 在此处写入你的System Prompt


# ====== 主聊天逻辑 ======
@sv.on_prefix(('问', 'chat'), only_to_me=True)
async def chat(bot, ev):
    msg = ev.message.extract_plain_text().strip()
    if not msg:
        return

    session_id = get_session_id(ev)

    # ===== 初始化 =====
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = sessions[session_id]

    # ===== 加入用户输入 =====
    history.append({"role": "user", "content": msg})

    # ===== 控制上下文 =====
    max_len = CONFIG["MAX_HISTORY"] * 2
    if len(history) > max_len:
        sessions[session_id] = history[-max_len:]
        history = sessions[session_id]

    # await bot.send(ev, "思考中...")

    # ===== 调用 LLM =====
    try:
        reply = await call_llm(history)
    except Exception as e:
        await bot.send(ev, f"出错了：{e}")
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
