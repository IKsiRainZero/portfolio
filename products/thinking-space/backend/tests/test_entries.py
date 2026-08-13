def test_create_entry(client):
    dims = client.get("/api/dimensions").json()
    layer_id = dims[0]["layers"][0]["id"]
    dim_id = dims[0]["id"]

    resp = client.post("/api/entries", json={
        "title": "线粒体功能",
        "content": "线粒体是细胞的能量工厂，负责ATP合成。",
        "entry_type": "known",
        "layer_id": layer_id,
        "dimension_id": dim_id,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "线粒体功能"
    assert data["status"] == "confirmed"
    assert data["entry_type"] == "known"

def test_list_entries_filtered(client):
    dims = client.get("/api/dimensions").json()
    layer_id = dims[0]["layers"][0]["id"]
    dim_id = dims[0]["id"]

    client.post("/api/entries", json={"title": "A", "dimension_id": dim_id, "layer_id": layer_id, "entry_type": "known"})
    client.post("/api/entries", json={"title": "B", "dimension_id": dim_id, "layer_id": layer_id, "entry_type": "unknown"})

    resp = client.get(f"/api/entries?layer_id={layer_id}&entry_type=known")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "A"

def test_confirm_entry(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]

    resp = client.post("/api/entries", json={
        "title": "Test", "dimension_id": dim_id, "source_type": "portfolio_index"
    })
    assert resp.json()["status"] == "pending"

    entry_id = resp.json()["id"]
    confirm = client.put(f"/api/entries/{entry_id}/confirm")
    assert confirm.json()["status"] == "confirmed"

def test_delete_entry(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    resp = client.post("/api/entries", json={"title": "ToDelete", "dimension_id": dim_id})
    entry_id = resp.json()["id"]
    del_resp = client.delete(f"/api/entries/{entry_id}")
    assert del_resp.status_code == 204
    get_resp = client.get(f"/api/entries?q=ToDelete")
    assert len(get_resp.json()) == 0
