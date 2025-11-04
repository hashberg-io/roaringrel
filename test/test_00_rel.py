from collections.abc import Iterable
from itertools import product
from math import ceil, isqrt, prod, sqrt
import pytest
from numpy.random import Generator, default_rng
from pyroaring import BitMap64
from roaringrel import Entry, Rel, Shape


ARITIES = range(0, 6)
SET_SIZES = range(1, 5)

NUM_SHAPE_SAMPLES = 10
NUM_REL_SAMPLES = 10

SEED = 0


rng = default_rng(SEED)
arity_samples = [int(n) for n in rng.choice(ARITIES, NUM_SHAPE_SAMPLES, replace=True)]
shape_samples = [
    tuple(map(int, rng.choice(SET_SIZES, arity, replace=True)))
    for arity in arity_samples
]
rel_param_samples: dict[Shape, list[frozenset[Entry]]] = {}
for shape in shape_samples:
    entryset_samples: list[frozenset[Entry]] = []
    rel_param_samples[shape] = entryset_samples
    all_entries = tuple(Rel.iter_entries(shape))
    total_size = prod(shape)
    entryset_samples.append(frozenset())
    if total_size > 1:
        rel_size_samples = rng.integers(1, total_size, NUM_REL_SAMPLES)
        for rel_size in rel_size_samples:
            entryset = frozenset(
                tuple(map(int, _entry))
                for _entry in rng.choice(all_entries, rel_size, replace=False)
            )
            entryset_samples.append(entryset)
    entryset_samples.append(frozenset(all_entries))


@pytest.mark.parametrize(
    "shape,entryset",
    [
        (shape, entryset)
        for shape, entryset_samples in rel_param_samples.items()
        for entryset in entryset_samples
    ],
)
def test_constructor(shape: Shape, entryset: frozenset[Entry]) -> None:
    all_entries = frozenset(Rel.iter_entries(shape))
    missing_entries = all_entries - entryset
    rel = Rel(shape, entryset)
    assert rel.shape == shape
    assert len(rel) == len(entryset)
    assert frozenset(rel) == entryset
    assert all(entry in rel for entry in entryset)
    assert all(entry not in rel for entry in missing_entries)
    for entry in all_entries:
        rel.validate_entry(entry)
    with pytest.raises(ValueError):
        bitmap = BitMap64([prod(shape)])
        Rel(shape, bitmap)


@pytest.mark.parametrize(
    "shape,entryset",
    [
        (shape, entryset)
        for shape, entryset_samples in rel_param_samples.items()
        for entryset in entryset_samples
    ],
)
def test_copy(shape: Shape, entryset: frozenset[Entry]) -> None:
    all_entries = frozenset(Rel.iter_entries(shape))
    missing_entries = all_entries - entryset
    rel = Rel(shape, entryset)
    # copy() method:
    copy = rel.copy()
    assert copy.shape == shape
    assert len(copy) == len(entryset)
    assert frozenset(copy) == entryset
    assert all(entry in copy for entry in entryset)
    assert all(entry not in copy for entry in missing_entries)
    for entry in all_entries:
        copy.validate_entry(entry)
    assert rel == copy
    # Rel copy constructor:
    copy = Rel(shape, rel)
    assert copy.shape == shape
    assert len(copy) == len(entryset)
    assert frozenset(copy) == entryset
    assert all(entry in copy for entry in entryset)
    assert all(entry not in copy for entry in missing_entries)
    for entry in all_entries:
        copy.validate_entry(entry)
    assert rel == copy
    # BitMap64 copy constructor:
    copy = Rel(shape, rel._Rel__data) # type: ignore[attr-defined]
    assert copy.shape == shape
    assert len(copy) == len(entryset)
    assert frozenset(copy) == entryset
    assert all(entry in copy for entry in entryset)
    assert all(entry not in copy for entry in missing_entries)
    for entry in all_entries:
        copy.validate_entry(entry)
    assert rel == copy

@pytest.mark.parametrize(
    "shape,entryset",
    [
        (shape, entryset)
        for shape, entryset_samples in rel_param_samples.items()
        for entryset in entryset_samples
    ],
)
def test_invert(shape: Shape, entryset: frozenset[Entry]) -> None:
    all_entries = frozenset(Rel.iter_entries(shape))
    missing_entries = all_entries - entryset
    rel = Rel(shape, entryset)
    rel_inv = ~rel
    assert rel_inv.shape == shape
    assert len(rel_inv) == len(missing_entries)
    assert frozenset(rel_inv) == missing_entries
    assert all(entry not in rel_inv for entry in entryset)
    assert all(entry in rel_inv for entry in missing_entries)
    for entry in all_entries:
        rel_inv.validate_entry(entry)


NUM_REL_SAMPLES_ISQRT = isqrt(NUM_REL_SAMPLES) + 1


def select_entryset_samples(
    entryset_samples: list[frozenset[Entry]], num_samples: int
) -> list[frozenset[Entry]]:
    assert len(entryset_samples) >= 2
    selected_samples = [entryset_samples[0]]
    if len(entryset_samples) > 2:
        selected_samples.extend(rng.choice(entryset_samples[1:-1], num_samples))  # type: ignore
    selected_samples.append(entryset_samples[-1])
    return selected_samples


rel_pair_samples: dict[Shape, list[tuple[frozenset[Entry], frozenset[Entry]]]] = {}
for shape, entryset_samples in rel_param_samples.items():
    lhs_samples = select_entryset_samples(entryset_samples, NUM_REL_SAMPLES_ISQRT)
    rhs_samples = select_entryset_samples(entryset_samples, NUM_REL_SAMPLES_ISQRT)
    rel_pair_samples[shape] = list(product(lhs_samples, rhs_samples))


@pytest.mark.parametrize(
    "shape,lhs_entryset,rhs_entryset",
    [
        (shape, lhs_entryset, rhs_entryset)
        for shape, entryset_pair_samples in rel_pair_samples.items()
        for lhs_entryset, rhs_entryset in entryset_pair_samples
    ],
)
def test_binops(
    shape: Shape, lhs_entryset: frozenset[Entry], rhs_entryset: frozenset[Entry]
) -> None:
    lhs = Rel(shape, lhs_entryset)
    rhs = Rel(shape, rhs_entryset)
    assert frozenset(lhs & rhs) == lhs_entryset & rhs_entryset
    assert frozenset(lhs | rhs) == lhs_entryset | rhs_entryset
    assert frozenset(lhs ^ rhs) == lhs_entryset ^ rhs_entryset
    assert frozenset(lhs - rhs) == lhs_entryset - rhs_entryset


@pytest.mark.parametrize(
    "shape,lhs_entryset,rhs_entryset",
    [
        (shape, lhs_entryset, rhs_entryset)
        for shape, entryset_pair_samples in rel_pair_samples.items()
        for lhs_entryset, rhs_entryset in entryset_pair_samples
    ],
)
def test_inplace_binops(
    shape: Shape, lhs_entryset: frozenset[Entry], rhs_entryset: frozenset[Entry]
) -> None:
    lhs = Rel(shape, lhs_entryset)
    rhs = Rel(shape, rhs_entryset)
    res = lhs.copy()
    _res = res
    res &= rhs
    assert res is _res and frozenset(_res) == lhs_entryset & rhs_entryset
    res = lhs.copy()
    _res = res
    res |= rhs
    assert res is _res and frozenset(_res) == lhs_entryset | rhs_entryset
    res = lhs.copy()
    _res = res
    res ^= rhs
    assert res is _res and frozenset(_res) == lhs_entryset ^ rhs_entryset
    res = lhs.copy()
    _res = res
    res -= rhs
    assert res is _res and frozenset(_res) == lhs_entryset - rhs_entryset


@pytest.mark.parametrize(
    "shape,lhs_entryset,rhs_entryset",
    [
        (shape, lhs_entryset, rhs_entryset)
        for shape, entryset_pair_samples in rel_pair_samples.items()
        for lhs_entryset, rhs_entryset in entryset_pair_samples
    ],
)
def test_inplace_updates(
    shape: Shape, lhs_entryset: frozenset[Entry], rhs_entryset: frozenset[Entry]
) -> None:
    lhs = Rel(shape, lhs_entryset)
    res = lhs.copy()
    _res = res
    res.update(rhs_entryset)
    assert res is _res and frozenset(_res) == lhs_entryset | rhs_entryset
    res = lhs.copy()
    _res = res
    res.symmetric_difference_update(rhs_entryset)
    assert res is _res and frozenset(_res) == lhs_entryset ^ rhs_entryset
    res = lhs.copy()
    _res = res
    res.difference_update(rhs_entryset)
    assert res is _res and frozenset(_res) == lhs_entryset - rhs_entryset


@pytest.mark.parametrize(
    "shape,lhs_entryset,rhs_entryset",
    [
        (shape, lhs_entryset, rhs_entryset)
        for shape, entryset_pair_samples in rel_pair_samples.items()
        for lhs_entryset, rhs_entryset in entryset_pair_samples
    ],
)
def test_inplace_entrywise_update(
    shape: Shape, lhs_entryset: frozenset[Entry], rhs_entryset: frozenset[Entry]
) -> None:
    lhs = Rel(shape, lhs_entryset)
    res = lhs.copy()
    _res = res
    for entry in sorted(rhs_entryset):
        res.add(entry)
    assert res is _res and frozenset(_res) == lhs_entryset | rhs_entryset
    res = lhs.copy()
    _res = res
    for entry in sorted(rhs_entryset):
        res.flip(entry)
    assert res is _res and frozenset(_res) == lhs_entryset ^ rhs_entryset
    res = lhs.copy()
    _res = res
    for entry in sorted(rhs_entryset):
        if entry in res:
            res.remove(entry)
        else:
            with pytest.raises(KeyError):
                res.remove(entry)
    assert res is _res and frozenset(_res) == lhs_entryset - rhs_entryset


@pytest.mark.parametrize(
    "shape,lhs_entryset,rhs_entryset",
    [
        (shape, lhs_entryset, rhs_entryset)
        for shape, entryset_pair_samples in rel_pair_samples.items()
        for lhs_entryset, rhs_entryset in entryset_pair_samples
    ],
)
def test_containment(
    shape: Shape, lhs_entryset: frozenset[Entry], rhs_entryset: frozenset[Entry]
) -> None:
    lhs = Rel(shape, lhs_entryset)
    rhs = Rel(shape, rhs_entryset)
    empty = Rel(shape)
    full = Rel(shape, Rel.iter_entries(shape))
    assert empty <= lhs and empty <= rhs
    assert lhs <= full and rhs <= full
    assert lhs & rhs <= lhs and lhs & rhs <= rhs
    assert lhs <= lhs | rhs and rhs <= lhs | rhs
    assert lhs - rhs <= lhs and rhs - lhs <= rhs
