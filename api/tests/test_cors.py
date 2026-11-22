import importlib


def test_cors_exact_and_regex(monkeypatch):
    monkeypatch.setenv("PPE_CORS_ORIGINS", "https://siteguard.vercel.app")
    monkeypatch.setenv("PPE_CORS_ORIGIN_REGEX", r"https://siteguard(-[a-z0-9-]+)?\.vercel\.app")
    import app.settings as s

    importlib.reload(s)
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=s.settings.cors_origins,
                       allow_origin_regex=s.settings.cors_origin_regex, allow_methods=["*"])

    @app.get("/x")
    def x():
        return {}

    c = TestClient(app)
    ok = lambda o: c.get("/x", headers={"Origin": o}).headers.get("access-control-allow-origin") == o
    assert ok("https://siteguard.vercel.app")
    assert ok("https://siteguard-git-feature-me.vercel.app")
    assert not ok("https://evil.vercel.app")
    assert not ok("https://siteguard.vercel.app.evil.com")
    importlib.reload(s)  # restore defaults for other tests
