"""Strike (onset) detection for percussion recordings.

Pipeline: load -> mono float32 @ 22050 Hz -> high-pass (cuts HVAC rumble) -> spectral-flux onset
strength -> peak picking -> backtrack -> sample-level refinement -> noise-floor gating.
"""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

TARGET_SR = 22050
HOP = 128  # ~5.8 ms frames
N_FFT = 1024
ABS_MIN_DB = -55.0  # never accept onsets quieter than this (dBFS RMS)
SILENCE_DB = -120.0


@dataclass
class OnsetParams:
    threshold: float = 0.07  # peak-pick delta on the normalised onset envelope (0-1)
    min_gap_s: float = 0.07  # minimum time between strikes
    pre_max_s: float = 0.03
    post_max_s: float = 0.03
    pre_avg_s: float = 0.10
    post_avg_s: float = 0.10
    highpass_hz: float = 70.0
    noise_floor_db: float | None = None  # from CalibrationProfile; None = estimate from clip
    gate_margin_db: float = 9.0  # onsets must be this far above the noise floor
    mask_window_s: float = 0.15  # an onset this soon after a louder strike...
    mask_drop_db: float = 9.0  # ...and this much quieter is treated as its decay/ring
    relative_gate_db: float = 30.0  # drop onsets this far below the typical strike level


@dataclass
class Onset:
    time_s: float
    strength: float  # normalised onset-envelope peak (0-1)
    level_db: float  # peak short-term RMS after the onset (dBFS)


@dataclass
class OnsetResult:
    onsets: list[Onset]
    confidence: float  # 0-1
    noise_floor_db: float
    snr_db: float
    duration_s: float
    rejected: list[Onset] = field(default_factory=list)  # gated below noise floor

    @property
    def times(self) -> np.ndarray:
        return np.array([o.time_s for o in self.onsets], dtype=float)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- loading


def load_audio(source, sr: int | None = None) -> tuple[np.ndarray, int]:
    """Load a WAV path / bytes / file-like / ndarray into mono float32 at TARGET_SR."""
    if isinstance(source, np.ndarray):
        if sr is None:
            raise ValueError("sr is required when passing an array")
        y = source.astype(np.float32)
    else:
        if isinstance(source, bytes | bytearray):
            source = io.BytesIO(source)
        y, sr = sf.read(source, dtype="float32", always_2d=True)
        y = y.mean(axis=1)
    if y.ndim > 1:
        y = y.mean(axis=-1 if y.shape[-1] <= 2 else 0)
    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)
    return np.ascontiguousarray(y, dtype=np.float32), TARGET_SR


def highpass(y: np.ndarray, sr: int, cutoff: float) -> np.ndarray:
    if cutoff <= 0 or len(y) < 32:
        return y
    sos = butter(4, cutoff, btype="high", fs=sr, output="sos")
    return sosfiltfilt(sos, y).astype(np.float32)


def _db(x: np.ndarray | float) -> np.ndarray | float:
    return 20.0 * np.log10(np.maximum(x, 1e-6))


def frame_rms_db(y: np.ndarray, frame: int = 1024, hop: int = 256) -> np.ndarray:
    if len(y) < frame:
        y = np.pad(y, (0, frame - len(y)))
    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=hop, center=True)[0]
    return _db(rms)


def estimate_noise_floor_db(y: np.ndarray, percentile: float = 20.0) -> float:
    """Background level of a clip: a low percentile of short-term RMS (dBFS)."""
    if not np.any(y):
        return SILENCE_DB
    return float(np.percentile(frame_rms_db(y), percentile))


# ---------------------------------------------------------------- detection


def _refine(y_env: np.ndarray, sr: int, t_peak: float, lo_bound: float) -> float:
    """Move an onset to the start of the attack using a sample-level amplitude envelope."""
    a = max(int((t_peak - 0.04) * sr), int(lo_bound * sr), 0)
    b = min(int((t_peak + 0.04) * sr), len(y_env))
    if b - a < 4:
        return t_peak
    seg = y_env[a:b]
    ipk = int(np.argmax(seg))
    imin = int(np.argmin(seg[: ipk + 1]))
    thr = seg[imin] + 0.2 * (seg[ipk] - seg[imin])
    above = np.nonzero(seg[imin : ipk + 1] >= thr)[0]
    idx = imin + (int(above[0]) if len(above) else 0)
    return (a + idx) / sr


def detect_onsets(
    y: np.ndarray, sr: int = TARGET_SR, params: OnsetParams | None = None
) -> OnsetResult:
    """Detect strikes in a mono float32 signal (already at TARGET_SR)."""
    p = params or OnsetParams()
    duration = len(y) / sr
    y = highpass(y, sr, p.highpass_hz)
    floor_est = estimate_noise_floor_db(y)
    floor = max(floor_est, p.noise_floor_db) if p.noise_floor_db is not None else floor_est

    if not np.any(np.abs(y) > 1e-5):
        return OnsetResult([], 0.0, floor, 0.0, duration)

    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP, n_fft=N_FFT)
    env = env - env.min()
    if env.max() <= 0:
        return OnsetResult([], 0.0, floor, 0.0, duration)
    env = env / env.max()

    fps = sr / HOP
    frames = librosa.util.peak_pick(
        env,
        pre_max=max(1, int(p.pre_max_s * fps)),
        post_max=max(1, int(p.post_max_s * fps)),
        pre_avg=max(1, int(p.pre_avg_s * fps)),
        post_avg=max(1, int(p.post_avg_s * fps)),
        delta=p.threshold,
        wait=max(1, int(p.min_gap_s * fps)),
    )
    frames = np.asarray(frames, dtype=int)
    back = librosa.onset.onset_backtrack(frames, env) if len(frames) else frames

    # Sample-level amplitude envelope (1 ms smoothing) for refinement and levels.
    k = max(1, int(0.001 * sr))
    y_env = np.convolve(np.abs(y), np.ones(k) / k, mode="same")
    rms_db = frame_rms_db(y, frame=512, hop=64)
    rms_fps = sr / 64

    accepted: list[Onset] = []
    rejected: list[Onset] = []
    prev = 0.0
    for f_peak, f_back in zip(frames, back, strict=True):
        t_peak = librosa.frames_to_time(f_peak, sr=sr, hop_length=HOP)
        t_back = librosa.frames_to_time(f_back, sr=sr, hop_length=HOP)
        t = _refine(y_env, sr, max(t_peak, t_back), lo_bound=max(prev, t_back - 0.01))
        i0, i1 = int(t * rms_fps), int((t + 0.06) * rms_fps) + 1
        level = float(np.max(rms_db[i0:i1])) if i1 > i0 and i0 < len(rms_db) else SILENCE_DB
        onset = Onset(time_s=round(float(t), 5), strength=float(env[f_peak]), level_db=level)
        masked = any(
            0 < t - a.time_s <= p.mask_window_s and a.level_db - level >= p.mask_drop_db
            for a in accepted[-3:]
        )
        if level >= max(floor + p.gate_margin_db, ABS_MIN_DB) and not masked:
            accepted.append(onset)
            prev = t + p.min_gap_s / 2
        else:
            rejected.append(onset)

    if accepted:
        typical = float(np.median([o.level_db for o in accepted]))
        keep = [o for o in accepted if o.level_db >= typical - p.relative_gate_db]
        rejected += [o for o in accepted if o.level_db < typical - p.relative_gate_db]
        accepted = keep

    confidence, snr = _confidence(accepted, floor, p.threshold)
    return OnsetResult(accepted, confidence, floor, snr, duration, rejected)


def _confidence(onsets: list[Onset], floor_db: float, threshold: float) -> tuple[float, float]:
    """Confidence 0-1 from peak-to-noise ratio and the share of near-threshold onsets."""
    if not onsets:
        return 0.0, 0.0
    snr = float(np.median([o.level_db for o in onsets]) - floor_db)
    snr_conf = float(np.clip((snr - 6.0) / (24.0 - 6.0), 0.0, 1.0))
    near = np.mean([o.strength < max(2.5 * threshold, 0.15) for o in onsets])
    return round(snr_conf * (1.0 - 0.6 * float(near)), 3), round(snr, 2)


def analyze_clip(source, sr: int | None = None, params: OnsetParams | None = None) -> OnsetResult:
    y, sr = load_audio(source, sr)
    return detect_onsets(y, sr, params)
