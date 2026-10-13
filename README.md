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

## Published wheels — release [v0.3.0](https://github.com/indrad3v4/py315-audio-stack/releases/tag/v0.3.0)

All four packages now build, publish, and — the part that matters — install into
a live CPython 3.15.0 and import. The release is created by the same script that
gates it: the tag exists only if all four say `IMPORT OK`.

| package | wheel | size | check on live 3.15.0 |
|---|---|---|---|
| `av` | `av-19.0.1-cp315-cp315-manylinux_2_34_x86_64.whl` | 23.5 MB | `import av` → 19.0.1, links libavcodec 63.1.102 (FFmpeg 9) |
| `praat-parselmouth` | `praat_parselmouth-0.4.7-cp315-cp315-manylinux…whl` | 10.9 MB | `import parselmouth` → 0.4.7 |
| `webrtcvad` | `webrtcvad-2.0.10-cp315-cp315-manylinux…whl` | 86 KB | import works with `setuptools<81` installed |
| `pymupdf` | `pymupdf-1.28.2-cp315-abi3-manylinux…whl` | 25.7 MB | `import pymupdf` → 1.28.2 (abi3 wheel) |

`webrtcvad` imports `pkg_resources` at import time and never declares it, so it
needs `setuptools<81` in the environment: setuptools 81+ no longer ships
`pkg_resources` at all. That is upstream's wart, not the wheel's.

`pip install <wheel-url>` from the release is the intended path; the wheels are
`cp315-cp315`, i.e. version-specific, because upstream ships none.

## The four walls, and what each one actually was

Every failure below looked like a package problem and was not one:

| symptom | real cause | fix |
|---|---|---|
| `av`: `AV_HWDEVICE_TYPE_AMF` / `…_OHCODEC` undeclared | FFmpeg too old — 4.2 in Alma 8, 5.1 in RPM Fusion el9, and PyAV's README says its release supports **FFmpeg 9.x** | build FFmpeg 9.0.2 from source in the container |
| `pymupdf`: `libclang.so: cannot open shared object file` | `pip install libclang` installs the **`clang`** package (no `libclang` module), and the metadata build runs in pip's isolated env where `LIBCLANG_PATH` never arrives | put the `.so` where `LD_LIBRARY_PATH` already points; smoke-test it with no `LIBCLANG_*` set |
| `pymupdf`: `PyString_FromString` undeclared | not in the wrapper sources at all. MuPDF's **generator** emits it: `scripts/wrap/swig.py:743` writes `PyString_FromString("format_tb")` into every wrapper it produces, so patching `.i` files is a no-op — and the one occurrence multiplies across the generated `.cpp` | patch the generator as well, and gate on zero mentions |
| `pymupdf`: patched tree ignored, byte-identical errors | `PYMUPDF_SETUP_MUPDF_TGZ` is read by `get_mupdf_tgz()`, which exists to build sdist *archives*. The build path is `get_mupdf()`, which reads `PYMUPDF_SETUP_MUPDF_BUILD` (a **directory**) and otherwise downloads a pristine tree itself, silently ignoring the file it was handed | pass a directory through the build knob, not a tarball through the archiving knob |
| CI died the instant the patch succeeded | `set -e` plus `grep` with no matches: grep exits 1 when it finds nothing, so the gate that proves "zero mentions remain" killed the step exactly when it became true | `(grep … \|\| true) \| wc -l` |
| container: `cibuildwheel: Command ['which', 'python'] failed` | the container env string was appended with `echo` in double quotes, so `$HOME`/`$PATH` expanded **on the runner** and the host PATH replaced the image's | write the container-side string single-quoted, and print it to the log |
| `praat-parselmouth`: `CMake Error: CMAKE_MAKE_PROGRAM` | the pip `ninja` wheel landed off-PATH and the shell-quoted copy was mangled by cibuildwheel's `sh -c` wrapper | `yum install -y epel-release ninja-build` — no quoting, no PATH games |

Two rules earned the hard way, both worth more than the wheels:

1. **Environment variables are not a transport.** Rust, FFmpeg, Ninja and
   libclang all failed at some point because a variable was set in the wrong
   layer (host step vs container, `CIBW_ENVIRONMENT` vs job level). What travels
   reliably is a path in the filesystem that the failing step can already see.
2. **A gate must survive its own success.** A check whose success condition is
   "nothing found" fails under `set -e` the moment it works, and a check that
   writes its verdict into the wrong layer reports a green that means nothing.
3. **A green job that never loads the artifact proves nothing.** Every fix here
   ends in a check: `ctypes.CDLL('libclang.so')` with the variables unset,
   `pkg-config --modversion libavcodec`, `grep -c PyString_` equals zero,
   `import av` on a real 3.15 interpreter.

## Build results — runs 5 and 6 (workflow v5 / v6)

Runs [`38322566111`](https://github.com/indrad3v4/py315-audio-stack/actions/runs/38322566111) and
[`38322858000`](https://github.com/indrad3v4/py315-audio-stack/actions/runs/38322858000).

| Package | Outcome | Root cause | Fix in workflow v7 |
|---|---|---|---|
| `webrtcvad` | ✅ SUCCESS (fifth run in a row) | — | — |
| `av` | FFmpeg devel installed; compile failed on two enums | `AV_HWDEVICE_TYPE_AMF` (v4, FFmpeg 4.2), `AV_HWDEVICE_TYPE_OHCODEC` (v5, FFmpeg 5.1) — both are **FFmpeg 7.1+**, and no RPM Fusion repo for el8/el9 ships 7.x | build FFmpeg 7.1 from source in the container, install to `/usr` with pkg-config metadata |
| `pymupdf` | MuPDF itself built (3m26s, exit 0), then the metadata step died | `OSError: libclang.so: cannot open shared object file` — `clang/cindex.py` calls `dlopen("libclang.so")` with no path, and `LIBCLANG_PATH` does not reach pip's isolated build env | copy `libclang.so` to `/usr/local/lib` + `ldconfig`, then **prove** it loads via `env -u LIBCLANG_PATH … CDLL('libclang.so')` |
| `praat-parselmouth` | same Ninja error as v3 | the v4.1 fix was shell-quoted and cibuildwheel wraps `CIBW_BEFORE_ALL_*` in its own `sh -c`, so `cp` and `which` both failed silently | EPEL's `ninja-build`, no quoting, `ninja --version` as the check |

Two lessons worth more than the wheels:

1. **`CIBW_BEFORE_ALL_*` runs through a shell wrapper.** Nested quotes around `$(...)`
   get mangled — silently, because the command ends with `|| true`. Anything
   quote-shaped belongs in a package manager call instead.
2. **Environment variables are not a transport mechanism.** Rust, FFmpeg, Ninja and
   libclang all failed at least once precisely because a variable set in one place
   was absent where the work actually ran: a different step, a different machine
   (host vs container), or pip's isolated build env. Paths written into the
   filesystem — `/usr/local/lib`, `/usr`, `$GITHUB_PATH` — survived; variables did not.

`pymupdf` is also the clearest case that "the build failed" and "the build failed to
*tell you* it built" are different problems: MuPDF compiled perfectly, then the step
that reports it fell over.

## Build results — run 4 (workflow v4 / v4.1)

Runs [`38320291548`](https://github.com/indrad3v4/py315-audio-stack/actions/runs/38320291548) and
[`38320373729`](https://github.com/indrad3v4/py315-audio-stack/actions/runs/38320373729).

| Package | Outcome | Root cause | Fix in workflow v5 |
|---|---|---|---|
| `webrtcvad` | ✅ SUCCESS (third run in a row) | — | — |
| `av` | FFmpeg devel now installs; compile failed on real API gaps | `av_channel_layout_describe` undeclared, `AVCodecParameters` has no member `ch_layout` — AlmaLinux 8 ships FFmpeg **4.2**, PyAV needs much newer | build in `manylinux_2_34` (Alma 9) with the **el9** RPM Fusion repo |
| `pymupdf` | Rust ✅ and libclang ✅ installed, then the job died | `syntax error near unexpected token 'os.path.dirname'` — a nested-quoted shell expression cannot travel through a matrix variable into `eval` | dedicated env step (no `eval`), `LIBCLANG_PATH` verified before use |
| `ctranslate2` | same missing headers as v3, **with submodules present** | submodules were never the cause: `python/pyproject.toml` is plain `setuptools` (`build-backend = setuptools.build_meta`) and `setup.py` compiles `cpp/*.cc` while expecting the C++ core and its generated headers to already exist | **removed from the matrix** — a dedicated build: CMake over the whole repo first, then the bindings |
| `praat-parselmouth` | compiling at the time of writing | — | Ninja now on `PATH` (v4.1) |

`ctranslate2` is the honest boundary of this pipeline: the pattern "fetch sdist →
cibuildwheel → test" fits projects whose build frontend is self-contained. A
project that ships wheels only, and whose Python build expects a pre-built C++
core, needs a written recipe instead. That recipe is work, not a matrix line —
and pretending otherwise would have produced a green badge on a broken wheel.

## Build results — run 3 (workflow v3)

Run [`38317992784`](https://github.com/indrad3v4/py315-audio-stack/actions/runs/38317992784).

| Package | Outcome | Root cause | Fix in workflow v4 |
|---|---|---|---|
| `webrtcvad` | ✅ **SUCCESS** again | stable | — |
| `praat-parselmouth` | compiling (longest target: the whole Praat C++ core) | — | pending |
| `av` | failed in before-all | `yum install -y ffmpeg-devel` → *"Unable to find a match"*: EPEL does not carry FFmpeg; the RPM Fusion free repo must be added explicitly, and manylinux_2_28 is AlmaLinux **8** | add `rpmfusion-free-release-8.noarch.rpm`, then `ffmpeg-devel` |
| `pymupdf` | failed in host metadata generation | `OSError: libclang.so: cannot open shared object file` — `mupdfwrap.py` drives clang's Python bindings before cibuildwheel runs | `pip install libclang` host-side + export `LIBCLANG_PATH` |
| `ctranslate2` | reached the compiler, headers missing | `fatal error: ctranslate2/encoder.h: No such file or directory` — a `--depth 1` clone carries no submodules, so CMake has no spdlog/cpu_features to generate the headers from | clone with `--recurse-submodules --shallow-submodules` |

Second lesson of the same shape: **the host step and the build container are two
different machines.** Rust (`pymupdf`), FFmpeg headers (`av`) and clang bindings
(`pymupdf`) each had to be installed twice, and `export` inside one CI step does
not reach the next — environment now travels through `$GITHUB_ENV`/`$GITHUB_PATH`.

## Build results — run 2 (workflow v2)

Run [`38315956261`](https://github.com/indrad3v4/py315-audio-stack/actions/runs/38315956261).
**One wheel published: `webrtcvad`** — built, imported, uploaded
(`wheel-webrtcvad-cp315`, 85 KB). The other four moved forward and failed one
layer deeper, each for a reason visible only in the log:

| Package | Outcome | Root cause | Fix in workflow v3 |
|---|---|---|---|
| `webrtcvad` | ✅ **SUCCESS** — wheel artifact uploaded | — | done |
| `praat-parselmouth` | compiled, then failed | CMake aborted: *"unable to find a build program corresponding to Ninja"* — Ninja is not in the manylinux base image | `pip install swig ninja` in before-all |
| `pymupdf` | failed in *Fetch source from PyPI* | the sdist's build backend invokes `cargo` during **metadata generation on the host** — Rust was only installed inside the build container | install rustup host-side too |
| `av` | failed before compiling | `yum install -y ffmpeg-devel pkgconfig` → non-zero: `pkgconfig` is not a package name on the AlmaLinux-based manylinux image (it is `pkgconf-pkg-config`), and `ffmpeg-devel` needs RPM Fusion | `epel-release` + `pkgconf-pkg-config`, then `ffmpeg-devel` |
| `ctranslate2` | source fetched, build frontend not found | *"Could not find any of {setup.py, setup.cfg, pyproject.toml} at root of package"* — CTranslate2's Python project lives in `python/`, not at the repo root | build `src/ctranslate2/python/` |

Progression worth noting: `webrtcvad` went from *"import fails, no wheel"* to a
published artifact by installing one package into the test environment. That is
what "adapting to 3.15" actually costs when the library is alive.

## Build results — run 1 (workflow v1)

Run [`38315515682`](https://github.com/indrad3v4/py315-audio-stack/actions) on
`main`. **Zero wheels published yet** — and every failure is now diagnosed from
its own log, not guessed. Five jobs, five different reasons, one shared lesson:
"no cp315 wheel" hides a *specific* defect that a probe cannot see.

| Package | Outcome | Root cause (from the job log) | Fix in workflow v2 |
|---|---|---|---|
| `webrtcvad` | **wheel BUILT in 3.7 s**, then the job failed | `webrtcvad.py` line 1 is `import pkg_resources` — removed from setuptools ≥ 81, so the extension compiled but the module could not import | install `setuptools<81` in the test environment (`CIBW_BEFORE_TEST_LINUX`) |
| `ctranslate2` | failed before any compile | `pip download --no-binary :all: ctranslate2` → *"no matching distribution"*: PyPI lists **35 files, 0 sdists** — there is no source tarball to build | fetch from the git tag `v4.8.2` instead |
| `av` | metadata generation failed | the *host* step that generates build metadata needs FFmpeg headers (`pkg-config`, `libav*-dev`); they are not on a bare runner, and `CIBW_BEFORE_ALL_LINUX` only affects the build container | install FFmpeg dev packages host-side **and** `ffmpeg-devel` in the container |
| `pymupdf` | `metadata-generation-failed` | the build needs the Rust toolchain, and `export PATH=$HOME/.cargo/bin` inside *before-all* does not persist across cibuildwheel's shells | keep the install in before-all, expose the path via `CIBW_ENVIRONMENT_LINUX` |
| `praat-parselmouth` | still running at the time of writing | — | unchanged |

The most useful result is `webrtcvad`: **its cp315 wheel exists and works; the
library itself is what breaks.** `pkg_resources` was removed from setuptools in
2025, so the 2018-era code cannot import on a modern environment regardless of
Python version. A cp315 wheel is not the fix — the fix is dropping the
`pkg_resources` import (or using a maintained fork).

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
