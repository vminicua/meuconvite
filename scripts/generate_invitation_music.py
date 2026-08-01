"""Generate the original, royalty-free ambient loop bundled with MeuConvite."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


RATE = 22050
DURATION = 16.0
NOTES = [261.63, 329.63, 392.00, 523.25, 440.00, 349.23, 392.00, 329.63]


def envelope(position: float, length: float = 1.8) -> float:
    attack = min(position / 0.12, 1.0)
    release = max(0.0, min((length - position) / 0.75, 1.0))
    return attack * release


def sample_at(t: float) -> float:
    value = 0.0
    for index, frequency in enumerate(NOTES):
        start = index * 2.0
        position = t - start
        if 0 <= position < 1.8:
            amp = envelope(position)
            value += amp * (
                math.sin(2 * math.pi * frequency * position)
                + 0.30 * math.sin(2 * math.pi * frequency * 2 * position)
                + 0.12 * math.sin(2 * math.pi * frequency * 3 * position)
            )
    bass = 0.12 * math.sin(2 * math.pi * 130.81 * t) * (0.75 + 0.25 * math.sin(math.pi * t / 4))
    return max(-1.0, min(1.0, value * 0.16 + bass))


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "static" / "audio" / "meuconvite-theme.wav"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        frames = bytearray()
        for number in range(int(RATE * DURATION)):
            frames.extend(struct.pack("<h", int(sample_at(number / RATE) * 32767)))
        output.writeframes(frames)
    print(destination)


if __name__ == "__main__":
    main()
