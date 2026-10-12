#!/usr/bin/env python3
"""py315_probe — what actually installs on a given Python version, straight from PyPI.

Answers one question per package: does the current release ship a wheel for my
interpreter, or will pip fall back to building from source (needing a toolchain)?

Usage:
    python3 py315_probe.py                 # probe the interpreter running this file
    python3 py315_probe.py --cp 315        # probe cp315 wheels specifically
    python3 py315_probe.py --json out.json # machine-readable result
    python3 py315_probe.py --packages torch numpy librosa

No third-party dependencies: stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

DEFAULT_PACKAGES = [
    "numpy", "scipy", "numba", "soundfile", "librosa", "noisereduce",
    "opensmile", "praat-parselmouth", "webrtcvad", "av", "pymupdf",
    "faster-whisper", "ctranslate2", "onnxruntime", "torch", "torchaudio",
    "fal-client", "boto3",
]

WHEEL_PY_TAG = re.compile(r"cp3\d+m?t?|py3|pp3\d+")


def fetch(package: str, timeout: int = 25) -> dict:
    url = f"https://pypi.org/pypi/{package}/json"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def classify(package: str, cp: str) -> dict:
    """Return one verdict row for `package` against interpreter tag `cp` (e.g. 'cp315')."""
    try:
        data = fetch(package)
    except urllib.error.HTTPError as exc:
        return {"package": package, "status": "unknown", "note": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001 - probe must never crash on one bad package
        return {"package": package, "status": "unknown", "note": type(exc).__name__}

    version = data["info"]["version"]
    files = data.get("releases", {}).get(version, []) or []
    names = [f["filename"] for f in files]
    wheels = [n for n in names if n.endswith(".whl")]
    sdists = [n for n in names if not n.endswith(".whl")]

    has_cp = any(cp in n for n in wheels)
    pure = any(n.endswith("-none-any.whl") for n in wheels)
    # A `py3-none-manylinux…` wheel is interpreter-agnostic but platform-tagged:
    # it installs on the target version without a build, as long as the platform
    # matches. Conflating it with "no wheel for you" is how migrations panic early.
    py_platform = [n for n in wheels if re.search(r"-py3-none-", n) and not n.endswith("-none-any.whl")]
    tags = sorted({m.group(0) for n in wheels for m in [WHEEL_PY_TAG.search(n)] if m})

    if has_cp and pure:
        status, note = "wheel+pure", f"{cp} wheel and pure-python fallback"
    elif has_cp:
        status, note = "wheel", f"native {cp} wheel"
    elif pure:
        status, note = "pure", "pure-python wheel (version-agnostic)"
    elif py_platform:
        status, note = "py3-wheel", f"py3 platform wheel ({py_platform[0].split('-py3-none-')[1]}) — no build needed"
    elif wheels:
        status, note = "no-wheel-for-you", f"wheels exist but only for {', '.join(tags)}"
    elif sdists:
        status, note = "sdist-only", "source distribution only — needs a toolchain"
    else:
        status, note = "unknown", "no files listed for latest release"

    return {
        "package": package,
        "version": version,
        "status": status,
        "wheel_tags": tags,
        "wheels": len(wheels),
        "sdists": len(sdists),
        "note": note,
    }


STATUS_ORDER = {
    "wheel+pure": 0, "wheel": 1, "py3-wheel": 2, "pure": 3, "no-wheel-for-you": 4,
    "sdist-only": 5, "unknown": 6,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cp", default=f"cp{sys.version_info.major}{sys.version_info.minor}",
                        help="interpreter tag to probe, e.g. cp315 (default: this interpreter)")
    parser.add_argument("--packages", nargs="*", default=DEFAULT_PACKAGES)
    parser.add_argument("--json", metavar="PATH", help="write machine-readable JSON here")
    args = parser.parse_args()

    rows = [classify(p, args.cp) for p in args.packages]

    width = max(len(r["package"]) for r in rows) + 2
    print(f"py315_probe · target={args.cp} · python={sys.version.split()[0]} · PyPI live")
    print(f"{'package':<{width}}{'version':<12}{'verdict':<18}detail")
    for row in sorted(rows, key=lambda r: (STATUS_ORDER.get(r["status"], 9), r["package"])):
        print(f"{row['package']:<{width}}{row['version']:<12}{row['status']:<18}{row['note']}")

    ok = [r for r in rows if r["status"] in ("wheel+pure", "wheel", "pure", "py3-wheel")]
    blocked = [r for r in rows if r["status"] in ("no-wheel-for-you", "sdist-only")]
    print(f"\ninstalls as-is on {args.cp}: {len(ok)}/{len(rows)} · needs a build or a substitute: {len(blocked)}")

    if args.json:
        payload = {"target": args.cp, "python": sys.version.split()[0], "rows": rows}
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(f"json → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
