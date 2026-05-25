from __future__ import annotations

import array
import math
import struct
from pathlib import Path

import pygame

from game.platform_util import ensure_pygame_init, is_web

ROOT = Path(__file__).resolve().parent.parent
SOUND_DIR = ROOT / "assets" / "sounds"
SOUND_EXT = ".ogg" if is_web() else ".wav"

_TONE_SPECS: dict[str, tuple[float, float]] = {
    "build": (440, 0.08),
    "shoot": (880, 0.04),
    "hit": (220, 0.06),
    "kill": (660, 0.1),
    "upgrade": (523, 0.15),
    "hurt": (150, 0.12),
    "win": (784, 0.25),
    "lose": (196, 0.3),
    "click": (600, 0.05),
    "coin": (1320, 0.09),
}


def _write_tone(path: Path, freq: float, duration: float, volume: float = 0.35) -> None:
    import wave

    rate = 22050
    n = int(rate * duration)
    frames = bytearray()
    for i in range(n):
        t = i / rate
        env = min(1.0, t * 20) * max(0.0, 1.0 - (t / duration) * 1.2)
        sample = int(volume * 32767 * env * math.sin(2 * math.pi * freq * t))
        sample = max(-32767, min(32767, sample))
        frames += struct.pack("<h", sample)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def _procedural_sound(freq: float, duration: float, volume: float = 0.35) -> pygame.mixer.Sound:
    rate = 22050
    n = max(1, int(rate * duration))
    buf = array.array("h", [0] * n)
    for i in range(n):
        t = i / rate
        env = min(1.0, t * 20) * max(0.0, 1.0 - (t / duration) * 1.2)
        sample = int(volume * 32767 * env * math.sin(2 * math.pi * freq * t))
        buf[i] = max(-32767, min(32767, sample))
    return pygame.mixer.Sound(buffer=bytes(buf))


def ensure_sounds() -> None:
    if is_web():
        return
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    for name, (freq, dur) in _TONE_SPECS.items():
        p = SOUND_DIR / f"{name}.wav"
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

    def _load_sound_files(self) -> None:
        if SOUND_DIR.is_dir():
            for path in SOUND_DIR.glob(f"*{SOUND_EXT}"):
                try:
                    self.sounds[path.stem] = pygame.mixer.Sound(str(path))
                except Exception:
                    continue

    def _load_procedural_fallback(self) -> None:
        for name, spec in _TONE_SPECS.items():
            if name not in self.sounds:
                try:
                    self.sounds[name] = _procedural_sound(*spec)
                except Exception:
                    continue

    def init(self) -> None:
        try:
            ensure_pygame_init()
            mixer_get_init = getattr(pygame.mixer, "get_init", None)
            if not (callable(mixer_get_init) and mixer_get_init()):
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            if not is_web():
                ensure_sounds()
            self._load_sound_files()
            self._load_procedural_fallback()
            self._ready = bool(self.sounds)
        except Exception:
            self._ready = False

    def ensure_ready(self) -> None:
        """网页需在用户点击后再次尝试初始化 mixer。"""
        if self._ready:
            return
        self.init()

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        self.ensure_ready()
        if not self._ready:
            return
        s = self.sounds.get(name)
        if s:
            try:
                s.play()
            except Exception:
                pass
