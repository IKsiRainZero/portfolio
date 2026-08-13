def test_create_dimension(client):
    r = client.post("/api/dimensions", json={"name": "时间维度", "description": "以时间为轴"})
    assert r.status_code == 201
    assert r.json()["name"] == "时间维度"
    assert r.json()["layers"] == []


def test_update_dimension(client):
    d = client.post("/api/dimensions", json={"name": "旧名"}).json()
    r = client.put(f"/api/dimensions/{d['id']}", json={"name": "新名"})
    assert r.json()["name"] == "新名"


def test_delete_dimension(client):
    d = client.post("/api/dimensions", json={"name": "待删"}).json()
    assert client.delete(f"/api/dimensions/{d['id']}").status_code == 204
    assert client.get(f"/api/dimensions/{d['id']}").status_code == 404
