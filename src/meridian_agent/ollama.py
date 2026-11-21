"""Loopback-only Ollama adapter."""

import asyncio
import os

import httpx

from meridian_agent.extraction import ExtractionError


class OllamaProvider:
    def __init__(
        self,
        host: str,
        model: str,
        timeout: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        try:
            url = httpx.URL(host)
            allowed = (
                url.scheme == "http"
                and url.host in {"127.0.0.1", "::1", "localhost"}
                and not (url.userinfo or url.query or url.fragment)
                and url.path == "/"
            )
            if not allowed or not model.strip() or not 1 <= timeout <= 600:
                raise ValueError
        except (ValueError, httpx.InvalidURL) as exc:
            raise ExtractionError(
                "invalid_ollama_config",
                "Set OLLAMA_HOST to a loopback HTTP URL, OLLAMA_MODEL to a local model, "
                "and OLLAMA_TIMEOUT_SECONDS to a number from 1 to 600.",
                503,
            ) from exc
        self._url = url.copy_with(host="127.0.0.1" if url.host == "localhost" else url.host)
        self._model = model
        self._timeout = timeout
        self._transport = transport

    @classmethod
    def from_environment(cls) -> "OllamaProvider":
        try:
            timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
        except ValueError:
            timeout = 0
        return cls(
            os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            timeout,
        )

    async def generate(self, policy: str, notes: str, schema: dict[str, object]) -> str:
        try:
            async with asyncio.timeout(self._timeout):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout, connect=2),
                    trust_env=False,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        self._url.copy_with(path="/api/chat"),
                        json={
                            "model": self._model,
                            "stream": False,
                            "format": schema,
                            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 2048},
                            "messages": [
                                {"role": "system", "content": policy},
                                {"role": "user", "content": notes},
                            ],
                        },
                    )
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise ExtractionError(
                "ollama_timeout", "Ollama timed out. Try again or shorten the notes.", 504
            ) from exc
        except httpx.RequestError as exc:
            raise ExtractionError(
                "ollama_unavailable", "Start the local Ollama service and try again.", 503
            ) from exc

        if response.status_code == 404:
            raise ExtractionError(
                "ollama_model_missing", "Check that OLLAMA_MODEL is installed locally.", 503
            )
        if response.is_error:
            raise ExtractionError(
                "ollama_failed",
                "Ollama could not complete extraction. Check its service logs.",
                502,
            )
        try:
            payload = response.json()
            content = payload["message"]["content"]
            if not isinstance(content, str) or payload.get("done_reason") == "length":
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractionError(
                "invalid_model_output", "Ollama returned an invalid extraction. Try again.", 502
            ) from exc
        return content
