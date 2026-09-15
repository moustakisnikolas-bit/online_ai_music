import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.album import AlbumBatch, AlbumTrack
from app.models.album_track_short import AlbumTrackShort
from app.models.audio_job import AudioJob
from app.models.youtube_publishing import YouTubePublication
from app.repositories.album_track_shorts import create_album_track_short
from app.repositories.albums import list_album_tracks, update_album_track
from app.repositories.youtube import create_youtube_publication, mark_publication_uploaded
from app.services.album_pipeline import TRACKS_PER_ALBUM

client = TestClient(app)


def _cleanup_batch(batch_id: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(AlbumTrack).where(AlbumTrack.album_batch_id == uuid.UUID(batch_id)))
        db.execute(delete(AlbumBatch).where(AlbumBatch.id == uuid.UUID(batch_id)))
        db.commit()
    finally:
        db.close()


def _cleanup_short(short_id: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(AlbumTrackShort).where(AlbumTrackShort.id == uuid.UUID(short_id)))
        db.commit()
    finally:
        db.close()


def test_list_album_concepts_returns_the_real_catalog() -> None:
    response = client.get("/api/v1/albums/concepts")

    assert response.status_code == 200
    body = response.json()
    ids = {c["id"] for c in body}
    assert {"focus", "relaxation", "mind_clearness", "sleep", "healing", "study", "chakra"} <= ids


def test_list_album_concepts_exposes_brainwave_bands_and_noise_colors() -> None:
    # Real regression test for a real bug: AlbumConceptResponse not
    # declaring brainwave_bands meant FastAPI's response_model filtering
    # silently dropped it from every response, even though the concept
    # catalog itself always had it.
    response = client.get("/api/v1/albums/concepts")

    body = {c["id"]: c for c in response.json()}
    assert body["chakra"]["brainwave_bands"] == ["theta", "alpha"]
    assert "violet_noise" in body["chakra"]["noise_type_preference"]
    assert "blue_noise" in body["study"]["noise_type_preference"]


def test_concepts_route_does_not_collide_with_album_id_route() -> None:
    # /albums/concepts must resolve to the concepts list, not attempt to
    # parse "concepts" as a UUID for /albums/{album_id}.
    response = client.get("/api/v1/albums/concepts")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_album_creates_tracks_per_album_tracks() -> None:
    response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Focus Album", "seed": 1}
    )

    assert response.status_code == 200
    body = response.json()
    try:
        assert body["status"] == "generating"
        assert body["concept_id"] == "focus"
        assert sum(body["track_summary"].values()) == TRACKS_PER_ALBUM
        assert body["track_summary"].get("pending") == TRACKS_PER_ALBUM
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
        assert len(body["tracks"]) == TRACKS_PER_ALBUM
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


def test_delete_album_removes_it_and_its_tracks() -> None:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Delete Album", "seed": 5}
    )
    batch_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/albums/{batch_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] is True
    assert body["tracks_deleted"] == TRACKS_PER_ALBUM
    assert client.get(f"/api/v1/albums/{batch_id}").status_code == 404

    db = SessionLocal()
    try:
        assert list_album_tracks(db, uuid.UUID(batch_id)) == []
    finally:
        db.close()


def test_delete_album_returns_404_for_unknown_id() -> None:
    response = client.delete(f"/api/v1/albums/{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_album_refuses_when_a_track_is_already_published() -> None:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Published Album", "seed": 6}
    )
    batch_id = create_response.json()["id"]

    db = SessionLocal()
    try:
        track = list_album_tracks(db, uuid.UUID(batch_id))[0]
        update_album_track(db, track, uploaded_at=datetime.now(timezone.utc))
    finally:
        db.close()

    try:
        response = client.delete(f"/api/v1/albums/{batch_id}")

        assert response.status_code == 409
        assert "already published" in response.json()["detail"].lower()
        # Refused -- the album must still exist.
        assert client.get(f"/api/v1/albums/{batch_id}").status_code == 200
    finally:
        _cleanup_batch(batch_id)


def test_delete_album_with_force_deletes_even_when_published() -> None:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Forced Delete Album", "seed": 7}
    )
    batch_id = create_response.json()["id"]

    db = SessionLocal()
    try:
        track = list_album_tracks(db, uuid.UUID(batch_id))[0]
        update_album_track(db, track, uploaded_at=datetime.now(timezone.utc))
    finally:
        db.close()

    response = client.delete(f"/api/v1/albums/{batch_id}?force=true")

    assert response.status_code == 200
    assert client.get(f"/api/v1/albums/{batch_id}").status_code == 404


def _create_album_and_track() -> tuple[str, str]:
    create_response = client.post(
        "/api/v1/albums", json={"concept_id": "focus", "title": "Test Shorts Album", "seed": 8}
    )
    batch_id = create_response.json()["id"]

    db = SessionLocal()
    try:
        track = list_album_tracks(db, uuid.UUID(batch_id))[0]
        track_id = str(track.id)
    finally:
        db.close()

    return batch_id, track_id


def test_list_track_shorts_returns_accurate_status_counts() -> None:
    batch_id, track_id = _create_album_and_track()

    before = client.get("/api/v1/albums/shorts?limit=500").json()["summary"]

    db = SessionLocal()
    try:
        pending = create_album_track_short(
            db, album_track_id=uuid.UUID(track_id), clip_index=0, start_offset_seconds=0, duration_seconds=28
        )
        uploaded = create_album_track_short(
            db, album_track_id=uuid.UUID(track_id), clip_index=1, start_offset_seconds=300, duration_seconds=28
        )
        uploaded.status = "uploaded"
        db.commit()
        pending_id = str(pending.id)
        uploaded_id = str(uploaded.id)
    finally:
        db.close()

    try:
        response = client.get("/api/v1/albums/shorts?limit=500")

        assert response.status_code == 200
        body = response.json()
        after = body["summary"]
        assert after.get("pending", 0) == before.get("pending", 0) + 1
        assert after.get("uploaded", 0) == before.get("uploaded", 0) + 1

        ids = {s["id"] for s in body["shorts"]}
        assert pending_id in ids
        assert uploaded_id in ids
        matching = next(s for s in body["shorts"] if s["id"] == pending_id)
        assert matching["track_title"]
        assert matching["concept_id"] == "focus"
    finally:
        _cleanup_short(pending_id)
        _cleanup_short(uploaded_id)
        _cleanup_batch(batch_id)


def test_delete_track_short_removes_a_not_yet_uploaded_short_cleanly() -> None:
    batch_id, track_id = _create_album_and_track()

    db = SessionLocal()
    try:
        short = create_album_track_short(
            db, album_track_id=uuid.UUID(track_id), clip_index=0, start_offset_seconds=0, duration_seconds=28
        )
        short_id = str(short.id)
    finally:
        db.close()

    try:
        response = client.delete(f"/api/v1/albums/shorts/{short_id}")

        assert response.status_code == 200
        assert response.json()["deleted"] is True

        listing = client.get("/api/v1/albums/shorts?limit=500").json()
        assert short_id not in {s["id"] for s in listing["shorts"]}
    finally:
        _cleanup_batch(batch_id)


def test_delete_track_short_returns_404_for_unknown_id() -> None:
    response = client.delete(f"/api/v1/albums/shorts/{uuid.uuid4()}")

    assert response.status_code == 404


def test_delete_track_short_refuses_when_already_published_unless_forced() -> None:
    batch_id, track_id = _create_album_and_track()

    db = SessionLocal()
    try:
        short = create_album_track_short(
            db, album_track_id=uuid.UUID(track_id), clip_index=0, start_offset_seconds=0, duration_seconds=28
        )
        # audio_job_id is a real, enforced FK on youtube_publications --
        # a fresh AudioJob row is needed, not just a random UUID.
        audio_job = AudioJob(
            title="Fake Short Audio",
            mode="mixed_ambient",
            channels="stereo",
            duration_seconds=28,
            status="completed",
            review_status="approved",
        )
        db.add(audio_job)
        db.commit()
        db.refresh(audio_job)

        publication = create_youtube_publication(
            db,
            audio_job_id=audio_job.id,
            video_filename="fake-short.mp4",
            title="Fake Short",
            video_kind="short",
        )
        publication = mark_publication_uploaded(
            db,
            publication,
            youtube_video_id="fake-real-video-id",
            youtube_url="https://youtube.com/shorts/fake-real-video-id",
        )
        short.youtube_publication_id = publication.id
        db.commit()
        short_id = str(short.id)
        publication_id = str(publication.id)
        audio_job_id = str(audio_job.id)
    finally:
        db.close()

    try:
        refused = client.delete(f"/api/v1/albums/shorts/{short_id}")
        assert refused.status_code == 409
        assert "already been published" in refused.json()["detail"].lower()

        forced = client.delete(f"/api/v1/albums/shorts/{short_id}?force=true")
        assert forced.status_code == 200
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(YouTubePublication).where(YouTubePublication.id == uuid.UUID(publication_id)))
            db.execute(delete(AudioJob).where(AudioJob.id == uuid.UUID(audio_job_id)))
            db.commit()
        finally:
            db.close()
        _cleanup_batch(batch_id)


def test_delete_track_short_never_touches_the_parent_track() -> None:
    batch_id, track_id = _create_album_and_track()

    db = SessionLocal()
    try:
        short = create_album_track_short(
            db, album_track_id=uuid.UUID(track_id), clip_index=0, start_offset_seconds=0, duration_seconds=28
        )
        short_id = str(short.id)
    finally:
        db.close()

    before = client.get(f"/api/v1/albums/{batch_id}").json()

    try:
        response = client.delete(f"/api/v1/albums/shorts/{short_id}")
        assert response.status_code == 200

        after = client.get(f"/api/v1/albums/{batch_id}").json()
        assert after == before
    finally:
        _cleanup_batch(batch_id)
