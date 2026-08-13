def _layer_ids(client):
    dims = client.get("/api/dimensions").json()
    return dims[0]["id"], [l["id"] for l in dims[0]["layers"]]

def test_create_with_tags(client):
    dim_id, layers = _layer_ids(client)
    e = client.post("/api/entries", json={
        "title": "多标签", "dimension_id": dim_id, "tag_ids": [layers[0], layers[4]]
    }).json()
    assert set(e["tag_ids"]) == {layers[0], layers[4]}

def test_update_tags(client):
    dim_id, layers = _layer_ids(client)
    e = client.post("/api/entries", json={"title": "T", "dimension_id": dim_id, "tag_ids": [layers[0]]}).json()
    upd = client.put(f"/api/entries/{e['id']}", json={"tag_ids": [layers[1], layers[2]]}).json()
    assert set(upd["tag_ids"]) == {layers[1], layers[2]}

def test_default_no_tags(client):
    dim_id, _ = _layer_ids(client)
    e = client.post("/api/entries", json={"title": "N", "dimension_id": dim_id}).json()
    assert e["tag_ids"] == []
