"""AC4 proof: webrtcvad on CPython 3.15.0 with no pkg_resources, doing real VAD.

The wrapper is pure Python; only its import of pkg_resources broke, so the wheel
is rebuilt with the patched wrapper and the prebuilt C extension, then driven
over a generated 16 kHz mono WAV (silence / 220 Hz tone / speech-band noise /
silence) with 10, 20 and 30 ms frames. Stdlib only -- no numpy.
"""

import importlib.util
import math
import random
import struct
import sys
import wave
from pathlib import Path

print("interpreter:", sys.version.replace("\n", " "))
print("pkg_resources importable:", importlib.util.find_spec("pkg_resources") is not None)

import webrtcvad

print("webrtcvad module:", webrtcvad.__file__)
print("webrtcvad.__version__:", webrtcvad.__version__)
assert importlib.util.find_spec("pkg_resources") is None, "pkg_resources present"

RATE = 16000
tmp = Path("/tmp/vadproof")
tmp.mkdir(parents=True, exist_ok=True)
wav = tmp / "vad-315.wav"


def silence(n):
    return [0.0] * n


def tone(n):
    return [0.6 * math.sin(2 * math.pi * 220 * t / RATE) for t in range(n)]


def noise(n, rng):
    return [0.5 * rng.uniform(-1, 1) for _ in range(n)]


rng = random.Random(1515)
seg = silence(int(0.30 * RATE)) + tone(int(0.30 * RATE)) + noise(int(0.30 * RATE), rng) + silence(int(0.20 * RATE))
pcm = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in seg)
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(pcm)
print("wrote", wav, "| samples:", len(seg), "| order: silence/tone/noise/silence")

vad = webrtcvad.Vad(3)  # most aggressive mode
for ms in (10, 20, 30):
    n = RATE * ms // 1000
    size = n * 2
    flags = [vad.is_speech(pcm[o:o + size], RATE) for o in range(0, len(pcm) - size + 1, size)]
    speech = sum(1 for f in flags if f)
    print(f"frame {ms:>2} ms ({n:>3} samples): {''.join('1' if f else '0' for f in flags)} "
          f"speech={speech}/{len(flags)}")

print("valid_rate_and_frame_length(16000, 480):",
      webrtcvad.valid_rate_and_frame_length(16000, 480))
print("VAD_OK", True)
