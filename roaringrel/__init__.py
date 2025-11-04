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

__version__ = "1.0.0.post0"

from collections.abc import Iterable, Iterator
from itertools import product
from math import prod
from typing import Any, Self

from pyroaring import BitMap64

type Shape = tuple[int, ...]
"""Type alias for the shape of a relation (see :class:`Rel`)."""

type Entry = tuple[int, ...]
"""Type alias for an entry in a relation (see :class:`Rel`)."""


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
    """

    __shape: Shape
    __data: BitMap64
    __strides: tuple[int, ...]

    __slots__ = ("__weakref__", "__shape", "__data", "__strides")

    def __new__(
        cls,
        shape: Iterable[int],
        data: BitMap64 | Rel | Iterable[Entry] | None = None,
    ) -> Self:
        """
        Creates a relation with the given shape and initial data:

        - if ``data`` is a :class:`Rel` instance, performs a copy of that relation;
        - if ``data`` is an iterable of entries, creates a relation with those entries;
        - if ``data`` is a `BitMap64 <https://github.com/Ezibenroc/PyRoaringBitMap>`_,
          creates a relation using the bitmap for the underlying set of entries;
        - if ``data`` is :obj:`None` (default), an empty relation is created.

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
        self = super().__new__(cls)
        self.__shape = shape
        self.__strides = Rel.__strides_from_shape(shape)
        if data is None:
            self.__data = BitMap64(data)
        elif isinstance(data, BitMap64):
            data = data.copy()
            full_bitmap = BitMap64()
            full_bitmap.add_range(0, total_size)
            if not data <= full_bitmap:
                raise ValueError("Data bitmap contains invalid entries.")
            self.__data = data
        elif isinstance(data, Rel):
            self.__data = data.__data.copy()
        else:
            # We can use __pack_entry here because it does not access the __data attr:
            packed_entries = [self.__pack_entry(entry) for entry in data]
            self.__data = BitMap64(packed_entries)
        return self

    @property
    def shape(self) -> tuple[int, ...]:
        """The shape of the relation, i.e. the tuple of sizes for its component sets."""
        return self.__shape

    def copy(self) -> "Rel":
        """Returns a copy of the relation (independently mutable)."""
        copy = super().__new__(Rel)
        copy.__shape = self.__shape
        copy.__strides = self.__strides
        copy.__data = self.__data.copy()
        return copy

    def validate_entry(self, entry: Entry) -> None:
        """
        Validates the given entry against the shape of the relation.

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
        """Adds the given entry to the relation."""
        idx = self.__pack_entry(entry)
        self.__data.add(idx)

    def remove(self, entry: Entry) -> None:
        """
        Removes the given entry from the relation.

        :raises KeyError: if the tuple is not in the relation.
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
        """
        idx = self.__pack_entry(entry)
        bitmap = self.__data
        if idx in bitmap:
            bitmap.remove(idx)
        else:
            bitmap.add(idx)

    def update(self, *entry_sets: Iterable[Entry]) -> None:
        """Adds all entries from all given iterables to the relation."""
        packed_entries = [
            self.__pack_entry(entry) for entry_set in entry_sets for entry in entry_set
        ]
        self.__data.update(packed_entries)

    def difference_update(self, *entry_sets: Iterable[Entry]) -> None:
        """Removes all entries from all given iterables from the relation."""
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
        flips.
        """
        packed_entries = [
            self.__pack_entry(entry) for entry_set in entry_sets for entry in entry_set
        ]
        update_bitset = BitMap64(packed_entries)
        self.__data.symmetric_difference_update(update_bitset)

    def __contains__(self, entry: Entry) -> bool:
        """
        Whether the given entry is in the relation.

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
        self.__data = self.__data.intersection(other.__data)
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
        self.__data = self.__data.union(other.__data)
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
        self.__data = self.__data.symmetric_difference(other.__data)
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
        self.__data = self.__data.difference(other.__data)
        return self

    def __eq__(self, other: Any) -> bool:
        """
        Equality comparison between relations, as sets of entries.

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

        :meta public:
        """
        if not isinstance(other, Rel):
            return NotImplemented
        if self.__shape != other.shape:
            raise ValueError("Comparison requires relations to have the same shape.")
        return self.__data <= other.__data

    def __repr__(self) -> str:
        return f"<Rel of shape {self.__shape} with {len(self)} entries>"

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
        instance = super().__new__(Rel)
        instance.__shape = self.__shape
        instance.__strides = self.__strides
        instance.__data = new_data
        return instance

    @staticmethod
    def __strides_from_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
        seq = (1,) + tuple(reversed(shape))[:-1]
        prod = 1
        strides: list[int] = []
        for x in seq:
            prod *= int(x)
            strides.append(prod)
        strides.reverse()
        return tuple(strides)
