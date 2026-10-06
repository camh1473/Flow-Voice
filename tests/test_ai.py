import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from flowvoice import ai
from flowvoice.ai import AiError, OllamaClient, ensure_running, is_loopback


class _Server:
    """Throwaway loopback HTTP server; `routes` maps (method, path) -> handler(req) -> (status, body, headers)."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _handle(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.requests.append((method, self.path, body))
                route = outer.routes.get((method, self.path))
                if route is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status, payload, headers = route(self)
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)


@pytest.fixture
def server():
    s = _Server()
    try:
        yield s
    finally:
        s.stop()


def _chat_ok(text="Hello there."):
    return lambda req: (200, {"message": {"role": "assistant", "content": text}}, None)


def test_is_loopback_accepts_local_hosts():
    assert is_loopback("http://localhost:11434")
    assert is_loopback("http://LOCALHOST:11434/")
    assert is_loopback("http://127.0.0.1:11434")
    assert is_loopback("http://[::1]:11434")
    assert is_loopback("https://localhost")


@pytest.mark.parametrize("url", [
    "http://example.com:11434",
    "http://10.0.0.5:11434",
    "http://localhost.evil.com:11434",
    "http://localhost@evil.com/",
    "http://127.0.0.1.evil.com/",
    "ftp://localhost/",
    "localhost:11434",
    "",
    "http://",
    "file:///C:/x",
])
def test_is_loopback_rejects_others(url):
    assert not is_loopback(url)


def test_non_loopback_refused_before_any_socket(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    for url in ("http://example.com:11434", "http://10.0.0.5:11434"):
        with pytest.raises(AiError):
            OllamaClient(url, "m")


def test_loopback_urls_accepted():
    for url in ("http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"):
        OllamaClient(url, "m")


def test_chat_success_request_shape(server):
    server.routes[("POST", "/api/chat")] = _chat_ok("Polished text.")
    client = OllamaClient(server.url, "qwen-test")
    out = client.chat("SYS", "USER", examples=[("in1", "out1"), ("in2", "out2")], max_tokens=99)
    assert out == "Polished text."
    method, path, body = server.requests[0]
    data = json.loads(body)
    assert data["model"] == "qwen-test"
    assert data["stream"] is False
    assert data["think"] is False
    assert data["keep_alive"] == "30m"
    assert data["options"]["temperature"] == 0
    assert data["options"]["num_predict"] == 99
    assert data["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "in1"},
        {"role": "assistant", "content": "out1"},
        {"role": "user", "content": "in2"},
        {"role": "assistant", "content": "out2"},
        {"role": "user", "content": "USER"},
    ]


def test_chat_without_examples(server):
    server.routes[("POST", "/api/chat")] = _chat_ok()
    OllamaClient(server.url, "m").chat("S", "U")
    data = json.loads(server.requests[0][2])
    assert [m["role"] for m in data["messages"]] == ["system", "user"]
    assert data["options"]["num_predict"] == 512


def test_chat_http_500(server):
    server.routes[("POST", "/api/chat")] = lambda req: (500, {"error": "boom secret dictated text"}, None)
    with pytest.raises(AiError) as exc:
        OllamaClient(server.url, "m").chat("S", "U")
    assert "secret" not in str(exc.value)


def test_chat_malformed_json(server):
    server.routes[("POST", "/api/chat")] = lambda req: (200, b"not json{", None)
    with pytest.raises(AiError):
        OllamaClient(server.url, "m").chat("S", "U")


@pytest.mark.parametrize("payload", [
    {"message": {"content": ""}},
    {"message": {"content": None}},
    {"message": {}},
    {"message": "x"},
    {},
    [],
])
def test_chat_bad_content(server, payload):
    server.routes[("POST", "/api/chat")] = lambda req: (200, payload, None)
    with pytest.raises(AiError):
        OllamaClient(server.url, "m").chat("S", "U")


@pytest.mark.parametrize("text", ["", "  \n "])
def test_chat_empty_content_is_empty_reply(server, text):
    server.routes[("POST", "/api/chat")] = _chat_ok(text)
    with pytest.raises(ai.AiEmptyReply) as exc:
        OllamaClient(server.url, "m").chat("S", "U")
    assert isinstance(exc.value, AiError)
    assert str(exc.value) == "Local AI returned an empty reply"


@pytest.mark.parametrize("payload", [{"message": {"content": None}}, {"message": {}}, {}, []])
def test_chat_malformed_content_is_not_empty_reply(server, payload):
    server.routes[("POST", "/api/chat")] = lambda req: (200, payload, None)
    with pytest.raises(AiError) as exc:
        OllamaClient(server.url, "m").chat("S", "U")
    assert not isinstance(exc.value, ai.AiEmptyReply)


def test_chat_timeout(server):
    def slow(req):
        time.sleep(1.5)
        return 200, {"message": {"content": "late"}}, None

    server.routes[("POST", "/api/chat")] = slow
    client = OllamaClient(server.url, "m", timeout=0.3)
    start = time.monotonic()
    with pytest.raises(AiError):
        client.chat("S", "U")
    assert time.monotonic() - start < 1.0


def test_chat_trickling_server_hits_total_deadline():
    # Server that sends one byte every 0.1 s: per-socket timeout never fires.
    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen(1)
    port = lsock.getsockname()[1]
    stop = threading.Event()

    def serve():
        try:
            conn, _ = lsock.accept()
        except OSError:
            return
        try:
            conn.settimeout(1)
            try:
                conn.recv(65536)
            except OSError:
                pass
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n")
            while not stop.is_set():
                conn.sendall(b"x")
                time.sleep(0.1)
        except OSError:
            pass
        finally:
            conn.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    try:
        client = OllamaClient(f"http://127.0.0.1:{port}", "m", timeout=0.4)
        start = time.monotonic()
        with pytest.raises(AiError):
            client.chat("S", "U")
        assert time.monotonic() - start < 1.2
    finally:
        stop.set()
        lsock.close()
        t.join(5)


def test_chat_connection_refused():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(AiError):
        OllamaClient(f"http://127.0.0.1:{port}", "m", timeout=1).chat("S", "U")


def test_redirect_refused(server):
    server.routes[("POST", "/api/chat")] = lambda req: (302, b"", {"Location": "http://example.com/x"})
    with pytest.raises(AiError):
        OllamaClient(server.url, "m").chat("S", "U")


def test_list_models(server):
    server.routes[("GET", "/api/tags")] = lambda req: (
        200, {"models": [{"name": "a:1b"}, {"name": "b:latest"}, {"x": 1}]}, None)
    assert OllamaClient(server.url, "a:1b").list_models() == ["a:1b", "b:latest"]


def test_list_models_error(server):
    server.routes[("GET", "/api/tags")] = lambda req: (500, b"{}", None)
    with pytest.raises(AiError):
        OllamaClient(server.url, "m").list_models()


def test_is_up(server):
    server.routes[("GET", "/api/tags")] = lambda req: (200, {"models": []}, None)
    assert OllamaClient(server.url, "m").is_up() is True


def test_is_up_false_when_down():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert OllamaClient(f"http://127.0.0.1:{port}", "m").is_up() is False


def test_is_up_false_on_error_status(server):
    server.routes[("GET", "/api/tags")] = lambda req: (500, b"{}", None)
    assert OllamaClient(server.url, "m").is_up() is False


def test_has_model_exact(server):
    server.routes[("GET", "/api/tags")] = lambda req: (
        200, {"models": [{"name": "qwen3.5:2b-q4_K_M"}, {"name": "other:latest"}]}, None)
    assert OllamaClient(server.url, "qwen3.5:2b-q4_K_M").has_model() is True
    assert OllamaClient(server.url, "qwen3.5:2b").has_model() is False
    assert OllamaClient(server.url, "qwen3.5").has_model() is False
    assert OllamaClient(server.url, "other").has_model() is True


def test_has_model_false_when_down():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert OllamaClient(f"http://127.0.0.1:{port}", "m").has_model() is False


def test_find_ollama_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(ai.shutil, "which", lambda name: r"C:\bin\ollama.exe")
    assert ai.find_ollama_exe() == r"C:\bin\ollama.exe"
    monkeypatch.setattr(ai.shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert ai.find_ollama_exe() is None
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert ai.find_ollama_exe() == str(exe)


class _FakeClient:
    def __init__(self, ups):
        self.ups = list(ups)
        self.calls = 0

    def is_up(self):
        self.calls += 1
        return self.ups.pop(0) if len(self.ups) > 1 else self.ups[0]


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_ensure_running_already_up():
    spawned = []
    ok = ensure_running(_FakeClient([True]), spawn=spawned.append, exe=lambda: "x.exe")
    assert ok is True and spawned == []


def test_ensure_running_comes_up_after_polls():
    spawned = []
    clock = _Clock()
    client = _FakeClient([False, False, False, True])
    ok = ensure_running(client, spawn=spawned.append, sleep=clock.sleep, clock=clock,
                        exe=lambda: "C:\\o\\ollama.exe")
    assert ok is True
    assert spawned == [["C:\\o\\ollama.exe", "serve"]]


def test_ensure_running_never_up():
    spawned = []
    clock = _Clock()
    ok = ensure_running(_FakeClient([False]), spawn=spawned.append, sleep=clock.sleep, clock=clock,
                        exe=lambda: "o.exe", wait_seconds=10.0)
    assert ok is False
    assert len(spawned) == 1
    assert 10.0 <= clock.t <= 11.0


def test_ensure_running_no_exe():
    spawned = []
    ok = ensure_running(_FakeClient([False]), spawn=spawned.append, exe=lambda: None)
    assert ok is False and spawned == []


def test_ensure_running_spawn_raises():
    def bad(args):
        raise OSError("nope")

    assert ensure_running(_FakeClient([False]), spawn=bad, exe=lambda: "o.exe") is False


def test_ensure_running_exe_lookup_raises():
    def bad():
        raise RuntimeError("x")

    assert ensure_running(_FakeClient([False]), spawn=lambda a: None, exe=bad) is False

def _localhost_url(server):
    return f"http://localhost:{server.httpd.server_address[1]}"


def test_localhost_url_is_fast_and_works_with_ipv4_only_server(server):
    server.routes[("GET", "/api/tags")] = lambda req: (200, {"models": [{"name": "m"}]}, None)
    server.routes[("POST", "/api/chat")] = _chat_ok("ok")
    client = OllamaClient(_localhost_url(server), "m")
    assert client.url == _localhost_url(server)
    start = time.monotonic()
    assert client.is_up() is True
    assert time.monotonic() - start < 0.5
    assert client.chat("S", "U") == "ok"
    assert client.list_models() == ["m"]
    assert client.has_model() is True


def test_localhost_connects_to_literal_ipv4_address(server):
    seen = []

    def tags(req):
        seen.append(req.headers.get("Host"))
        return 200, {"models": []}, None

    server.routes[("GET", "/api/tags")] = tags
    assert OllamaClient(_localhost_url(server), "m").is_up() is True
    assert seen == [f"127.0.0.1:{server.httpd.server_address[1]}"]


def test_ipv6_loopback_literal_works():
    try:
        s6 = socket.socket(socket.AF_INET6)
        s6.bind(("::1", 0))
    except OSError:
        pytest.skip("IPv6 loopback not available")
    s6.close()

    class Srv6(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            data = b'{"models": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = Srv6(("::1", 0), H)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    t.start()
    try:
        assert OllamaClient(f"http://[::1]:{httpd.server_address[1]}", "m").is_up() is True
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(5)
