# LLM_Chat
基于[HoshinoBot](https://github.com/Ice9Coffee/HoshinoBot)构建的接入大模型聊天的插件，大模型运行平台基于[LM Studio](https://lmstudio.ai/)构建，不确定是否适用于其他平台（如Ollama）

---
## 部署
在`modules`目录下克隆本仓库项目：
```
git clone https://github.com/AmamiyaAkina/LLM_Chat.git
```
并在`__bot__.py`的`module`中添加`LLM_Chat`

---
## 快速开始
在`main.py`中的`CONFIG`配置你的`BASE_URL`与`MODEL`，并配置你的`System Prompt` 

```
# Example

CONFIG = {
    "BASE_URL": "http://0.0.0.0:1234",
    "MODEL": "qwen3-vl-8b",
    "MAX_HISTORY": 10
}

...

SYSTEM_PROMPT =  """
                  你是一个实用的AI助手...
                 """
```

配置完成后，at机器人账号输入`chat`在后面输入内容即可开启聊天
<p align="center">
  <img width="920" height="464" alt="图片" src="https://github.com/user-attachments/assets/c4bb16a7-a6b8-4bcf-a3d7-513705cae31e" />
</p>

插件已内置图片输入，在上述内容后方贴入图片，即可让支持视觉模型的LLM识别图片内容
<p align="center">
  <img width="1208" height="1146" alt="图片" src="https://github.com/user-attachments/assets/aad85858-6c97-46ba-bbe5-3812707e238a" />
</p>

---
## debugging
at机器人输入`debug`，以快速查看调试信息（如加载的模型、服务器URL、最近对话、对话长度等）
<p align="center">
  <img width="914" height="792" alt="图片" src="https://github.com/user-attachments/assets/c8e8568c-d667-4460-b06e-29d273359b42" />
</p>

---
## 其他配置
`temperature`:语言模型的温度
`max_tokens`:模型输出最大文本量，如果该值设置的太小会被截断导致信息不会被发出
如需进一步调试，可将该行输出思考回复取消注释 
```
await bot.send(ev, "思考中...")
```

## 未来与展望
未来一些想加的功能，大概取决于我什么时候愿意去写吧
- 更新API Key功能调用LLM
- 加入工具调用函数
- 让机器人能自发随机在群聊中触发聊天，并将语言像真人一样拆分分段输出
- 支持私聊直接聊天
- 定时记忆管理，让机器人可自发撰写回忆并写成Prompt保存供自己调用
