import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.album import AlbumBatch, AlbumTrack

client = TestClient(app)


def _cleanup_batch(batch_id: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(AlbumTrack).where(AlbumTrack.album_batch_id == uuid.UUID(batch_id)))
        db.execute(delete(AlbumBatch).where(AlbumBatch.id == uuid.UUID(batch_id)))
        db.commit()
    finally:
        db.close()


def test_list_album_concepts_returns_the_real_catalog() -> None:
    response = client.get("/api/v1/albums/concepts")

    assert response.status_code == 200
    body = response.json()
    ids = {c["id"] for c in body}
    assert {"focus", "relaxation", "mind_clearness"} <= ids


def test_concepts_route_does_not_collide_with_album_id_route() -> None:
    # /albums/concepts must resolve to the concepts list, not attempt to
    # parse "concepts" as a UUID for /albums/{album_id}.
    response = client.get("/api/v1/albums/concepts")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_album_creates_ten_tracks() -> None:
    response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Focus Album", "seed": 1}
    )

    assert response.status_code == 200
    body = response.json()
    try:
        assert body["status"] == "generating"
        assert body["concept_id"] == "focus"
        assert sum(body["track_summary"].values()) == 10
        assert body["track_summary"].get("pending") == 10
    finally:
        _cleanup_batch(body["id"])


def test_create_album_rejects_unknown_concept() -> None:
    response = client.post("/api/v1/albums", json={"concept_id": "not_a_real_concept"})

    assert response.status_code == 400


def test_get_album_returns_full_track_detail() -> None:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "relaxation", "title": "Test Relax Album", "seed": 2}
    )
    batch_id = create_response.json()["id"]

    try:
        response = client.get(f"/api/v1/albums/{batch_id}")

        assert response.status_code == 200
        body = response.json()
        assert len(body["tracks"]) == 10
        assert all(track["status"] == "pending" for track in body["tracks"])
        assert body["tracks"][0]["sequence_index"] == 0
    finally:
        _cleanup_batch(batch_id)


def test_get_album_returns_404_for_unknown_id() -> None:
    response = client.get(f"/api/v1/albums/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_albums_includes_a_newly_created_batch() -> None:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "mind_clearness", "title": "Test List Album", "seed": 3}
    )
    batch_id = create_response.json()["id"]

    try:
        response = client.get("/api/v1/albums")

        assert response.status_code == 200
        assert any(b["id"] == batch_id for b in response.json())
    finally:
        _cleanup_batch(batch_id)


def test_cancel_album_sets_status_to_cancelled() -> None:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Cancel Album", "seed": 4}
    )
    batch_id = create_response.json()["id"]

    try:
        response = client.post(f"/api/v1/albums/{batch_id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    finally:
        _cleanup_batch(batch_id)


def test_cancel_album_returns_404_for_unknown_id() -> None:
    response = client.post(f"/api/v1/albums/{uuid.uuid4()}/cancel")

    assert response.status_code == 404
