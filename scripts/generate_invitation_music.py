"""Generate an original, royalty-free joyful wedding waltz for MeuConvite."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


RATE = 22050
BPM = 116
BEAT = 60 / BPM
BAR = BEAT * 3

# Oito compassos em Dó maior: luminoso, leve e preparado para repetir.
CHORDS = [
    (60, 64, 67),  # C
    (55, 59, 62),  # G
    (57, 60, 64),  # Am
    (53, 57, 60),  # F
    (60, 64, 67),  # C
    (53, 57, 60),  # F
    (55, 59, 62),  # G
    (60, 64, 67),  # C
]
MELODY = [
    (76, 79, 81, 79, 76, 72),
    (74, 79, 83, 81, 79, 74),
    (76, 81, 84, 81, 79, 76),
    (72, 77, 81, 79, 77, 72),
    (76, 79, 84, 83, 79, 76),
    (77, 81, 84, 81, 79, 77),
    (74, 79, 83, 81, 79, 74),
    (76, 79, 84, 79, 76, 72),
]
DURATION = len(CHORDS) * BAR


def frequency(midi_note: int) -> float:
    return 440.0 * 2 ** ((midi_note - 69) / 12)


def piano(note: int, position: float, decay: float) -> float:
    """Ataque macio com harmónicos curtos, semelhante a piano leve."""
    if position < 0:
        return 0.0
    freq = frequency(note)
    attack = min(position / 0.018, 1.0)
    env = attack * math.exp(-position * decay)
    phase = 2 * math.pi * freq * position
    return env * (
        math.sin(phase)
        + 0.32 * math.sin(phase * 2)
        + 0.12 * math.sin(phase * 3)
    )


def sample_at(t: float) -> float:
    bar_index = min(int(t / BAR), len(CHORDS) - 1)
    bar_position = t - bar_index * BAR
    chord = CHORDS[bar_index]

    # Valsa: baixo no primeiro tempo, acorde ascendente no segundo e terceiro.
    beat_index = min(int(bar_position / BEAT), 2)
    beat_position = bar_position - beat_index * BEAT
    accompaniment_note = chord[beat_index] - (12 if beat_index == 0 else 0)
    accompaniment = piano(accompaniment_note, beat_position, 3.7) * (0.32 if beat_index == 0 else 0.24)

    # Melodia brilhante em colcheias, sem a lentidão da faixa anterior.
    half_beat = BEAT / 2
    melody_index = min(int(bar_position / half_beat), 5)
    melody_position = bar_position - melody_index * half_beat
    melody = piano(MELODY[bar_index][melody_index], melody_position, 5.0) * 0.22

    # Fundo muito subtil para unir os compassos, com entrada e saída suaves.
    pad_env = min(bar_position / 0.12, 1.0) * min((BAR - bar_position) / 0.16, 1.0)
    pad = sum(math.sin(2 * math.pi * frequency(note - 12) * bar_position) for note in chord)
    pad *= 0.018 * max(0.0, pad_env)

    value = accompaniment + melody + pad
    return max(-0.92, min(0.92, value))


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
