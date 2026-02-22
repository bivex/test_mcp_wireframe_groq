#!/usr/bin/env python3
"""
Middleware: обрезает tools до 128, затем проксирует в LiteLLM на порту 4001.
Claude Code → :4000 (этот скрипт) → :4001 (litellm) → Groq
"""
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
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
