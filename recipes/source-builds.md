# Source builds on cp315 — per package

Why CI and not the local box: the runtime container this matrix was produced on
has **no compiler** (`gcc`, `g++`, `make`, `cmake`, `swig`, `rustc` all absent).
Installing a toolchain inside a running container is possible but ephemeral, and
a 10 GB build tree does not belong on a persistent data volume. cibuildwheel on
GitHub runners gives a disposable toolchain, manylinux images for reproducible
glibc floors, and release assets at the end.

| Package | System deps | Build system | Expected build time | Notes |
|---|---|---|---|---|
| `webrtcvad` | none | setuptools + C | < 1 min | smallest possible target — the extension is one C file |
| `praat-parselmouth` | `swig` | setuptools + SWIG + C++ | 3–6 min | Praat core is large but self-contained |
| `av` | `ffmpeg-devel` | setuptools + Cython | 4–8 min | version must match the FFmpeg headers in the manylinux image |
| `pymupdf` | Rust toolchain | setuptools + Rust + C | 8–15 min | `rustup` inside `CIBW_BEFORE_ALL`; keep the toolchain out of the wheel |
| `ctranslate2` | `cmake` | CMake | 20–40 min | CUDA off by default; CPU-only keeps the wheel portable |

## Which flags matter

- `CIBW_BUILD=cp315-manylinux_x86_64` — one interpreter, one platform, on purpose.
  Adding aarch64/musllinux multiplies the job count and the failure surface before
  the first wheel is proven.
- `CIBW_TEST_COMMAND` — an import of the built extension. A wheel that installs but
  cannot import is not a wheel; the import is the only check that proves the `.so`
  loaded against the target interpreter.
- `CIBW_BEFORE_ALL_LINUX` — where per-package system deps go. Keeping them next to
  the matrix entry (instead of in a shared script) means a build failure names its
  own cause.

## Order of work

1. `webrtcvad` — prove the pipeline end to end with the cheapest possible target.
2. `praat-parselmouth` — first real C++ target; SWIG is the only external tool.
3. `av` + `opensmile` — the pair that needs system libraries, so they exercise
   `CIBW_BEFORE_ALL_LINUX` honestly.
4. `pymupdf`, `ctranslate2` — long builds; keep them last so a red CI run does not
   hide a fast failure behind a 40-minute job.

## What is deliberately not attempted

`torch`, `torchaudio`, `onnxruntime`. These are maintained build farms with their
own CUDA/toolchain matrices. A wheel built here would be unsupported, unreproducible
against their releases, and would silently diverge from upstream the moment they
ship cp315. The honest deliverable is the probe output that names the gap — which
`.github/workflows/wheels.yml` publishes on every run.

## Substitutions instead of builds

When the build is not worth the maintenance, change the dependency:

- **`praat-parselmouth` → `opensmile` eGeMAPS.** 88 interpretable prosody and
  voice-quality features, covering most pitch/jitter/shimmer use cases that pull
  people toward Praat in the first place.
- **`ctranslate2` + `faster-whisper` → hosted Whisper.** For bursty transcription
  workloads, per-minute API pricing beats maintaining a local inference runtime;
  measure before assuming local is cheaper.
- **`torch` for embeddings → any hosted embedding endpoint.** Removes the largest
  wheel in the stack and its CUDA tail.
