# Decisions this repository is held to

These are frozen decisions, in the shape Prelint reads them: a statement, and the reason
it exists. Any pull request that contradicts one of them is drift, however well the code
works. Numbered so a review comment can cite the number.

## D1 — Evidence over claims

A fix is not done when the job is green; it is done when the artifact is loaded. Every
change here ends in a command that exercises the thing on a real interpreter:
`import av` on CPython 3.15, `grep -c PyString_` equals zero, `pkg-config --modversion
libavcodec`. Reports name what was **not** executed.

*Why:* this repository exists because four different packages all claimed 3.15 support in
their metadata while failing to import on it. Green metadata is the failure mode.

## D2 — No environment variable as transport

Build inputs do not travel between layers through environment variables. Rust, FFmpeg,
Ninja and libclang all failed here because a variable was set in the host step while the
container never saw it, or in `CIBW_ENVIRONMENT` where the failing step could not read
it. What travels reliably is a path in the filesystem that the failing step can already
see.

*Why:* a variable set in the wrong layer produces a log that looks correct and a build
that dies thirty seconds later.

## D3 — A gate must survive its own success

A check whose success condition is "nothing found" must not fail under `set -e` at the
moment it starts working, and it must write its verdict where the next layer reads it.

*Why:* the first version of the MuPDF patch gate failed exactly when the patch applied
cleanly — it reported a red for the best possible outcome.

## D4 — No prefix already inside the variable

An identifier stored with its own prefix must never be given a second one. The wheel tag
lives in `CP_TAG` / `inputs.tag` *with* its `cp`; writing the field as
`cp${{ inputs.tag || 'cp315' }}` builds `cpcp315`, cibuildwheel finds no such build
identifier, and every job dies inside a minute while the YAML still parses and
`actionlint` still passes.

*Why:* only the run itself caught this. Configuration linters did not.

## D5 — Compute tags in code, not in YAML

GitHub expressions have no `replace()`. Deriving a version or a tag inside a workflow
expression is not a style preference, it is invalid: the file fails to parse. Compute it
in the script that dispatches, where it can be tested.

*Why:* the watcher's first live run died on the expression parser, not on the build.

## D6 — Build only for minors that exist

A package can ship a `cp<minor>` tag only for a CPython minor that is present in the
interpreter matrix. Never add a wheel target ahead of the interpreter release, and never
widen the matrix to make a tag appear.

*Why:* wheels for a nonexistent interpreter are noise in the index and lies in the
metadata.

## D7 — The watcher stays stdlib-only

The CPython watcher runs on the runner's bare interpreter with nothing installed.
It must remain stdlib-only and keep working under `--dry-run`, because it is the thing
that tells us when a new interpreter is worth a release at all.

*Why:* a watcher that needs an install is a watcher that can fail for reasons unrelated
to the thing it watches.

## What these decisions are not

They do not describe code style, test coverage, or architecture. Prelint reviews the
product layer; the linters and the reviewers cover the rest.

## D8 — libclang: имя пакета ≠ имя модуля (проверено 2026-10-13)

**Решение.** В шаге установки инструментов CI не выводить путь из импортируемого
модуля `libclang`: пакет с этим именем на PyPI ставит модуль `clang`. Устанавливать
`libclang`, а `LIBCLANG_PATH` указывать на `clang/native` и до записи в
`GITHUB_ENV` доказывать наличие файла командой `ls -la "$LIBCLANG_PATH/libclang.so"`.

**Почему.** Версия v5 выводила путь из модуля, которого не существует, — шаг падал
с `ModuleNotFoundError` после успешной установки пакета. Проверено на колесе
`libclang-18.1.1-py2.py3-none-manylinux2010_x86_64.whl`, где лежат `clang/__init__.py`
и `clang/native/libclang.so`.

**Результат.** Четыре колеса cp315 собираются зелёными: run 38411806350 на `main`,
run 38414571512 на ветке `draft/pymupdf-issue-5170`.
