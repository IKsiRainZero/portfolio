from __future__ import annotations


def test_create_and_list_layer_link(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    layers = dims[0]["layers"]
    r = client.post("/api/layer-links", json={
        "source_layer_id": layers[0]["id"], "target_layer_id": layers[1]["id"],
        "relation_type": "leads_to", "note": "细胞构成组织"
    })
    assert r.status_code == 201
    listed = client.get(f"/api/dimensions/{dim_id}/layer-links").json()
    assert len(listed) == 1
    assert listed[0]["note"] == "细胞构成组织"


def test_delete_layer_link(client):
    dims = client.get("/api/dimensions").json()
    layers = dims[0]["layers"]
    link = client.post("/api/layer-links", json={
        "source_layer_id": layers[0]["id"], "target_layer_id": layers[2]["id"]
    }).json()
    assert client.delete(f"/api/layer-links/{link['id']}").status_code == 204
    assert client.delete(f"/api/layer-links/{link['id']}").status_code == 404
