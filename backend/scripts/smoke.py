import httpx

c = httpx.Client(base_url="http://127.0.0.1:8001")
print("health", c.get("/api/v1/health").json())
g = c.post("/api/v1/graphs", json={"title": "Smoke"}).json()
print("graph", g["id"])
a = c.post(
    f"/api/v1/graphs/{g['id']}/nodes",
    json={"title": "A", "position_x": 10, "position_y": 20},
).json()
b = c.post(
    f"/api/v1/graphs/{g['id']}/nodes",
    json={"title": "B", "position_x": 200, "position_y": 40},
).json()
e = c.post(
    f"/api/v1/graphs/{g['id']}/edges",
    json={"source_node_id": a["id"], "target_node_id": b["id"], "type": "IS_A"},
).json()
print("edge", e["type"])
r = c.delete(f"/api/v1/nodes/{a['id']}")
print("delete_node_status", r.status_code, r.json()["error"]["code"])
print("nodes", len(c.get(f"/api/v1/graphs/{g['id']}/nodes").json()))
