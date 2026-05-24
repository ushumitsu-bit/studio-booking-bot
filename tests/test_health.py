async def test_health_returns_ok(api_client):
    r = await api_client.get("/miniapp/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["db"] == "ok"
    assert "ts" in d
