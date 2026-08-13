from __future__ import annotations


def test_update_entry_preserves_z_depth(client):
    """PUT /api/entries/{id} with z_depth should persist (not be silently dropped)."""
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    e = client.post("/api/entries", json={"title": "DepthCheck", "dimension_id": dim_id}).json()
    assert e["z_depth"] == 0.0

    r = client.put(f"/api/entries/{e['id']}", json={"title": "DepthCheck Updated", "z_depth": 0.5})
    assert r.status_code == 200
    d = r.json()
    assert d["z_depth"] == 0.5
    assert d["title"] == "DepthCheck Updated"


def test_update_geometry(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    e = client.post("/api/entries", json={"title": "G", "dimension_id": dim_id}).json()
    assert e["x"] == 0 and e["width"] == 200

    r = client.put(f"/api/entries/{e['id']}/geometry",
                   json={"x": 120.5, "y": 80.0, "width": 260, "height": 150, "z_depth": 0.4})
    assert r.status_code == 200
    d = r.json()
    assert d["x"] == 120.5 and d["y"] == 80.0
    assert d["width"] == 260 and d["z_depth"] == 0.4


def test_update_geometry_partial(client):
    dims = client.get("/api/dimensions").json()
    e = client.post("/api/entries", json={"title": "P", "dimension_id": dims[0]["id"]}).json()
    r = client.put(f"/api/entries/{e['id']}/geometry", json={"x": 10, "y": 20})
    assert r.json()["x"] == 10 and r.json()["width"] == 200  # 未传保持默认


def test_geometry_404(client):
    r = client.put("/api/entries/nope/geometry", json={"x": 1, "y": 2})
    assert r.status_code == 404
