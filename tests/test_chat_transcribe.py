"""Voice questions in the lesson chat: audio in, composer text out."""

TRANSCRIBE_PATH = "/api/v1/chat/transcribe"
WAV_DATA_URL = "data:audio/wav;base64," + "A" * 64


async def test_transcribe_returns_text(client):
    response = await client.post(TRANSCRIBE_PATH, json={"audio": WAV_DATA_URL})
    assert response.status_code == 200
    assert response.json()["text"]


async def test_transcribe_needs_auth(client, auth):
    auth.user = None
    response = await client.post(TRANSCRIBE_PATH, json={"audio": WAV_DATA_URL})
    assert response.status_code == 401


async def test_transcribe_rejects_non_audio_data_url(client):
    response = await client.post(
        TRANSCRIBE_PATH, json={"audio": "data:image/png;base64," + "A" * 64}
    )
    assert response.status_code == 400


async def test_transcribe_rejects_oversized_recording(client):
    response = await client.post(
        TRANSCRIBE_PATH, json={"audio": "data:audio/wav;base64," + "A" * 4_000_001}
    )
    assert response.status_code == 400
