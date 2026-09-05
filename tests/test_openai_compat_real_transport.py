"""Real OpenAI-compatible transport checks against a loopback-only fixture."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from typing import Any, ClassVar

import pytest

from dochris.llm.openai_compat import OpenAICompatProvider


class _LocalOpenAIHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible endpoint that never leaves localhost."""

    requests: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length))
        self.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "payload": payload,
            }
        )

        if payload.get("stream"):
            chunks = [
                {
                    "id": "chatcmpl-local-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "fixture-model",
                    "choices": [{"index": 0, "delta": {"content": "本地"}, "finish_reason": None}],
                },
                {
                    "id": "chatcmpl-local-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "fixture-model",
                    "choices": [
                        {"index": 0, "delta": {"content": "流式回答"}, "finish_reason": None}
                    ],
                },
                {
                    "id": "chatcmpl-local-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "fixture-model",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            ]
            body = (
                "".join(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks)
                + "data: [DONE]\n\n"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True
            return

        response = {
            "id": "chatcmpl-local",
            "object": "chat.completion",
            "created": 0,
            "model": "fixture-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "本地完整回答"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        }
        body = json.dumps(response, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def log_message(self, format: str, *args: object) -> None:
        """Keep the deterministic fixture quiet during test runs."""


async def _exercise_provider(provider: OpenAICompatProvider) -> tuple[str, list[str]]:
    try:
        answer = await provider.generate("问题", system_prompt="系统")
        streamed = [chunk async for chunk in provider.generate_stream("流式问题")]
        return answer, streamed
    finally:
        await provider.close()


@pytest.mark.integration
def test_openai_compat_provider_against_local_fixture() -> None:
    """Exercise the real OpenAI SDK serialization and stream parser locally."""

    pytest.importorskip("openai")
    _LocalOpenAIHandler.requests = []
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _LocalOpenAIHandler,
        bind_and_activate=False,
    )
    # HTTPServer.server_bind() performs a reverse-DNS lookup that can stall
    # isolated CI hosts; TCPServer still exercises the real loopback socket.
    TCPServer.server_bind(server)
    server.server_name = str(server.server_address[0])
    server.server_port = int(server.server_address[1])
    server.server_activate()
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = OpenAICompatProvider(
        api_key="local-placeholder",
        api_base=f"http://127.0.0.1:{server.server_port}/v1",
        model="fixture-model",
        max_tokens=64,
        temperature=0.2,
        timeout=5,
    )

    try:
        answer, streamed = asyncio.run(_exercise_provider(provider))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert answer == "本地完整回答"
    assert streamed == ["本地", "流式回答"]
    assert not thread.is_alive()
    assert len(_LocalOpenAIHandler.requests) == 2

    regular, stream = _LocalOpenAIHandler.requests
    assert regular["path"] == "/v1/chat/completions"
    assert regular["authorization"] == "Bearer local-placeholder"
    assert regular["payload"]["model"] == "fixture-model"
    assert regular["payload"]["messages"] == [
        {"role": "system", "content": "系统"},
        {"role": "user", "content": "问题"},
    ]
    assert regular["payload"]["max_tokens"] == 64
    assert regular["payload"]["temperature"] == 0.2
    assert regular["payload"].get("stream") is not True
    assert stream["path"] == "/v1/chat/completions"
    assert stream["authorization"] == "Bearer local-placeholder"
    assert stream["payload"]["stream"] is True
