def test_create_and_delete_cross_link(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]

    e1 = client.post("/api/entries", json={"title": "E1", "dimension_id": dim_id}).json()
    e2 = client.post("/api/entries", json={"title": "E2", "dimension_id": dim_id}).json()

    resp = client.post("/api/cross-links", json={
        "source_entry_id": e1["id"], "target_entry_id": e2["id"], "relation_type": "supports"
    })
    assert resp.status_code == 201
    assert resp.json()["relation_type"] == "supports"

    del_resp = client.delete(f"/api/cross-links/{resp.json()['id']}")
    assert del_resp.status_code == 204
