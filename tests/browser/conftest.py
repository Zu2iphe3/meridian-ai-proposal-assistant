"""Run browser integration tests against the real local FastAPI host."""

import socket
from collections.abc import Iterator
from threading import Thread

import pytest
import uvicorn

from meridian_agent.app import app


@pytest.fixture(scope="module")
def app_url() -> Iterator[str]:
    with socket.create_server(("127.0.0.1", 0)) as listener:
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="warning", timeout_graceful_shutdown=5)
        )
        worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{listener.getsockname()[1]}"
        finally:
            server.should_exit = True
            worker.join(timeout=10)
