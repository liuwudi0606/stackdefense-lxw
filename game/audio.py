from __future__ import annotations

import math
import struct
from pathlib import Path

import pygame

from game.platform_util import is_web

ROOT = Path(__file__).resolve().parent.parent
SOUND_DIR = ROOT / "assets" / "sounds"
SOUND_EXT = ".ogg" if is_web() else ".wav"


def _write_tone(path: Path, freq: float, duration: float, volume: float = 0.35) -> None:
    import wave

    rate = 22050
    n = int(rate * duration)
    frames = bytearray()
    for i in range(n):
        t = i / rate
        env = min(1.0, t * 20) * max(0.0, 1.0 - (t / duration) * 1.2)
        sample = int(
            volume * 32767 * env * math.sin(2 * math.pi * freq * t)
        )
        sample = max(-32767, min(32767, sample))
        frames += struct.pack("<h", sample)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def ensure_sounds() -> None:
    if is_web():
        return
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    specs = {
        "build.wav": (440, 0.08),
        "shoot.wav": (880, 0.04),
        "hit.wav": (220, 0.06),
        "kill.wav": (660, 0.1),
        "upgrade.wav": (523, 0.15),
        "hurt.wav": (150, 0.12),
        "win.wav": (784, 0.25),
        "lose.wav": (196, 0.3),
        "click.wav": (600, 0.05),
    }
    for name, (freq, dur) in specs.items():
        p = SOUND_DIR / name
        if not p.is_file():
            _write_tone(p, freq, dur)


def ensure_ogg_sounds() -> None:
    """WAV → OGG for desktop build scripts; web ships prebuilt .ogg in assets."""
    if is_web():
        return
    try:
        import soundfile as sf
    except ImportError:
        return
    ensure_sounds()
    for wav in SOUND_DIR.glob("*.wav"):
        ogg = wav.with_suffix(".ogg")
        if ogg.is_file() and ogg.stat().st_mtime >= wav.stat().st_mtime:
            continue
        data, sr = sf.read(wav)
        sf.write(ogg, data, sr, format="OGG")


class AudioManager:
    def __init__(self) -> None:
        self.enabled = True
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._ready = False

    def init(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            if not is_web():
                ensure_sounds()
            for path in SOUND_DIR.glob(f"*{SOUND_EXT}"):
                self.sounds[path.stem] = pygame.mixer.Sound(str(path))
            self._ready = True
        except Exception:
            self._ready = False

    def play(self, name: str) -> None:
        if not self.enabled or not self._ready:
            return
        s = self.sounds.get(name)
        if s:
            s.play()
