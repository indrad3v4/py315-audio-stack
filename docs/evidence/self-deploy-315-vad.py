#!/opt/hermes/venv/bin/python3
"""Прагон: сапраўдная гаворка + кантрольная цішыня праз webrtcvad на 3.15.
Запуск: /root/.hermes/py315-flight/bin/python /root/.hermes/py315/vad_self_proof.py
"""
import array
import glob
import sys

import av
import webrtcvad

sys.stderr.write(f"Python {sys.version.split()[0]} | webrtcvad {webrtcvad.__version__}\n")


def decode16k(path):
    """Любы файл -> 16 кГц мона s16le (патрабаванне webrtcvad)."""
    with av.open(path) as c:
        stream = c.streams.audio[0]
        res = av.AudioResampler(format="s16", layout="mono", rate=16000)
        out = bytearray()
        for frame in c.decode(stream):
            for rf in res.resample(frame):
                out += bytes(rf.planes[0])
        for rf in res.resample(None):
            out += bytes(rf.planes[0])
        return bytes(out)


def speech_frames(pcm, ms):
    vad = webrtcvad.Vad(2)          # агрэсіўны рэжым — як у практыцы STT
    step = 16000 * ms // 1000 * 2   # байт на кадр
    total = len(pcm) // step
    hits = sum(
        vad.is_speech(pcm[i * step:(i + 1) * step], 16000)
        for i in range(total)
    )
    return hits, total


print(f"{'файл':<16}{'10мс':>14}{'20мс':>14}{'30мс':>14}")
rows = {}
for p in sorted(glob.glob("/root/.hermes/hackyeah/wt-ai/audio/*.mp3")):
    pcm = decode16k(p)
    if len(pcm) < 3200:
        print(f"{p.split('/')[-1]:<16}  занадта кароткі ({len(pcm)} байт)")
        continue
    cells = []
    for ms in (10, 20, 30):
        h, t = speech_frames(pcm, ms)
        cells.append(f"{h}/{t}")
    rows[p] = cells
    print(f"{p.split('/')[-1]:<16}{cells[0]:>14}{cells[1]:>14}{cells[2]:>14}")

# Кантроль: 2 секунды абсалютнай цішыні.
sil = array.array("h", [0] * 32000).tobytes()
cells = [f"{speech_frames(sil, ms)[0]}/{speech_frames(sil, ms)[1]}" for ms in (10, 20, 30)]
print(f"{'ЦІШЫНЯ (контроль)':<16}{cells[0]:>14}{cells[1]:>14}{cells[2]:>14}")

ok = all(int(c[0].split('/')[0]) > 0 for c in rows.values())
print(f"\nVAD_OK: {ok} — гаворка знойдзена ў кожным файле, цішыня дала {speech_frames(sil,20)[0]} кадраў гаворкі")
