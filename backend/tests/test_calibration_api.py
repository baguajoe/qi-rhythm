import io
import json

import numpy as np
import soundfile as sf

from app.audio.synth import SynthOptions, render, voice_sample

from .helpers import auth_headers


def wav_bytes(y, sr):
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def upload(client, h, step, y, sr, **fields):
    data = {"audio": (io.BytesIO(wav_bytes(y, sr)), "clip.wav"), **fields}
    return client.post(
        f"/api/calibration/analyze/{step}", data=data, headers=h, content_type="multipart/form-data"
    )


def test_noise_step(client):
    h = auth_headers(client)
    rng = np.random.default_rng(0)
    y = (rng.standard_normal(48000 * 5) * 0.003).astype(np.float32)
    res = upload(client, h, "noise", y, 48000)
    assert res.status_code == 200
    body = res.get_json()
    assert -55 < body["noise_floor_db"] < -45
    assert "quiet" in body["message"]


def test_latency_step(client):
    h = auth_headers(client)
    clicks = {
        "count_in_beats": 0,
        "length_beats": 8,
        "events": [{"beat": b, "voice": "low"} for b in range(8)],
    }
    s = render(clicks, SynthOptions(bpm=100, latency_ms=110, jitter_ms=6, seed=3))
    click_times = [s.countin_start_s + b * 0.6 for b in range(8)]
    res = upload(client, h, "latency", s.audio, s.sr, click_times=json.dumps(click_times))
    body = res.get_json()
    assert body["reliable"] is True
    assert abs(body["latency_offset_ms"] - 110) < 15
    bad = upload(client, h, "latency", s.audio, s.sr)
    assert bad.status_code == 400


def test_sensitivity_step(client):
    h = auth_headers(client)
    sr = 44100
    rng = np.random.default_rng(0)
    y = rng.standard_normal(sr * 3) * 0.002
    hit = voice_sample("low", sr, rng)
    y[int(0.8 * sr) : int(0.8 * sr) + len(hit)] += 0.06 * hit
    y[int(1.8 * sr) : int(1.8 * sr) + len(hit)] += 0.8 * hit
    res = upload(client, h, "sensitivity", y.astype(np.float32), sr, noise_floor_db="-54")
    body = res.get_json()
    assert body["ok"] is True and 0.03 <= body["onset_threshold"] <= 0.3


def test_missing_audio(client):
    h = auth_headers(client)
    res = client.post(
        "/api/calibration/analyze/noise", data={}, headers=h, content_type="multipart/form-data"
    )
    assert res.status_code == 400


def test_save_and_list_profiles(client):
    h = auth_headers(client)
    res = client.post(
        "/api/calibration",
        json={
            "device_label": "Activity room laptop",
            "latency_offset_ms": 85.5,
            "noise_floor_db": -52.0,
            "onset_threshold": 0.06,
        },
        headers=h,
    )
    assert res.status_code == 201
    client.post(
        "/api/calibration", json={"device_label": "Dining hall", "latency_offset_ms": 40}, headers=h
    )
    profiles = client.get("/api/calibration", headers=h).get_json()["profiles"]
    assert [p["device_label"] for p in profiles] == ["Dining hall", "Activity room laptop"]
    assert (
        client.post(
            "/api/calibration", json={"device_label": "x", "latency_offset_ms": 5000}, headers=h
        ).status_code
        == 400
    )
    other = auth_headers(client, email="other@example.com")
    assert client.get("/api/calibration", headers=other).get_json()["profiles"] == []
