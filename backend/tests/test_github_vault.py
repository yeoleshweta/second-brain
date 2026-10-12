from __future__ import annotations

import base64

import pytest

from src.integrations.obsidian import GitHubVaultBackend


class _FakeResp:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> object:
        return self._payload


@pytest.mark.asyncio
async def test_github_append_creates_then_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {}
    sha = {"n": 0}

    class FakeClient:
        async def aclose(self) -> None:
            return None

        async def get(self, url: str, params: dict | None = None) -> _FakeResp:
            del params
            path = url.rsplit("/contents/", 1)[-1]
            if path not in store:
                return _FakeResp(404, {})
            body = store[path]
            encoded = base64.b64encode(body.encode()).decode()
            return _FakeResp(200, {"type": "file", "content": encoded, "sha": f"sha{sha['n']}"})

        async def put(self, url: str, json: dict) -> _FakeResp:
            path = url.rsplit("/contents/", 1)[-1]
            raw = base64.b64decode(json["content"]).decode()
            store[path] = raw
            sha["n"] += 1
            return _FakeResp(200, {"content": {"sha": f"sha{sha['n']}"}})

    backend = GitHubVaultBackend("yeoleshweta/second-brain-vault", "t", "main")
    monkeypatch.setattr(backend, "_client", FakeClient())
    await backend.append("Inbox/test.md", "hello\n")
    await backend.append("Inbox/test.md", "world\n")
    assert await backend.get("Inbox/test.md") == "hello\nworld\n"
    await backend.close()
