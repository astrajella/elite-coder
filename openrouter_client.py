import requests
from typing import List, Dict, Any, Optional
from config import settings

API_URL = "https://openrouter.ai/api/v1/chat/completions"

def chat(messages: List[Dict[str, str]], model: Optional[str] = None, tools: Any = None) -> Dict[str, Any]:
    model = model or settings.OPENROUTER_DEFAULT_MODEL
    if not settings.ALLOW_INTERNET:
        return {"model": model, "offline": True, "choices":[{"message":{"role":"assistant","content":"OFFLINE_STUB"}}]}
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AI Code-Agent Elite",
    }
    payload = {"model": model, "messages": messages}
    if tools: payload["tools"] = tools
    r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()
