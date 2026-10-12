"""Inference across locally owned models or voluntary external endpoints.

Borg's control plane is original and vendor-neutral. Neural model weights
and optimized inference kernels are separate, replaceable components.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock

_GGUF_LOCK = RLock()
from urllib.request import Request, urlopen


@lru_cache(maxsize=2)
def _local_gguf(path, n_ctx, threads, gpu_layers):
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise RuntimeError('Local GGUF needs the optional llama-cpp-python package: pip install -e .[local]') from exc
    return Llama(model_path=path, n_ctx=n_ctx, n_threads=threads,
                 n_gpu_layers=gpu_layers, verbose=False)


def infer(prompt, backend='mock', model=None, base_url=None, timeout=120):
    """Run inference locally or via a configured HTTP service.

    No software execution instructions are accepted from unknown peers.
    Models and user-supplied GGUF weights are not embedded in Borg source.
    """
    if backend == 'mock':
        return '[MOCK COMPUTE - not an AI answer] ' + prompt[:180].replace('\n', ' ')
    if backend == 'gguf':
        if not model or not Path(model).is_file() or Path(model).suffix.lower() != '.gguf':
            raise ValueError('GGUF backend requires a local .gguf model file')
        threads = int(os.environ.get('BORG_CPU_THREADS', '4'))
        gpu_layers = int(os.environ.get('BORG_GPU_LAYERS', '0'))
        n_ctx = int(os.environ.get('BORG_CONTEXT_SIZE', '2048'))
        if not 1 <= threads <= 128 or not 256 <= n_ctx <= 32768 or not 0 <= gpu_layers <= 200:
            raise ValueError('Invalid local inference resource limits')
        llm = _local_gguf(str(Path(model).resolve()), n_ctx, threads, gpu_layers)
        # One in-process Llama object should not be accessed concurrently.
        with _GGUF_LOCK:
            reply = llm.create_chat_completion(
                messages=[{'role':'user','content':prompt}],
                max_tokens=512, temperature=0.3)
        return reply['choices'][0]['message']['content']

    if backend == 'ollama':
        url = (base_url or 'http://127.0.0.1:11434').rstrip('/') + '/api/chat'
        payload = {'model':model or 'qwen3:1.7b', 'stream':False,
                   'messages':[{'role':'user','content':prompt}]}
    elif backend in ('http-api', 'openai-compatible'):
        if not base_url or not model:
            raise ValueError('HTTP inference requires base URL and model')
        url = base_url.rstrip('/') + '/chat/completions'
        payload = {'model':model,
                   'messages':[{'role':'user','content':prompt}], 'max_tokens':1024}
    else:
        raise ValueError('Unknown backend')
    if not url.startswith('https://') and not url.startswith('http://127.0.0.1') and not url.startswith('http://localhost'):
        raise ValueError('Remote inference requires HTTPS')
    headers = {'Content-Type':'application/json'}
    if backend in ('http-api', 'openai-compatible') and os.getenv('BORG_MODEL_API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.getenv('BORG_MODEL_API_KEY')
    req = Request(url,json.dumps(payload).encode(),headers)
    with urlopen(req,timeout=timeout) as response:
        data=json.load(response)
    if backend=='ollama':
        return data['message']['content']
    return data['choices'][0]['message']['content']
