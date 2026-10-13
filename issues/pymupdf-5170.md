# Draft: issue to pymupdf/PyMuPDF #5170 ("3.15t support?")

Purpose of this file: hold the exact text and patch we intend to send upstream, so it is
reviewed here first — against the decisions in `docs/decisions.md` — before it leaves the
repository. Nothing in this file is a promise; the status line says what was executed.

## Status, honestly

- `cp315` wheel exists for our build: yes, but for the *patched* MuPDF directory, see below.
- Issue #5170 is open (opened 2026-10-09, "3.15t support?").
- PyPI 1.28.2 carries `cp310`, `cp313`, `cp314` wheels — no `cp315`.
- Not verified: that the maintainers accept this as in-scope for MuPDF rather than PyMuPDF.

## What breaks

CPython 3.15 removes `PyString_FromString`. The MuPDF generator that PyMuPDF ships emits
it unconditionally, so the build fails in generated SWIG code:

    error: implicit declaration of function 'PyString_FromString'

The wall is not in PyMuPDF's own wrappers: it is in the MuPDF tree's generator,
`scripts/wrap/swig.py`, line 743, which writes the call into every binding it generates.
That is why patching `.i` files does not help and why the fix belongs upstream in MuPDF.

## What we did here

Patched the generator directory (not the `.i` files) and built against it; the wheel then
builds, and `import pymupdf` succeeds on CPython 3.15.0. The check that proves it is a real
import on a real 3.15 interpreter — not the presence of a tag in the filename.

## Proposed text for the issue

> The 3.15 build fails in generated code, not in hand-written code:
> `scripts/wrap/swig.py:743` emits `PyString_FromString`, which CPython 3.15 no longer
> provides. Because the call is written by the generator, it appears in every binding and
> cannot be fixed in any `.i` file. Replacing the emitted call with the PyUnicode form
> where the generator is written is the change that makes 3.15 build; patching the
> generated output by hand does not survive regeneration.
