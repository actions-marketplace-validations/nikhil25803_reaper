import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen

from fake_llama_server import FakeLlamaHandler


def request_json(url: str, payload: dict | None = None) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=2) as response:
        return json.loads(response.read())


def test_fake_llama_server_contract() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeLlamaHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        assert request_json(f"{base_url}/health") == {"status": "ok"}
        assert request_json(f"{base_url}/v1/models") == {
            "data": [{"id": "fake-workflow-model"}]
        }
        response = request_json(
            f"{base_url}/v1/chat/completions",
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "candidates": [
                                    {"node_id": "dead"},
                                    {"node_id": "review"},
                                    {"node_id": "used"},
                                ]
                            }
                        ),
                    }
                ]
            },
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    content = json.loads(response["choices"][0]["message"]["content"])
    assert [item["verdict"] for item in content["findings"]] == [
        "likely_dead",
        "needs_review",
        "likely_used",
    ]
