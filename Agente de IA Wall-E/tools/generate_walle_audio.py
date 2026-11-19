"""Genera los sonidos originales de WALL-E para la cabina.

No usa samples de la película: sintetiza chirridos, servos, orugas, carga solar
y un loop ambiente inspirado en el diseño sonoro de Ben Burtt (voz filtrada,
mecanismos eléctricos, chimes suaves). Salida: ui/public/sounds/*.wav

Uso: python tools/generate_walle_audio.py
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ui" / "public" / "sounds"
RATE = 44100


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def write_wav(name: str, samples: list[float], rate: int = RATE) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    peak = max(1e-9, max(abs(sample) for sample in samples))
    gain = min(1.0, 0.92 / peak)
    frames = bytearray()
    for sample in samples:
        frames += struct.pack("<h", int(clamp(sample * gain) * 32767))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(frames))
    print(f"[ok] {name} · {len(samples) / rate:.2f}s · {path.stat().st_size / 1024:.0f} KB")


def write_wav_stereo(name: str, left: list[float], right: list[float], rate: int = 22050) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    peak = max(1e-9, max(max(abs(v) for v in left), max(abs(v) for v in right)))
    gain = min(1.0, 0.92 / peak)
    frames = bytearray()
    for l_sample, r_sample in zip(left, right):
        frames += struct.pack("<hh", int(clamp(l_sample * gain) * 32767), int(clamp(r_sample * gain) * 32767))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(frames))
    print(f"[ok] {name} · {len(left) / rate:.2f}s · {path.stat().st_size / 1024:.0f} KB")


def silence(duration: float, rate: int = RATE) -> list[float]:
    return [0.0] * int(duration * rate)


def mix(target: list[float], source: list[float], at: float, gain: float = 1.0, rate: int = RATE) -> None:
    start = int(at * rate)
    for index, sample in enumerate(source):
        position = start + index
        if position >= len(target):
            break
        target[position] += sample * gain


def lowpass(samples: list[float], cutoff: float, rate: int = RATE) -> list[float]:
    alpha = clamp(1.0 - math.exp(-2.0 * math.pi * cutoff / rate), 0.0, 1.0)
    out = []
    state = 0.0
    for sample in samples:
        state += alpha * (sample - state)
        out.append(state)
    return out


def highpass(samples: list[float], cutoff: float, rate: int = RATE) -> list[float]:
    low = lowpass(samples, cutoff, rate)
    return [sample - low_sample for sample, low_sample in zip(samples, low)]


def enveloped(
    samples: list[float],
    attack: float,
    release: float,
    rate: int = RATE,
) -> list[float]:
    total = len(samples)
    attack_n = max(1, int(attack * rate))
    release_n = max(1, int(release * rate))
    out = [0.0] * total
    for index, sample in enumerate(samples):
        if index < attack_n:
            env = index / attack_n
        elif index > total - release_n:
            env = max(0.0, (total - index) / release_n)
        else:
            env = 1.0
        out[index] = sample * env
    return out


def robot_voice(
    start_freq: float,
    end_freq: float,
    duration: float,
    harmonics: tuple[float, ...] = (1.0, 0.55, 0.32, 0.18, 0.09),
    wobble: float = 0.0,
    rate: int = RATE,
) -> list[float]:
    total = int(duration * rate)
    out = [0.0] * total
    phase = 0.0
    for index in range(total):
        t = index / total
        freq = start_freq + (end_freq - start_freq) * (t * t * (3 - 2 * t))
        freq *= 1.0 + math.sin(t * math.pi * 2 * 5.5) * wobble
        phase += 2.0 * math.pi * freq / rate
        sample = 0.0
        for harmonic, amplitude in enumerate(harmonics, start=1):
            sample += math.sin(phase * harmonic) * amplitude
        # Un poco de ruido de garganta mecánica.
        sample += (random.random() * 2 - 1) * 0.05
        out[index] = sample * 0.32
    return enveloped(out, 0.025, 0.12, rate)


def click(duration: float = 0.02, tone: float = 1400.0, rate: int = RATE) -> list[float]:
    total = int(duration * rate)
    out = []
    for index in range(total):
        t = index / total
        env = math.exp(-t * 9.0)
        out.append((random.random() * 2 - 1) * 0.4 * env + math.sin(2 * math.pi * tone * index / rate) * 0.2 * env)
    return out


def servo(duration: float = 0.9, base: float = 108.0) -> list[float]:
    total = int(duration * RATE)
    out = [0.0] * total
    phase = 0.0
    for index in range(total):
        t = index / total
        freq = base + math.sin(t * math.pi * 2 * 2.2) * 16 + math.sin(t * math.pi * 2 * 11) * 3
        phase += 2.0 * math.pi * freq / RATE
        saw = 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
        out[index] = saw * 0.2 + (random.random() * 2 - 1) * 0.045
    out = lowpass(out, 720)
    # Golpecitos de engranaje.
    for tick in (0.12, 0.3, 0.51, 0.73):
        mix(out, click(0.025, 900), tick, 0.25)
    return enveloped(out, 0.04, 0.18)


def tread_loop(duration: float = 2.4) -> list[float]:
    total = int(duration * RATE)
    out = [0.0] * total
    phase = 0.0
    for index in range(total):
        t = index / RATE
        freq = 54 + math.sin(2 * math.pi * 1.25 * t) * 6
        phase += 2.0 * math.pi * freq / RATE
        rumble = math.sin(phase) * 0.3 + math.sin(phase * 2) * 0.08
        out[index] = rumble + (random.random() * 2 - 1) * 0.055
    out = lowpass(out, 240)
    # Eslabones: pulso cada 0.3 s, exactamente 8 por loop para que cierre.
    for step in range(8):
        mix(out, click(0.04, 520), step * 0.3, 0.22)
    # Cierre circular sin salto.
    fade = int(0.08 * RATE)
    for index in range(fade):
        blend = index / fade
        out[index] = out[index] * blend + out[total - fade + index] * (1 - blend)
    return out[: total - fade]


def charge() -> list[float]:
    out = silence(1.8)
    for step, (freq, at) in enumerate([(523.25, 0.0), (659.25, 0.18), (783.99, 0.36), (1046.5, 0.54)]):
        tone = robot_voice(freq, freq * 1.01, 0.9, harmonics=(1.0, 0.3, 0.12), wobble=0.004)
        mix(out, tone, at, 0.34)
    shimmer = []
    for index in range(int(1.2 * RATE)):
        t = index / RATE
        shimmer.append(math.sin(2 * math.pi * (1568 + t * 320) * t) * math.exp(-t * 2.2) * 0.1)
    mix(out, shimmer, 0.55, 0.8)
    return enveloped(out, 0.02, 0.35)


def boot() -> list[float]:
    out = silence(2.2)
    for freq, at, gain in [(392.0, 0.0, 0.26), (523.25, 0.16, 0.24), (659.25, 0.32, 0.22), (783.99, 0.5, 0.2)]:
        tone = robot_voice(freq, freq, 1.4, harmonics=(1.0, 0.4, 0.16, 0.08), wobble=0.003)
        mix(out, tone, at, gain)
    mix(out, servo(0.6, 96), 0.1, 0.5)
    mix(out, click(0.04, 1800), 1.5, 0.35)
    return enveloped(out, 0.02, 0.5)


def pluck(freq: float, duration: float, decay: float = 3.2, gain: float = 0.2) -> list[float]:
    total = int(duration * RATE)
    out = [0.0] * total
    for index in range(total):
        t = index / RATE
        attack = min(1.0, t / 0.012)
        env = attack * math.exp(-t * decay)
        sample = (
            math.sin(2 * math.pi * freq * t) * 1.0
            + math.sin(2 * math.pi * freq * 2.001 * t) * 0.28
            + math.sin(2 * math.pi * freq * 3.003 * t) * 0.12
            + math.sin(2 * math.pi * freq * 4.007 * t) * 0.05
        )
        out[index] = sample * env * gain
    return out


def pad(frequencies: list[float], duration: float, gain: float = 0.12) -> list[float]:
    total = int(duration * RATE)
    out = [0.0] * total
    for freq in frequencies:
        for detune, phase_shift in [(-0.35, 0.0), (0.0, 1.7), (0.35, 3.1)]:
            phase = phase_shift
            for index in range(total):
                t = index / RATE
                lfo = 1.0 + math.sin(2 * math.pi * 0.13 * t + phase_shift) * 0.003
                phase += 2 * math.pi * (freq + detune) * lfo / RATE
                out[index] += math.sin(phase) * gain / 3.0
    # Ataque y caída suaves dentro del compás.
    return enveloped(out, 0.7, 0.9)


def ambient_loop() -> list[float]:
    """Loop intimista de 32 s, en La menor, con piano, pads, viento y drone."""
    rate = 22050
    bar = 4.0
    bars = 8
    duration = bar * bars
    total = int(duration * rate)
    left = [0.0] * total
    right = [0.0] * total

    chords = [
        [220.0, 261.63, 329.63],   # Am
        [174.61, 220.0, 261.63],   # F
        [261.63, 329.63, 392.0],   # C
        [196.0, 246.94, 293.66],   # G
        [220.0, 261.63, 329.63],   # Am
        [174.61, 220.0, 261.63],   # F
        [261.63, 329.63, 392.0],   # C
        [196.0, 246.94, 293.66],   # G
    ]
    melody = [
        (659.25, 0.0, 1.4), (783.99, 1.4, 1.0), (659.25, 2.4, 1.3),
        (523.25, 4.0, 1.8), (440.0, 5.8, 1.2), (523.25, 7.0, 0.9),
        (659.25, 8.0, 1.4), (880.0, 9.4, 0.9), (783.99, 10.3, 1.7),
        (587.33, 12.0, 1.6), (493.88, 13.6, 1.2), (392.0, 14.8, 1.2),
        (523.25, 16.0, 1.8), (659.25, 17.8, 1.0), (783.99, 18.8, 1.4),
        (698.46, 20.0, 2.0), (523.25, 22.0, 1.4),
        (659.25, 24.0, 1.4), (587.33, 25.4, 1.0), (523.25, 26.4, 1.8),
        (392.0, 28.0, 2.2), (440.0, 30.2, 1.6),
    ]

    # Piano con paneo suave.
    for freq, at, length in melody:
        note = pluck(freq, length + 0.8, 1.9, 0.22)
        mix(left, note, at, 0.82, rate)
        mix(right, note, at + 0.012, 0.72, rate)

    # Pads por compás.
    for index, chord in enumerate(chords):
        voices = [freq / 2 for freq in chord]
        note = pad(voices, bar + 0.6, 0.14)
        mix(left, note, index * bar, 0.58, rate)
        mix(right, note, index * bar + 0.02, 0.5, rate)

    # Drone de La, continuo (cierra exacto en 32 s).
    drone = []
    for sample_index in range(total):
        t = sample_index / rate
        drone.append(
            math.sin(2 * math.pi * 55.0 * t) * 0.055
            + math.sin(2 * math.pi * 110.0 * t) * 0.026
            + math.sin(2 * math.pi * 165.0 * t + 0.7) * 0.009
        )
    mix(left, drone, 0.0, 0.9, rate)
    mix(right, drone, 0.0, 0.9, rate)

    # Viento lejano con Vaivén lento; se desvanece en los bordes del loop.
    random.seed(4360)
    wind = highpass([(random.random() * 2 - 1) for _ in range(total)], 420, rate)
    wind = lowpass(wind, 2400, rate)
    fade = int(0.8 * rate)
    for index in range(total):
        t = index / rate
        env = 1.0
        if index < fade:
            env = index / fade
        elif index > total - fade:
            env = (total - index) / fade
        lfo = 0.55 + 0.45 * math.sin(2 * math.pi * 0.043 * t + 1.2)
        wind[index] *= env * lfo * 0.045
    mix(left, wind, 0.0, 1.0, rate)
    mix(right, wind, 0.0, 0.9, rate)

    # Campanitas dispersas.
    bells = [(1318.5, 6.5), (1568.0, 11.8), (1046.5, 21.2), (1318.5, 27.4), (1760.0, 30.4)]
    for freq, at in bells:
        bell = pluck(freq, 2.4, 1.6, 0.055)
        mix(left, bell, at, 0.7, rate)
        mix(right, bell, at + 0.02, 0.6, rate)

    # Reverb circular simple: realimentación de delays dentro del loop.
    def reverb(channel: list[float], taps: list[tuple[float, float]]) -> list[float]:
        out = channel[:]
        for delay_s, gain in taps:
            delay = int(delay_s * rate)
            for index in range(total):
                out[index] += out[(index - delay) % total] * gain
        return out

    left = reverb(left, [(0.073, 0.28), (0.137, 0.19), (0.211, 0.12)])
    right = reverb(right, [(0.081, 0.28), (0.149, 0.19), (0.223, 0.12)])

    # Limpieza final.
    left = [clamp(sample * 0.75, -0.95, 0.95) for sample in left]
    right = [clamp(sample * 0.75, -0.95, 0.95) for sample in right]
    return left, right


def main() -> None:
    random.seed(2008)
    OUT.mkdir(parents=True, exist_ok=True)

    # Saludos y expresiones.
    happy = silence(1.05)
    mix(happy, robot_voice(430, 660, 0.34, wobble=0.012), 0.0, 0.9)
    mix(happy, robot_voice(560, 880, 0.4, wobble=0.01), 0.36, 0.85)
    write_wav("expression-happy.wav", happy)

    curious = silence(0.72)
    mix(curious, robot_voice(360, 610, 0.55, wobble=0.018), 0.0, 0.95)
    write_wav("expression-curious.wav", curious)

    sad = silence(0.95)
    mix(sad, robot_voice(440, 250, 0.8, wobble=0.014), 0.0, 0.9)
    write_wav("expression-sad.wav", sad)

    alert = silence(0.6)
    for at in (0.0, 0.22):
        beep = robot_voice(980, 980, 0.12, harmonics=(1.0, 0.3, 0.1), wobble=0.0)
        mix(alert, beep, at, 0.8)
    write_wav("expression-alert.wav", alert)

    write_wav("servo.wav", servo(0.9))
    write_wav("tread-loop.wav", tread_loop(2.4))
    write_wav("charge.wav", charge())
    write_wav("boot.wav", boot())

    left, right = ambient_loop()
    write_wav_stereo("ambient-loop.wav", left, right)

    print("\nListo. Archivos en", OUT)


if __name__ == "__main__":
    main()
