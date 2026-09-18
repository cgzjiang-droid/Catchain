from fastapi.testclient import TestClient

from catchain.api import create_app


def test_health_and_actor_boundary(tmp_path) -> None:
    app = create_app(database=tmp_path / "api.sqlite")
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/review/queue").status_code == 401
    assert client.get(
        "/review/queue", headers={"X-Actor": "alice", "X-Actor-Role": "reviewer"}
    ).status_code == 200

