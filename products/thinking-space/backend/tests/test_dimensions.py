def test_get_dimensions_returns_seeded_data(client):
    response = client.get("/api/dimensions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "物质层次"
    assert len(data[0]["layers"]) == 10
    assert data[0]["layers"][0]["name"] == "细胞"
    assert data[0]["layers"][9]["name"] == "宇宙"

def test_dimension_not_found(client):
    response = client.get("/api/dimensions/nonexistent")
    assert response.status_code == 404
