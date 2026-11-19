"""Voz local de WALL-E.

Sintetiza con Piper (CPU) y le da un color robótico y chiquito: tono un poco
más alto, un dejo metálico y una respiración de servo. Todo queda en disco
para que las frases repetidas salgan al instante.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import threading
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AI_DIR = ROOT
VOICE_MODEL = AI_DIR / "voices" / "es_ES-davefx-medium.onnx"
CACHE_DIR = AI_DIR / "datos" / "tts_cache"

MAX_CHARS = 360

_lock = threading.Lock()
_voice = None


class TtsUnavailable(RuntimeError):
    pass


def _load_voice():
    global _voice
    if _voice is not None:
        return _voice
    try:
        from piper import PiperVoice
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise TtsUnavailable("Piper no está instalado") from exc
    if not VOICE_MODEL.exists():
        raise TtsUnavailable("Falta la voz local de WALL-E")
    _voice = PiperVoice.load(VOICE_MODEL)
    return _voice


def _synth_raw(text: str) -> bytes:
    voice = _load_voice()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        voice.synthesize_wav(text, wav, set_wav_format=True)
    return buffer.getvalue()


def _robotize(raw: bytes) -> bytes:
    """Tono más alto y filo metálico sin cambiar la duración."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return raw

    with wave.open(io.BytesIO(raw), "rb") as source:
        rate = source.getframerate()
    pitch = 1.09
    filters = (
        f"asetrate={int(rate * pitch)},atempo={1 / pitch:.6f},"
        "highpass=f=150,lowpass=f=7400,"
        "vibrato=f=5.4:d=0.05,"
        "tremolo=f=42:d=0.05,"
        "acompressor=threshold=-19dB:ratio=3:attack=6:release=90,"
        "alimiter=limit=0.94"
    )
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-af",
                filters,
                "-ar",
                str(rate),
                "-ac",
                "1",
                "-f",
                "wav",
                "pipe:1",
            ],
            input=raw,
            capture_output=True,
            check=True,
            timeout=20,
        )
    except (subprocess.SubprocessError, OSError):
        return raw
    return result.stdout or raw


def synthesize(text: str) -> bytes:
    clean = " ".join((text or "").split()).strip()
    if not clean:
        raise ValueError("texto vacío")
    clean = clean[:MAX_CHARS]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:24]
    cached = CACHE_DIR / f"{key}.wav"
    if cached.exists():
        return cached.read_bytes()

    with _lock:
        if cached.exists():
            return cached.read_bytes()
        audio = _robotize(_synth_raw(clean))
        cached.write_bytes(audio)
    return audio


def warm() -> None:
    try:
        with _lock:
            _load_voice()
    except TtsUnavailable:
        pass
