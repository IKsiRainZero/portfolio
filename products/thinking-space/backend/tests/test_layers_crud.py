from __future__ import annotations

from app.models import LayerLink
from app.models.entry import entry_tags as entry_tags_table


def test_create_layer(client):
    dim = client.post("/api/dimensions", json={"name": "自定义链"}).json()
    r = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "起点", "description": "第一层"})
    assert r.status_code == 201
    assert r.json()["name"] == "起点"
    assert r.json()["level"] == 0


def test_update_layer(client):
    dims = client.get("/api/dimensions").json()
    lid = dims[0]["layers"][0]["id"]
    r = client.put(f"/api/layers/{lid}", json={"name": "细胞(改)", "description": "新描述"})
    assert r.json()["name"] == "细胞(改)"
    assert r.json()["description"] == "新描述"


def test_delete_layer(client):
    dim = client.post("/api/dimensions", json={"name": "L"}).json()
    lay = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "临时"}).json()
    assert client.delete(f"/api/layers/{lay['id']}").status_code == 204
    assert client.delete(f"/api/layers/{lay['id']}").status_code == 404


def test_delete_layer_cleans_orphan_rows(client, db):
    """Deleting a layer should remove related LayerLink and entry_tags rows."""
    dim = client.post("/api/dimensions", json={"name": "CleanupDim"}).json()
    dim_id = dim["id"]

    a = client.post(f"/api/dimensions/{dim_id}/layers", json={"name": "LayerA"}).json()
    b = client.post(f"/api/dimensions/{dim_id}/layers", json={"name": "LayerB"}).json()

    # Create a layer_link between them
    client.post("/api/layer-links", json={
        "source_layer_id": a["id"], "target_layer_id": b["id"]
    })

    # Create an entry tagged with LayerA
    e = client.post("/api/entries", json={
        "title": "TaggedEntry", "dimension_id": dim_id, "tag_ids": [a["id"]]
    }).json()
    assert a["id"] in e["tag_ids"]

    # Delete LayerA — should cascade cleanup
    assert client.delete(f"/api/layers/{a['id']}").status_code == 204

    # LayerLink row should be deleted from DB
    assert db.query(LayerLink).filter(
        (LayerLink.source_layer_id == a["id"]) | (LayerLink.target_layer_id == a["id"])
    ).count() == 0

    # entry_tags row should be deleted from DB
    assert db.execute(
        entry_tags_table.select().where(entry_tags_table.c.layer_id == a["id"])
    ).fetchone() is None

    # LayerLink list returns empty (source layer gone)
    links = client.get(f"/api/dimensions/{dim_id}/layer-links").json()
    assert len(links) == 0

    # Entry still exists and no longer references the deleted layer
    entry = client.get("/api/entries?q=TaggedEntry").json()
    assert len(entry) == 1
    assert a["id"] not in entry[0]["tag_ids"]


def test_reorder_layers(client):
    dim = client.post("/api/dimensions", json={"name": "R"}).json()
    a = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "A"}).json()
    b = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "B"}).json()
    r = client.put(f"/api/dimensions/{dim['id']}/layers/reorder", json={"layer_ids": [b["id"], a["id"]]})
    assert r.status_code == 200
    got = client.get(f"/api/dimensions/{dim['id']}").json()["layers"]
    assert [l["name"] for l in got] == ["B", "A"]
