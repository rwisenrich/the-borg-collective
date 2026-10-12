"""AI model adapters. NVIDIA Dynamo/vLLM can supply an OpenAI-compatible endpoint."""
import json
import os
from urllib.request import Request, urlopen


def infer(prompt, backend="mock", model=None, base_url=None, timeout=120):
    if backend == "mock":
        # Deterministic integration test; NOT a neural model.
        return "[MOCK COMPUTE - not an AI answer] " + prompt[:180].replace("\n", " ")
    if backend == "ollama":
        url = (base_url or "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
        payload = {"model":model or "qwen3:1.7b", "stream":False,
                   "messages":[{"role":"user","content":prompt}]}
    elif backend == "openai-compatible":
        if not base_url or not model:
            raise ValueError("OpenAI-compatible backend requires base URL and model")
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model":model, "messages":[{"role":"user","content":prompt}],"max_tokens":1024}
    else:
        raise ValueError("Unknown backend")
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1") and not url.startswith("http://localhost"):
        raise ValueError("Remote inference requires HTTPS")
    headers = {"Content-Type":"application/json"}
    if backend == "openai-compatible" and os.getenv("BORG_MODEL_API_KEY"):
        headers["Authorization"] = "Bearer "+os.getenv("BORG_MODEL_API_KEY")
    req = Request(url,json.dumps(payload).encode(),headers)
    with urlopen(req,timeout=timeout) as resp:
        data = json.load(resp)
    if backend == "ollama":
        return data["message"]["content"]
    return data["choices"][0]["message"]["content"]
