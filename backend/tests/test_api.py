"""Small end-to-end API smoke test.

The test creates a project, a hierarchical codebook, a text source and a
search request.  It catches schema or routing errors before the application is
released.
"""
import os
import tempfile


def test_basic_research_workflow(monkeypatch):
    # main.py reads configuration at import time, so use a fresh process-like
    # module import with a temporary data directory for this isolated test.
    data = tempfile.mkdtemp()
    monkeypatch.setenv("DATA_DIR", data)
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("ENCRYPTION_ENABLED", "true")

    import importlib
    import app.config as config
    import app.db as db
    config.DATA_DIR = __import__("pathlib").Path(data)
    config.DB_PATH = config.DATA_DIR / "qualicoder.db"
    db.DB_PATH = config.DB_PATH
    db.init_db()

    from fastapi.testclient import TestClient
    import app.main as main
    client = TestClient(main.app)

    project = client.post("/api/projects", json={"title":"Smoke test"})
    assert project.status_code == 200
    pid = project.json()["id"]

    parent = client.post(f"/api/projects/{pid}/codes", json={"name":"Trust"})
    assert parent.status_code == 200
    parent_id = parent.json()["id"]
    child = client.post(f"/api/projects/{pid}/codes", json={"name":"Reliability","parent_id":parent_id})
    assert child.status_code == 200

    source = client.post(f"/api/projects/{pid}/sources/upload", files={"file":("interview.txt",b"I trust the service.","text/plain")})
    assert source.status_code == 200
    sid = source.json()["id"]

    segments = client.get(f"/api/projects/{pid}/sources/{sid}/segments")
    assert segments.status_code == 200
    assert segments.json()[0]["text"] == "I trust the service."

    result = client.post(f"/api/projects/{pid}/search", json={"query":"trust"})
    assert result.status_code == 200
    assert result.json()["results"]
