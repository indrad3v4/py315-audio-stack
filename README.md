# py315-audio-stack

**What actually installs on Python 3.15 — and what we build ourselves.**

Python 3.15 ships a real incentive to migrate: PEP 810 lazy imports remove the
startup tax of heavy module-level imports, and free-threaded builds keep
maturing. The blocker is never the interpreter — it is the **audio/ML C-extension
stack**, where most maintainers publish wheels several releases behind.

This repo is the honest, reproducible answer to one question:

> I have Python 3.15. Which of my dependencies install as wheels, which do I have
> to build, and which are blocked upstream?

## Probe first (stdlib only)

```bash
python3 py315_probe.py            # probes the interpreter running it
python3 py315_probe.py --cp 315   # probes cp315 specifically
python3 py315_probe.py --json results/matrix.json
```

It reads live PyPI metadata and classifies every package into one of six
verdicts: `wheel` · `wheel+pure` · `py3-wheel` · `pure` · `no-wheel-for-you` ·
`sdist-only`. No third-party imports, no cache files, nothing to configure.

## Verified matrix — 2026-10-12, live PyPI + live CPython 3.15.0

| Package | Latest | Verdict on cp315 |
|---|---|---|
| numpy | 2.5.4 | ✅ cp315 wheel |
| scipy | 1.18.1 | ✅ cp315 wheel |
| numba | 0.68.0 | ✅ cp315 wheel |
| opensmile | 2.6.0 | ✅ py3 platform wheel — **builds nothing** |
| librosa | 1.0.0 | ✅ pure-python |
| soundfile | 0.14.0 | ✅ pure-python |
| noisereduce | 3.0.3 | ✅ pure-python |
| fal-client | 1.0.3 | ✅ pure-python |
| boto3 | 1.43.112 | ✅ pure-python |
| faster-whisper | 1.2.1 | ✅ pure-python (but needs ctranslate2 below) |
| av | 19.0.1 | ⚠️ wheels only for cp312, cp314 |
| praat-parselmouth | 0.4.7 | ⚠️ wheels only up to cp314 |
| pymupdf | 1.28.2 | ⚠️ wheels only for cp310/313/314 |
| ctranslate2 | 4.8.2 | ⚠️ wheels only up to cp314 |
| onnxruntime | 1.31.0 | ⛔ upstream work |
| torch | 2.14.1 | ⛔ upstream work |
| torchaudio | 2.11.0 | ⛔ upstream work |
| webrtcvad | 2.0.10 | 🔨 sdist only — needs a toolchain |

**10 of 18 install without touching a compiler.** That includes the whole
feature-extraction path people actually migrate for: `opensmile` eGeMAPS
replaces Praat-based prosody features with no build step at all.

Two different problems hide behind "no cp315 wheel", and pretending they are the
same is how migrations fail:

1. **Buildable now.** The package's own source compiles against 3.15; it just
   needs a toolchain and a recipe — hours of compute, not months of engineering.
2. **Blocked upstream.** torch / onnxruntime / torchaudio need maintainers to add
   the interpreter to their own build matrix. No amount of CI on our side creates
   a supported build; we document the gap instead of shipping a fake.

### Verified live on a real 3.15 interpreter, not just from metadata

On CPython 3.15.0, in a clean venv:

```
OK   numpy        2.5.4       348.2 ms
OK   scipy        1.18.1       97.6 ms
OK   numba        0.68.0      560.9 ms
OK   soundfile    0.14.0       28.7 ms
OK   librosa      1.0.0         2.6 ms
OK   noisereduce  3.0.3      1639.7 ms
OK   opensmile    2.6.0      2142.0 ms   (FeatureSet.eGeMAPSv02 available)
OK   boto3        1.43.112   3979.9 ms
```

## Building the wheels

The box that produced this matrix has **no compiler at all** (`gcc`, `make`,
`cmake`, `swig`, `rustc` — absent), which is the normal state of a slim runtime
container. That is exactly why the build lives in CI: `.github/workflows/wheels.yml`
uses [cibuildwheel](https://cibuildwheel.pypa.io) on GitHub's runners, where the
toolchain and the manylinux images are a given.

- `push` / `pull_request` → build wheels for `cp315-manylinux_x86_64`, artifacts
  uploaded per package.
- tag `v*` → the same wheels are attached to a GitHub Release, so anyone can:

```bash
pip install --find-links https://github.com/<owner>/py315-audio-stack/releases/latest/download \
    praat-parselmouth
```

Per-package system dependencies (SWIG, FFmpeg headers, CMake, Rust) are declared
in the workflow, not hidden in a wiki.

## Substitutions when a build is not worth it

| Blocked | Substitute | Why |
|---|---|---|
| `praat-parselmouth` (Praat pitch/jitter/shimmer) | `opensmile` eGeMAPS (88 features) | installs as-is on 3.15, verified; comparable prosody + voice-quality set |
| `torch` for embeddings | any hosted embedding API | removes the largest wheel in the stack, and its CUDA tail |
| `ctranslate2` / `faster-whisper` | hosted Whisper (`whisper-large-v3`) | measured cheaper than local for bursty transcription workloads |

## Lazy imports are the reason to migrate early

Measured on a live CPython 3.15.0 with a production archiver script, `boto3`
imported only inside a function that most runs never reach:

| Variant | min | median |
|---|---|---|
| eager `import boto3` | 137.8 ms | 144.1 ms |
| `__lazy_modules__ = ["boto3"]` | 22.7 ms | 25.2 ms |

**−115 ms (−83%) on every run that does not touch S3.** The same line is inert on
3.12 (a plain module attribute), so it can be committed today and activates by
itself once the interpreter moves. The mechanism was also verified directly: after
`import heavy` under `__lazy_modules__`, the module is *not* in `sys.modules`
until first use.

## Layout

```
py315_probe.py               live PyPI verdicts, stdlib only
results/                     machine-readable probe output (dated)
recipes/source-builds.md     per-package build notes, order of work, substitutions
.github/workflows/wheels.yml cibuildwheel → artifacts → release assets
```

## Honest limits

- Wheel availability is a snapshot from live PyPI; re-run the probe before
  trusting this table.
- A wheel in a GitHub Release is not a supported upstream build. Prefer official
  wheels when they appear, and delete ours.
- Verification here means: the probe reads real PyPI data, the import timings come
  from real runs on CPython 3.15.0, and blocked packages are named as blocked.
  Nothing in this README is projected, extrapolated, or copied from another
  project's claims.

## License

MIT — see `LICENSE`.
