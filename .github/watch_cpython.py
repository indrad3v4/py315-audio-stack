#!/usr/bin/env python3
"""Watch python.org for CPython releases. Stdlib only, no third-party imports.

Runs daily in CI. Three things can happen:

  * a tracked minor gets a new *patch* (3.15.0 -> 3.15.1). The wheel tag does not
    change (cp315 stays cp315), so nothing is rebuilt; the state file records it.
  * a *new minor* appears (3.16). The job opens an issue and dispatches the wheel
    build for that minor. The build still has to pass its own import test before
    anyone tags anything -- this script never publishes.
  * nothing changed. It says so and exits.

State lives in state/cpython-seen.json so the next run knows what was already
handled. `--dry-run` prints the decisions and touches nothing.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

LISTING_URL = "https://www.python.org/ftp/python/"
STATE_PATH = "state/cpython-seen.json"
ISSUE_LABEL = "cpython-watch"
WHEELS_WORKFLOW = "wheels.yml"


def listing(url=LISTING_URL):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf8", "replace")


def versions(html):
    """{'3.15': {'3.15.0', '3.15.1'}, ...} from the /ftp/python/ index."""
    found = {}
    for match in re.finditer(r'href="(\d+)\.(\d+)\.(\d+)/"', html):
        major, minor, patch = (int(part) for part in match.groups())
        found.setdefault(f"{major}.{minor}", set()).add(f"{major}.{minor}.{patch}")
    return found


def sort_key(version):
    return tuple(int(part) for part in version.split("."))


def read_state(path=STATE_PATH):
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {"tracked": {}, "new_minors": []}


def write_state(state, path=STATE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}", file=sys.stderr)
    return result


def issue_body(minor, newest, repo):
    return f"""`python.org` now lists **{minor}** (newest {newest}), and the wheel
matrix here has never built for it.

What already happened automatically: this issue, and a `{WHEELS_WORKFLOW}` dispatch
for `minor={minor}` — so the build is already running. Watch it under Actions.

What still needs a person, if the build goes red:

1. `CIBW_BUILD` is derived from the minor, so the selector is fine.
2. Every matrix line may need a different manylinux image, system package or
   patch for the new minor. Failed runs say which; the run-by-run notes in the
   README are the place to record it.
3. Pre-release interpreters need `CIBW_ENABLE=cpython-prerelease` (set the repo
   variable `CIBW_ENABLE`), and a final release should drop it again.

Wheels are only published when they import on a live interpreter, so nothing in
this issue has to be undone if the build fails.
"""


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    tracked = [m for m in (os.environ.get("TRACKED_MINORS") or "3.15").split() if m]

    html = listing()
    found = versions(html)
    if not found:
        sys.exit("nothing parsed from the python.org listing -- refusing to guess")
    newest_overall = max((v for vs in found.values() for v in vs), key=sort_key)

    state = read_state()
    known_minors = set(tracked) | set(state.get("new_minors", []))
    seen_ceiling = max(sort_key(m) for m in tracked)

    print(f"лістынг: {len(found)} мінораў, найноўшае наогул {newest_overall}")
    changed = False

    for minor in tracked:
        if minor not in found:
            print(f"{minor}: няма ў лістынгу")
            continue
        newest = max(found[minor], key=sort_key)
        previous = state["tracked"].get(minor)
        if previous != newest:
            state["tracked"][minor] = newest
            changed = True
            note = "той жа ABI-тэг, перазборкі не патрэбна" if previous else "першы запіс"
            print(f"{minor}: {previous} -> {newest} ({note})")
        else:
            print(f"{minor}: {newest} (без змен)")

    new_minors = []
    for minor in sorted(found, key=sort_key):
        if minor in known_minors or sort_key(minor) <= seen_ceiling:
            continue
        newest = max(found[minor], key=sort_key)
        new_minors.append((minor, newest))
        print(f"НОВЫ МІНОР: {minor} (найноўшае {newest})")

    if new_minors:
        for minor, newest in new_minors:
            if dry_run:
                print(f"[dry-run] быў бы issue + dispatch для {minor}")
                continue
            title = f"CPython {minor} is out — build the wheels"
            existing = gh(
                "issue", "list", "--repo", repo, "--state", "open",
                "--label", ISSUE_LABEL, "--search", f"{minor} in:title",
                "--json", "number", "--jq", "length",
            ).stdout.strip()
            if existing not in ("", "0"):
                print(f"{minor}: issue ужо ёсць, новае не ствараю")
            else:
                gh(
                    "issue", "create", "--repo", repo,
                    "--title", title,
                    "--label", ISSUE_LABEL,
                    "--body", issue_body(minor, newest, repo),
                )
                print(f"{minor}: issue створаны")
            dispatched = gh(
                "workflow", "run", WHEELS_WORKFLOW, "--repo", repo, "--ref", "main",
                "-f", f"minor={minor}",
            )
            print(f"{minor}: dispatch {'ok' if dispatched.returncode == 0 else 'не прайшоў'}")
        state["new_minors"] = sorted(set(state.get("new_minors", [])) | {m for m, _ in new_minors})
        changed = True

    if dry_run:
        print("[dry-run] state не запісаны")
    elif changed:
        write_state(state)
        print(f"state запісаны: {STATE_PATH}")
    else:
        print("змен няма, state не чапаю")
    return 0


if __name__ == "__main__":
    sys.exit(main())
