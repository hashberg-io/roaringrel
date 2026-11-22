import copy
import pickle
from itertools import product
from math import isqrt, prod
import pytest
import numpy as np
from numpy.random import default_rng
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
    copy = Rel(shape, rel._Rel__data)  # type: ignore[attr-defined]
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


@pytest.mark.parametrize(
    "shape,lhs_entryset,rhs_entryset",
    [
        (shape, lhs_entryset, rhs_entryset)
        for shape, entryset_pair_samples in rel_pair_samples.items()
        for lhs_entryset, rhs_entryset in entryset_pair_samples
    ],
)
def test_inplace_binops_dont_touch_rhs(
    shape: Shape, lhs_entryset: frozenset[Entry], rhs_entryset: frozenset[Entry]
) -> None:
    """The in-place operators mutate the lhs bitmap directly, so this pins down that
    they leave the rhs relation, and any prior copy of the lhs, untouched."""
    for op in ("&", "|", "^", "-"):
        lhs = Rel(shape, lhs_entryset)
        rhs = Rel(shape, rhs_entryset)
        snapshot = lhs.copy()
        if op == "&":
            lhs &= rhs
        elif op == "|":
            lhs |= rhs
        elif op == "^":
            lhs ^= rhs
        else:
            lhs -= rhs
        assert frozenset(rhs) == rhs_entryset, f"'{op}=' mutated the rhs relation"
        assert frozenset(snapshot) == lhs_entryset, f"'{op}=' mutated a prior copy"


@pytest.mark.parametrize(
    "shape,entryset",
    [
        (shape, entryset)
        for shape, entryset_samples in rel_param_samples.items()
        for entryset in entryset_samples
    ],
)
def test_inplace_binops_self_operand(shape: Shape, entryset: frozenset[Entry]) -> None:
    """In-place operators applied to a relation and itself, where mutating the lhs
    bitmap while reading it as the rhs would be observable if it were unsound."""
    rel = Rel(shape, entryset)
    rel &= rel
    assert frozenset(rel) == entryset
    rel |= rel
    assert frozenset(rel) == entryset
    rel -= rel
    assert frozenset(rel) == frozenset()
    rel = Rel(shape, entryset)
    rel ^= rel
    assert frozenset(rel) == frozenset()


@pytest.mark.parametrize(
    "shape,entryset",
    [
        (shape, entryset)
        for shape, entryset_samples in rel_param_samples.items()
        for entryset in entryset_samples
    ],
)
def test_pickle(shape: Shape, entryset: frozenset[Entry]) -> None:
    rel = Rel(shape, entryset)
    for protocol in range(2, pickle.HIGHEST_PROTOCOL + 1):
        unpickled = pickle.loads(pickle.dumps(rel, protocol))
        assert unpickled.shape == shape
        assert frozenset(unpickled) == entryset
        assert unpickled == rel
        assert unpickled is not rel
    unpickled = pickle.loads(pickle.dumps(rel))
    all_entries = frozenset(Rel.iter_entries(shape))
    missing_entries = all_entries - entryset
    if missing_entries:
        unpickled.add(next(iter(sorted(missing_entries))))
        assert frozenset(rel) == entryset


@pytest.mark.parametrize(
    "shape,entryset",
    [
        (shape, entryset)
        for shape, entryset_samples in rel_param_samples.items()
        for entryset in entryset_samples
    ],
)
def test_copy_module(shape: Shape, entryset: frozenset[Entry]) -> None:
    rel = Rel(shape, entryset)
    for clone in (copy.copy(rel), copy.deepcopy(rel)):
        assert clone == rel
        assert clone is not rel
        clone.symmetric_difference_update(Rel.iter_entries(shape))
        assert frozenset(rel) == entryset


def test_unpickling_rejects_invalid_state() -> None:
    rel = Rel((2, 2), [(1, 1)])
    state = bytes(BitMap64([3]).serialize())
    assert pickle.loads(pickle.dumps(rel)) == rel
    for idx in [4, 99, 1 << 40]:
        tampered = pickle.dumps(rel).replace(state, bytes(BitMap64([idx]).serialize()))
        with pytest.raises(ValueError):
            pickle.loads(tampered)


def test_constructor_rejects_invalid_shape() -> None:
    for shape in [(0,), (2, 0), (-1,), (2, -3, 4)]:
        with pytest.raises(ValueError):
            Rel(shape)
    with pytest.raises(NotImplementedError):
        Rel((1 << 32, 1 << 32))


def test_constructor_converts_shape_to_int() -> None:
    rel = Rel([np.int64(2), np.uint8(3), True], [(1, 2, 0)])
    assert rel.shape == (2, 3, 1)
    assert all(type(s) is int for s in rel.shape)
    assert list(rel) == [(1, 2, 0)]


def test_constructor_rejects_non_integer_shape() -> None:
    for shape in [(2.0,), (2, 3.5), ("2",), (None,)]:
        with pytest.raises(TypeError):
            Rel(shape)  # type: ignore[arg-type]


def test_constructor_rejects_oversized_numpy_shape() -> None:
    with pytest.raises(NotImplementedError):
        Rel((np.int64(1 << 40), np.int64(1 << 40)))


def test_constructor_rejects_invalid_bitmap() -> None:
    shape = (2, 3, 4)
    total_size = prod(shape)
    for idx in [total_size, total_size + 1, 1 << 40]:
        with pytest.raises(ValueError):
            Rel(shape, BitMap64([idx]))
    Rel(shape, BitMap64([total_size - 1]))
    Rel(shape, BitMap64())


def test_constructor_rejects_oversized_relation() -> None:
    """A relation may be reinterpreted under another shape, provided that every one of
    its indices remains in range for that shape."""
    big = Rel((5, 5), [(4, 4)])
    with pytest.raises(ValueError):
        Rel((2, 2), big)
    reinterpreted = Rel((2, 6), Rel((3, 4), [(2, 3)]))
    assert list(reinterpreted) == [(1, 5)]
    assert list(Rel((5, 5), big)) == [(4, 4)]


def test_validate_entry_rejects_invalid_entries() -> None:
    rel = Rel((2, 3, 4))
    rel.validate_entry((0, 0, 0))
    rel.validate_entry((1, 2, 3))
    for entry in [(0, 0), (0, 0, 0, 0), ()]:
        with pytest.raises(ValueError):
            rel.validate_entry(entry)
    for entry in [(2, 0, 0), (0, 3, 0), (0, 0, 4), (-1, 0, 0), (0, -1, 0)]:
        with pytest.raises(ValueError):
            rel.validate_entry(entry)


def test_entry_normalisation() -> None:
    """Entries are normalised rather than validated, by design: this pins down the
    exact contract, so that it is not mistaken for a missing bounds check."""
    rel = Rel((2, 3, 4))
    rel.add((0, -1, -1))
    assert list(rel) == [(0, 2, 3)]
    rel = Rel((2, 3, 4))
    rel.add((0, 5, 0))
    assert list(rel) == [(0, 2, 0)]
    rel = Rel((2, 3, 4))
    rel.add((1,))
    assert list(rel) == [(1, 0, 0)]
    rel = Rel((2, 3, 4))
    rel.add((0, 1, 2, 9, 9))
    assert list(rel) == [(0, 1, 2)]
    rel = Rel((2, 3, 4))
    rel.add((10**30, 0, 0))
    assert list(rel) == [(0, 0, 0)]


def test_entry_normalisation_is_total() -> None:
    """Whatever entry is passed, the relation stays within its own shape."""
    shape = (2, 3, 4)
    all_entries = frozenset(Rel.iter_entries(shape))
    wild_entries: list[Entry] = [
        (-7, -7, -7),
        (100, 100, 100),
        (),
        (1,),
        (1, 1, 1, 1, 1),
        (10**30, -(10**30), 0),
    ]
    for entry in wild_entries:
        rel = Rel(shape)
        rel.add(entry)
        assert len(rel) == 1
        assert frozenset(rel) <= all_entries
        assert entry in rel
        rel.remove(entry)
        assert len(rel) == 0
    rel = Rel(shape)
    rel.update(wild_entries)
    assert frozenset(rel) <= all_entries
    assert len(rel) + len(~rel) == prod(shape)


def test_binops_reject_shape_mismatch() -> None:
    lhs = Rel((2, 3))
    rhs = Rel((3, 2))
    for op in ["__and__", "__or__", "__xor__", "__sub__"]:
        with pytest.raises(ValueError):
            getattr(lhs, op)(rhs)
    for op in ["__iand__", "__ior__", "__ixor__", "__isub__"]:
        with pytest.raises(ValueError):
            getattr(lhs.copy(), op)(rhs)
    for op in ["__lt__", "__le__"]:
        with pytest.raises(ValueError):
            getattr(lhs, op)(rhs)


def test_eq_is_total_across_shapes() -> None:
    """Equality is total where containment is not: relations of different shape are
    unequal rather than incomparable."""
    assert Rel((2, 3)) != Rel((3, 2))
    assert Rel((2, 3)) != Rel((2, 3, 1))
    assert Rel((2, 3)) == Rel((2, 3))
    assert not Rel((2, 3)) == Rel((3, 2))


def test_ops_with_non_rel_operands() -> None:
    rel = Rel((2, 3))
    for other in [42, "spam", None, [(0, 0)]]:
        assert rel != other
        assert not rel == other
        for op in ["__and__", "__or__", "__xor__", "__sub__"]:
            assert getattr(rel, op)(other) is NotImplemented
        for op in ["__lt__", "__le__"]:
            assert getattr(rel, op)(other) is NotImplemented
        with pytest.raises(TypeError):
            rel & other  # type: ignore[operator]


def test_relations_are_unhashable() -> None:
    """Relations are mutable, so they are unhashable by design."""
    with pytest.raises(TypeError):
        hash(Rel((2, 3)))


def test_iter_entries() -> None:
    assert list(Rel.iter_entries((2, 3))) == [
        (0, 0),
        (0, 1),
        (0, 2),
        (1, 0),
        (1, 1),
        (1, 2),
    ]
    assert list(Rel.iter_entries(())) == [()]
    assert list(Rel.iter_entries((1,))) == [(0,)]
    for shape in [(2,), (2, 3), (2, 3, 4)]:
        assert len(list(Rel.iter_entries(shape))) == prod(shape)
        assert list(Rel.iter_entries(shape)) == list(
            Rel(shape, Rel.iter_entries(shape))
        )


def test_repr() -> None:
    assert repr(Rel((2, 3, 4))) == "<Rel of shape (2, 3, 4) with 0 entries>"
    assert (
        repr(Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1)]))
        == "<Rel of shape (2, 3, 4) with 2 entries>"
    )
    assert repr(Rel(())) == "<Rel of shape () with 0 entries>"


def test_no_instance_dict() -> None:
    rel = Rel((2, 3))
    assert not hasattr(rel, "__dict__")
    with pytest.raises(AttributeError):
        rel.spam = 42  # type: ignore[attr-defined]
