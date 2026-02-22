# Claude Code + Groq via LiteLLM

Run Claude Code using free Groq models instead of the Anthropic API.

---

## Requirements

- macOS with Python 3.x (Homebrew)
- [Claude Code](https://github.com/anthropics/claude-code) installed (`npm install -g @anthropic-ai/claude-code`)
- Groq API key: https://console.groq.com

---

## Setup from scratch

### 1. Install LiteLLM

```bash
pip3 install 'litellm[proxy]' --break-system-packages
```

### 2. Fix uvloop (incompatible with Python 3.14)

```bash
pip3 uninstall uvloop -y --break-system-packages
```

Patch uvicorn so it doesn't crash without uvloop:

```bash
python3 - <<'EOF'
path = __import__('site').getsitepackages()[0] + '/uvicorn/loops/uvloop.py'
open(path, 'w').write(
    "import asyncio\n\ntry:\n    import uvloop\n"
    "    def uvloop_setup(use_subprocess: bool = False) -> None:\n"
    "        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())\n"
    "except ImportError:\n"
    "    def uvloop_setup(use_subprocess: bool = False) -> None:\n"
    "        pass\n"
)
print('ok')
EOF
```

### 3. Create project directory

```bash
mkdir -p ~/groq-proxy && cd ~/groq-proxy
```

### 4. Create `litellm_config.yaml`

```yaml
model_list:
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: groq/openai/gpt-oss-120b
      api_key: os.environ/GROQ_API_KEY

  - model_name: claude-opus-4-5
    litellm_params:
      model: groq/openai/gpt-oss-120b
      api_key: os.environ/GROQ_API_KEY

  - model_name: claude-haiku-4-5
    litellm_params:
      model: groq/openai/gpt-oss-120b
      api_key: os.environ/GROQ_API_KEY

litellm_settings:
  drop_params: true
  set_verbose: false

general_settings:
  master_key: "sk-local-proxy"
```

> The `claude-*` model names are what Claude Code sends automatically.
> All of them are mapped to `openai/gpt-oss-120b` on Groq.

### 5. Create `middleware.py`

Claude Code sends 200+ tools per request; Groq accepts a maximum of 128. This middleware trims the list:

```python
#!/usr/bin/env python3
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()
LITELLM_BASE = "http://localhost:4001"
MAX_TOOLS = 128

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
async def proxy(request: Request, path: str):
    url = f"{LITELLM_BASE}/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    body = await request.body()

    if request.method == "POST" and body:
        try:
            data = json.loads(body)
            if isinstance(data.get("tools"), list) and len(data["tools"]) > MAX_TOOLS:
                data["tools"] = data["tools"][:MAX_TOOLS]
                body = json.dumps(data).encode()
                headers["content-length"] = str(len(body))
        except (json.JSONDecodeError, KeyError):
            pass

    client = httpx.AsyncClient(timeout=300)
    req = client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        content=body,
        params=request.query_params,
    )
    response = await client.send(req, stream=True)

    async def stream_body():
        async for chunk in response.aiter_bytes():
            yield chunk
        await client.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.headers.get("content-type"),
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=4000, loop="asyncio")
```

### 6. Create `start_proxy.sh`

```bash
#!/usr/bin/env bash
set -e

if [ -z "$GROQ_API_KEY" ]; then
  echo "❌ GROQ_API_KEY is not set!"
  echo "   export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "▶ Starting LiteLLM on http://localhost:4001 ..."
litellm --config litellm_config.yaml --port 4001 &
LITELLM_PID=$!
sleep 3

echo "▶ Starting middleware on http://localhost:4000 ..."
echo ""
echo "In another terminal run:"
echo "   export ANTHROPIC_BASE_URL=http://localhost:4000"
echo "   export ANTHROPIC_API_KEY=sk-local-proxy"
echo "   claude"
echo ""

trap "kill $LITELLM_PID 2>/dev/null" EXIT
python3 middleware.py
```

```bash
chmod +x start_proxy.sh
```

---

## Running

**Terminal 1:**
```bash
export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
./start_proxy.sh
```

**Terminal 2:**
```bash
export ANTHROPIC_BASE_URL=http://localhost:4000
export ANTHROPIC_API_KEY=sk-local-proxy
claude
```

---

## Architecture

```
Claude Code
    │  POST /v1/messages  (model: claude-sonnet-4-6, tools: 200 items)
    ▼
middleware.py :4000
    │  trims tools to 128
    ▼
LiteLLM :4001
    │  maps claude-sonnet-4-6 → groq/openai/gpt-oss-120b
    ▼
Groq API
    │  openai/gpt-oss-120b
    ▼
response back
```

---

## Available Groq models with tool support

| Model ID | Notes |
|----------|-------|
| `openai/gpt-oss-120b` | GPT-OSS 120B (recommended) |
| `openai/gpt-oss-20b` | GPT-OSS 20B (faster) |
| `llama-3.3-70b-versatile` | Llama 3.3 70B |
| `moonshotai/kimi-k2-instruct` | Kimi K2 |

To switch models, change the `model: groq/...` value in `litellm_config.yaml`.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `cannot import uvloop` | Python 3.14 incompatibility | Step 2 above |
| `model does not exist` | Wrong model ID format | Use `groq/openai/gpt-oss-120b` |
| `maximum number of items is 128` | Too many tools | middleware.py trims to 128 |
| `Invalid API Key` | Key not set in environment | `export GROQ_API_KEY=...` before starting |
