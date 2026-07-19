# RoaringRel

[![Python versions](https://img.shields.io/badge/python-3.13+-green.svg)](https://docs.python.org/3.13/)
[![PyPI version](https://img.shields.io/pypi/v/roaringrel.svg)](https://pypi.python.org/pypi/roaringrel/)
[![PyPI status](https://img.shields.io/pypi/status/roaringrel.svg)](https://pypi.python.org/pypi/roaringrel/)
[![Checked with Mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](https://github.com/python/mypy)
[![Documentation Status](https://readthedocs.org/projects/roaringrel/badge/?version=latest)](https://roaringrel.readthedocs.io/en/latest/?badge=latest)

RoaringRel is a low-level mutable data structure for finite relations `R ⊆ X₁ × ... × Xₙ` between finite sets, built on 64-bit [roaring bitmaps](http://roaringbitmap.org/).
It presumes that the *component sets* `X₁,...,Xₙ` are zero-based contiguous integer ranges `Xⱼ = {0,...,sⱼ-1}`: the tuple `(s₁,...,sₙ)` of component set sizes is the *shape* of the relation, and the tuples `(x₁,...,xₙ) ∈ R` are its *entries*.

## Install

You can install the latest release from [PyPI](https://pypi.org/project/roaringrel/) as follows:

```console
$ pip install roaringrel
```

## Usage

All functionality of the library is accessible from the `Rel` class, which is created from a shape and, optionally, some initial entries:

```python
>>> from roaringrel import Rel
>>> r = Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1), (1, 2, 3)])
>>> len(r)
3
>>> (0, 0, 0) in r
True
```

Relations behave as sets of entries, supporting the usual binary operators (`&`, `|`, `^`, `-`), their in-place counterparts, containment comparison, and entry-wise mutation via `add`, `remove` and `flip`.

Because this is a low-level structure aimed at performance-critical code, entries are *normalised* rather than validated: out-of-range elements wrap around modulo their component set size, and no method rejects an entry.
This cannot corrupt a relation — every entry normalises into a valid slot — but it does mean that an out-of-range entry silently addresses a different one.
Use the `validate_entry` method where that tradeoff is not acceptable; it is never called internally, so validation costs nothing unless you ask for it.

For an overview of library features and usage, see the [getting started guide](https://roaringrel.readthedocs.io/en/latest/getting-started.html).

## Project structure

- `roaringrel/` — the library itself, a single module defining the `Rel` class along with the `Shape` and `Entry` type aliases.
- `test/` — the test suite, run with `pytest`.
- `docs/` — the Sphinx documentation sources, together with the scripts used to generate the API documentation.
- `autodoc_typehints.py` — a custom Sphinx extension which renders type hints in the API documentation.

## API

For the full API documentation, see <https://roaringrel.readthedocs.io/>.

## License

[LGPLv3 © Hashberg.](LICENSE)
