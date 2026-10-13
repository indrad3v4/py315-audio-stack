"""Batch 1 / AC4 proof: the patched webrtcvad does real VAD on CPython 3.15.0.

The wrapper was patched with patches/webrtcvad-no-pkg-resources.patch
(pkg_resources -> importlib.metadata) and installed into a fresh 3.15.0 venv.

Signal is generated with **stdlib only** (wave, math, array): a 2.0 s, 16 kHz,
mono, 16-bit PCM WAV whose first second is an amplitude-modulated 440 Hz tone
(carrier amplitude 0.5, 4 Hz envelope) -- a quasi-speech burst -- and whose
second second is digital silence.  Frames of 10, 20 and 30 ms are pushed through
webrtcvad.Vad(2).
"""

import array
import hashlib
import importlib.util
import math
import os
import sys
import wave

RATE = 16000
DURATION_S = 2.0
SPEECH_S = 1.0
WAV = "/tmp/batch1/vad-315-batch1.wav"


def build_pcm():
    """1 s of 4 Hz-AM 440 Hz tone (peak 0.5) followed by 1 s of silence."""
    n_speech = int(RATE * SPEECH_S)
    n_total = int(RATE * DURATION_S)
    a = array.array("h")
    for t in range(n_speech):
        env = 0.5 + 0.5 * math.sin(2 * math.pi * 4.0 * t / RATE)   # 4 Hz modulation
        s = 0.5 * env * math.sin(2 * math.pi * 440.0 * t / RATE)   # 440 Hz, amp 0.5
        a.append(int(max(-1.0, min(1.0, s)) * 32767))
    for _ in range(n_total - n_speech):
        a.append(0)                                                # silent second
    return a


pcm = build_pcm()
with wave.open(WAV, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(pcm.tobytes())

print("interpreter      :", sys.version.replace("\n", " "))
print("pkg_resources    :", importlib.util.find_spec("pkg_resources"))

import webrtcvad  # noqa: E402  (import after the pkg_resources probe)

print("webrtcvad module :", webrtcvad.__file__)
print("webrtcvad version:", webrtcvad.__version__)
print("WAV              :", WAV, os.path.getsize(WAV), "bytes")
print("WAV sha256       :", hashlib.sha256(open(WAV, "rb").read()).hexdigest())
print("signal           : 1.0 s AM 440 Hz tone (amp 0.5, 4 Hz env) + 1.0 s silence"
      " | 16 kHz mono s16 LE")
print()

vad = webrtcvad.Vad(2)  # aggressiveness mode 2
hdr = f"{'frame(ms)':>9} | {'frames_total':>12} | {'speech_1st_s':>12} | {'speech_2nd_s':>12}"
print(hdr)
print("-" * len(hdr))

rows = []
data = pcm.tobytes()
for ms in (10, 20, 30):
    n = RATE * ms // 1000
    size = n * 2
    flags = [vad.is_speech(data[o:o + size], RATE)
             for o in range(0, len(data) - size + 1, size)]
    half = len(flags) // 2
    f1, f2 = sum(flags[:half]), sum(flags[half:])
    print(f"{ms:>9} | {len(flags):>12} | {f1:>12} | {f2:>12}")
    print(f"{'':>9} | 2nd-second flags: {''.join('1' if f else '0' for f in flags[half:])}")
    rows.append((ms, len(flags), f1, f2))

# "almost zero" == at most 150 ms worth of trailing frames after the tone stops
ok1 = all(f1 > 0 for _, _, f1, _ in rows)
ok2 = all(f2 <= int(0.150 / (ms / 1000.0)) for ms, _, _, f2 in rows)
print()
print("check speech_1st_s > 0      :", ok1)
print("check speech_2nd_s ~ 0 (<=150 ms):", ok2)
print("VAD_OK:", ok1 and ok2)
