"""
Implementation of integer relations based on
`roaring bitmaps <http://roaringbitmap.org/>`_.
"""

# Copyright (C) 2025 Hashberg Ltd
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

__version__ = "1.0.0.post1"

from collections.abc import Iterable, Iterator
from itertools import product
from math import prod
from typing import Any, Self, final

from pyroaring import BitMap64

type Shape = tuple[int, ...]
"""Type alias for the shape of a relation (see :class:`Rel`)."""

type Entry = tuple[int, ...]
"""
Type alias for an entry in a relation (see :class:`Rel`).

Entries passed to the methods of :class:`Rel` are normalised rather than validated:
see :ref:`entry-normalisation` for the exact contract.
"""


@final
class Rel:
    r"""
    A low-level mutable data structure to store a finite relation between finite sets:

    .. math::

        R \subseteq X_1 \times ... \times X_n

    It presumes that the *component sets* :math:`X_1,...,X_n` are finite zero-based
    contiguous integer ranges, in the form :math:`X_j = \lbrace 0,...,s_j-1 \rbrace`.
    The tuple :math:`(s_1,...,s_n)` of component set sizes is referred to as the *shape*
    of the relation :math:`R`, while the tuples :math:`(x_1,...x_n) \in R` are referred
    to as its *entries*.

    Relations are implemented using 64-bit
    `roaring bitmaps <http://roaringbitmap.org/>`_
    to store the underlying set of entries.

    See :meth:`Rel.__new__` for the constructor.

    **Entry normalisation.**
    This class is designed for use in performance-critical code, so entries are
    *normalised* rather than validated: no method which takes entries ever rejects
    them. An entry is converted into the index of its slot as follows:

    - the element in position :math:`j` is reduced modulo the component set size
      :math:`s_j`, so that negative elements index from the end of the component set
      (as is usual in Python) and out-of-range elements wrap around;
    - if the entry is shorter than the shape, the missing trailing elements are taken
      to be zero;
    - if the entry is longer than the shape, the surplus elements are ignored.

    Because every integer is reduced into the range of its own component set, this is
    a total operation: no entry whatsoever can take a relation outside of its own
    shape, and the invariants of the data structure hold for arbitrary integer input.
    An out-of-range entry silently addresses a well-defined *different* entry, it does
    not corrupt the relation.

    Callers which cannot guarantee that their entries are in range should check them
    with :meth:`Rel.validate_entry`, which exists for exactly this purpose and is
    never called internally. Validation is therefore entirely opt-in, and code which
    understands the tradeoff above pays nothing for it.

    **Equality, ordering and hashing.**
    Relations of different shape are never equal, but they are not ordered either:
    :meth:`Rel.__eq__` returns :obj:`False` on a shape mismatch, whereas
    :meth:`Rel.__lt__` and :meth:`Rel.__le__` raise :class:`ValueError`. This is
    deliberate. Equality is total, because unrelated objects are simply unequal, while
    containment between relations of different shape is a question about incomparable
    domains, which is much more likely to indicate a bug in the caller than a
    meaningful query.

    Relations are mutable, and therefore unhashable: defining :meth:`Rel.__eq__`
    without :meth:`object.__hash__` is what makes them so, by the same convention that
    applies to :class:`set` and :class:`list`. Use :class:`frozenset` of the entries
    where a hashable snapshot of a relation is required.
    """

    __shape: Shape
    """The shape of the relation."""

    __data: BitMap64
    """The bitmap of packed indices for the entries of the relation."""

    __strides: tuple[int, ...]
    """The stride of each component, used to pack entries into indices."""

    __slots__ = ("__weakref__", "__shape", "__data", "__strides")

    def __new__(
        cls,
        shape: Iterable[int],
        data: BitMap64 | Iterable[Entry] | None = None,
    ) -> Self:
        """
        Creates a relation with the given shape and initial data:

        - if ``data`` is a :class:`Rel` instance, performs a copy of that relation;
        - if ``data`` is an iterable of entries, creates a relation with those entries;
        - if ``data`` is a `BitMap64 <https://github.com/Ezibenroc/PyRoaringBitMap>`_,
          creates a relation using the bitmap for the underlying set of entries;
        - if ``data`` is :obj:`None` (default), an empty relation is created.

        Entries taken from an iterable are normalised, as described in
        :ref:`entry-normalisation`. Indices taken from a :class:`Rel` or a bitmap are
        validated instead, because they bypass normalisation entirely: this permits a
        relation to be reinterpreted under any shape large enough to hold its indices,
        while ruling out indices which would fall outside the new shape.

        :raises ValueError: if any component set size is not strictly positive.
        :raises ValueError: if a given relation or bitmap contains an index which is
            out of range for the given shape.
        :raises NotImplementedError: if the product of the component set sizes is too
            large to be indexed by a 64-bit bitmap.

        :meta public:
        """
        shape = tuple(shape)
        if any(s <= 0 for s in shape):
            raise ValueError("Component set sizes must be strictly positive.")
        total_size = prod(shape)
        if total_size >= (1 << 64):
            raise NotImplementedError(
                "The maximum supported size for the Cartesian product "
                "of component sets is 2**64-1."
            )
        self = object.__new__(cls)
        self.__shape = shape
        self.__strides = Rel.__strides_from_shape(shape)
        if data is None:
            self.__data = BitMap64()
        elif isinstance(data, BitMap64):
            if data and data.max() >= total_size:
                raise ValueError("Data bitmap contains invalid entries.")
            self.__data = data.copy()
        elif isinstance(data, Rel):
            other_data = data.__data
            if other_data and other_data.max() >= total_size:
                raise ValueError(
                    "Given relation contains entries which are invalid for this shape."
                )
            self.__data = other_data.copy()
        else:
            # We can use __pack_entry here because it does not access the __data attr:
            packed_entries = [self.__pack_entry(entry) for entry in data]
            self.__data = BitMap64(packed_entries)
        return self

    @property
    def shape(self) -> Shape:
        """The shape of the relation, i.e. the tuple of sizes for its component sets."""
        return self.__shape

    def copy(self) -> "Rel":
        """Returns a copy of the relation (independently mutable)."""
        copy = object.__new__(Rel)
        copy.__shape = self.__shape
        copy.__strides = self.__strides
        copy.__data = self.__data.copy()
        return copy

    def validate_entry(self, entry: Entry) -> None:
        """
        Validates the given entry against the shape of the relation.

        This method is never called internally: the methods of this class normalise
        entries instead of validating them, as described in :ref:`entry-normalisation`.
        It is provided as a convenience for callers which cannot otherwise guarantee
        that an entry is in range, and which would rather have an error than address a
        different entry by accident. Validating every entry is significantly more
        expensive than the operations it guards, so it is left to the caller to decide
        where that cost is worth paying.

        :raises ValueError: if the entry is not valid for the shape.
        """
        shape = self.shape
        if len(entry) != len(shape):
            raise ValueError(
                f"Expected entry of length {len(shape)}, "
                f"found length {len(entry)} instead."
            )
        for i, (el, dim) in enumerate(zip(entry, shape)):
            if not 0 <= el < dim:
                raise ValueError(
                    f"Expected element at index {i} to be in range({dim}), "
                    f"found {el} instead."
                )

    def add(self, entry: Entry) -> None:
        """
        Adds the given entry to the relation.

        The entry is normalised, not validated: see :ref:`entry-normalisation`.
        """
        idx = self.__pack_entry(entry)
        self.__data.add(idx)

    def remove(self, entry: Entry) -> None:
        """
        Removes the given entry from the relation.

        The entry is normalised, not validated: see :ref:`entry-normalisation`.

        :raises KeyError: if the entry is not in the relation.
        """
        idx = self.__pack_entry(entry)
        bitmap = self.__data
        if idx not in bitmap:
            raise KeyError(entry)
        bitmap.remove(idx)

    def flip(self, entry: Entry) -> None:
        """
        Removes the entry from the relation if it is in the relation;
        otherwise, adds the entry to the relation.

        The entry is normalised, not validated: see :ref:`entry-normalisation`.
        """
        idx = self.__pack_entry(entry)
        bitmap = self.__data
        if idx in bitmap:
            bitmap.remove(idx)
        else:
            bitmap.add(idx)

    def update(self, *entry_sets: Iterable[Entry]) -> None:
        """
        Adds all entries from all given iterables to the relation.

        Entries are normalised, not validated: see :ref:`entry-normalisation`.
        """
        packed_entries = [
            self.__pack_entry(entry) for entry_set in entry_sets for entry in entry_set
        ]
        self.__data.update(packed_entries)

    def difference_update(self, *entry_sets: Iterable[Entry]) -> None:
        """
        Removes all entries from all given iterables from the relation.

        Entries are normalised, not validated: see :ref:`entry-normalisation`.
        """
        packed_entries = [
            self.__pack_entry(entry) for entry_set in entry_sets for entry in entry_set
        ]
        update_bitset = BitMap64(packed_entries)
        self.__data.difference_update(update_bitset)

    def symmetric_difference_update(self, *entry_sets: Iterable[Entry]) -> None:
        """
        Flips all entries from all given iterables within the relation.
        That is, removes from the relation all given entries which are in the relation,
        and adds to the relation all given entries which are not in the relation.

        Note that the given entries are considered without repetition, so that multiple
        occurrences of the same entry in the given iterables don't result in multiple
        flips. Because entries are normalised rather than validated (see
        :ref:`entry-normalisation`), entries which normalise to the same slot count as
        repetitions of each other.
        """
        packed_entries = [
            self.__pack_entry(entry) for entry_set in entry_sets for entry in entry_set
        ]
        update_bitset = BitMap64(packed_entries)
        self.__data.symmetric_difference_update(update_bitset)

    def __contains__(self, entry: Entry) -> bool:
        """
        Whether the given entry is in the relation.

        The entry is normalised, not validated: see :ref:`entry-normalisation`. An
        entry which is out of range is therefore not reported as absent, it is taken to
        be the entry it normalises to.

        :meta public:
        """
        idx = self.__pack_entry(entry)
        return idx in self.__data

    def __iter__(self) -> Iterator[Entry]:
        """
        Iterates over all entries in the relation.

        :meta public:
        """
        for idx in self.__data:
            yield self.__unpack_idx(idx)

    def __len__(self) -> int:
        """
        Returns the number of entries in the relation.

        :meta public:
        """
        return len(self.__data)

    def __invert__(self) -> "Rel":
        """
        Returns the relation's complement within the set of all possible entries for
        the relation's own shape.

        :meta public:
        """
        shape, curr_bitset = self.__shape, self.__data
        new_data = BitMap64()
        new_data.add_range(0, prod(shape))
        new_data.difference_update(curr_bitset)
        return self.__with_new_data(new_data)

    def __and__(self, other: "Rel") -> "Rel":
        """
        Returns the intersection of this relation and a given relation of same shape.

        :raises ValueError: if the two relations have different shapes.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Intersection requires relations to have the same shape.")
        new_data = self.__data.intersection(other.__data)
        return self.__with_new_data(new_data)

    def __or__(self, other: "Rel") -> "Rel":
        """
        Returns the union of this relation and a given relation of same shape.

        :raises ValueError: if the two relations have different shapes.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Union requires relations to have the same shape.")
        new_data = self.__data.union(other.__data)
        return self.__with_new_data(new_data)

    def __xor__(self, other: "Rel") -> "Rel":
        """
        Returns the symmetric diff of this relation and a given relation of same shape.

        :raises ValueError: if the two relations have different shapes.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError(
                "Symmetric difference requires relations to have the same shape."
            )
        new_data = self.__data.symmetric_difference(other.__data)
        return self.__with_new_data(new_data)

    def __sub__(self, other: "Rel") -> "Rel":
        """
        Returns the difference of this relation and a given relation of same shape.

        :raises ValueError: if the two relations have different shapes.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Difference requires relations to have the same shape.")
        new_data = self.__data.difference(other.__data)
        return self.__with_new_data(new_data)

    def __iand__(self, other: "Rel") -> Self:
        """
        Inplace version of :meth:`Rel.__and__`, mutating the lhs relation.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Intersection requires relations to have the same shape.")
        self.__data.intersection_update(other.__data)
        return self

    def __ior__(self, other: "Rel") -> Self:
        """
        Inplace version of :meth:`Rel.__or__`, mutating the lhs relation.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Union requires relations to have the same shape.")
        self.__data.update(other.__data)
        return self

    def __ixor__(self, other: "Rel") -> Self:
        """
        Inplace version of :meth:`Rel.__xor__`, mutating the lhs relation.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError(
                "Symmetric difference requires relations to have the same shape."
            )
        self.__data.symmetric_difference_update(other.__data)
        return self

    def __isub__(self, other: "Rel") -> Self:
        """
        Inplace version of :meth:`Rel.__sub__`, mutating the lhs relation.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Difference requires relations to have the same shape.")
        self.__data.difference_update(other.__data)
        return self

    def __eq__(self, other: Any) -> bool:
        """
        Equality comparison between relations, as sets of entries.

        Relations of different shape are never equal, but no error is raised: unlike
        the containment comparisons, equality is total. Note that defining this method
        makes relations unhashable, as befits a mutable container.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            return False
        return self.__data == other.__data

    def __lt__(self, other: Any) -> bool:
        """
        Strict containment comparison between relations, as sets of entries.

        Unlike :meth:`Rel.__eq__`, this raises on a shape mismatch rather than
        returning :obj:`False`: containment between relations over different domains is
        much more likely to indicate a bug than a meaningful query.

        :raises ValueError: if the two relations have different shapes.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Comparison requires relations to have the same shape.")
        return self.__data < other.__data

    def __le__(self, other: Any) -> bool:
        """
        Containment comparison between relations, as sets of entries.

        Unlike :meth:`Rel.__eq__`, this raises on a shape mismatch rather than
        returning :obj:`False`: see :meth:`Rel.__lt__`.

        :raises ValueError: if the two relations have different shapes.

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Comparison requires relations to have the same shape.")
        return self.__data <= other.__data

    def __repr__(self) -> str:
        return f"<Rel of shape {self.__shape} with {len(self)} entries>"

    def __getnewargs__(self) -> tuple[Shape]:
        """
        Returns the arguments to :meth:`Rel.__new__` used to unpickle the relation,
        namely its shape. The entries are restored separately, by
        :meth:`Rel.__setstate__`.

        :meta public:
        """
        return (self.__shape,)

    def __getstate__(self) -> bytes:
        """
        Returns the state used to pickle the relation, as the serialised form of the
        underlying bitmap. The shape is not part of the state, because it is already
        restored by :meth:`Rel.__getnewargs__`.

        :meta public:
        """
        return bytes(self.__data.serialize())

    def __setstate__(self, state: bytes) -> None:
        """
        Restores the entries of a relation being unpickled, from the state returned by
        :meth:`Rel.__getstate__`. The shape and strides have already been set by
        :meth:`Rel.__new__`, via :meth:`Rel.__getnewargs__`.

        :meta public:
        """
        self.__data = BitMap64.deserialize(state)

    @staticmethod
    def iter_entries(shape: Iterable[int]) -> Iterator[Entry]:
        """Iterates over all possible entries for the given shape."""
        return iter(product(*map(range, shape)))

    def __pack_entry(self, entry: Entry) -> int:
        return sum(
            ((idx + dim) % dim) * stride
            for idx, dim, stride in zip(entry, self.__shape, self.__strides)
        )

    def __unpack_idx(self, idx: int) -> Entry:
        shape, strides = self.__shape, self.__strides
        entry = [0] * len(shape)
        idx_rem = idx
        for i, (dim, stride) in enumerate(zip(shape, strides)):
            val = idx_rem // stride
            entry[i] = val % dim
            idx_rem -= val * stride
        return tuple(entry)

    def __with_new_data(self, new_data: BitMap64) -> "Rel":
        instance = object.__new__(Rel)
        instance.__shape = self.__shape
        instance.__strides = self.__strides
        instance.__data = new_data
        return instance

    @staticmethod
    def __strides_from_shape(shape: Shape) -> tuple[int, ...]:
        seq = (1,) + tuple(reversed(shape))[:-1]
        prod = 1
        strides: list[int] = []
        for x in seq:
            prod *= int(x)
            strides.append(prod)
        strides.reverse()
        return tuple(strides)
