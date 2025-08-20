import os, json, time
try:
    import httpx
except Exception:
    httpx = None
ALLOW = os.getenv("ALLOW_INTERNET","false").lower() == "true"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY","")

def generate(prompt, model=None, stream=False):
    model = model or os.getenv("OPENROUTER_DEFAULT_MODEL","openrouter/auto")
    if not ALLOW or httpx is None:
        return {'provider':'openrouter','model':model,'text':f'[SIMULATED OPENROUTER] {prompt[:200]}', 'stream': False}
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    payload = {"model": model, "messages": [{"role":"user","content":prompt}]}
    r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30.0)
    r.raise_for_status()
    return r.json()


def generate_stream(prompt, model=None):
    """Yield text chunks for streaming. If ALLOW_INTERNET is False or httpx missing, simulate streaming."""
    if not ALLOW or 'httpx' not in globals() or httpx is None:
        parts = [f"[SIM]{prompt[:80]}", "...", "[END]" ]
        for p in parts:
            yield p
        return
    # If real httpx is available but streaming not implemented for provider, fall back to single response split
    full = generate(prompt, model=model, stream=False)
    text = ''
    if isinstance(full, dict):
        # attempt to extract text
        if 'text' in full:
            text = full['text']
        elif 'choices' in full and len(full['choices'])>0:
            text = full['choices'][0].get('text') or full['choices'][0].get('message',{}).get('content','')
        else:
            text = str(full)
    else:
        text = str(full)
    # split into 120-char chunks
    for i in range(0, len(text), 120):
        yield text[i:i+120]



def generate_stream_with_seq(prompt, model=None):
    """Wrapper producing (seq,chunk) tuples as JSON-friendly dicts."""
    seq = 0
    for chunk in generate_stream(prompt, model=model):
        seq += 1
        yield {'seq': seq, 'chunk': chunk}
    return
