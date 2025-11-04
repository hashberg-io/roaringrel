===============
Getting Started
===============

The :class:`~roaringrel.Rel` class implements a low-level mutable data structure to store a finite relation between finite sets:

    .. math::

        R \subseteq X_1 \times ... \times X_n

It presumes that the *component sets* :math:`X_1,...,X_n` are finite zero-based contiguous integer ranges, in the form :math:`X_j = \lbrace 0,...,s_j-1\rbrace`.
The tuple :math:`(s_1,...,s_n)` of component set sizes is referred to as the *shape* of the relation :math:`R`,
while the tuples :math:`(x_1,...x_n) \in R` are referred to as its *entries*.

Relations are implemented using 64-bit `roaring bitmaps <http://roaringbitmap.org/>`_ to store the underlying set of entries.

Install
=======

You can install the latest release from `PyPI <https://pypi.org/project/roaringrel/>`_ as follows:

.. code-block:: console

    $ pip install roaringrel

Usage
=====

All functionality of the library is accessible from the :class:`~roaringrel.Rel` class:

>>> from roaringrel import Rel

You can create a relation by specifying a shape for it, as a tuple of positive integers:

>>> Rel((2, 3, 4))
<Rel of shape (2, 3, 4) with 0 entries>

The code above creates a ternary relation :math:`R`, initially empty:

.. math::
    
    R \subseteq \lbrace 0, 1 \rbrace \times \lbrace 0, 1, 2 \rbrace \times \lbrace 0, 1, 2, 3 \rbrace


You can also specify initial entries for the relation at creation:

>>> Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1), (1, 2, 3)])
<Rel of shape (2, 3, 4) with 3 entries>

The code above creates a ternary relation :math:`R`, initially with the given three entries:

.. math::

    R = \lbrace (0,0,0), (1,1,1), (1,2, 3) \rbrace \subseteq \lbrace 0, 1 \rbrace \times \lbrace 0, 1, 2 \rbrace \times \lbrace 0, 1, 2, 3 \rbrace


Relations are sized iterable containers of entries:

>>> r = Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1), (1, 2, 3)])
>>> len(r)
3
>>> list(r)
[(0, 0, 0), (1, 1, 1), (1, 2, 3)]
>>> (0, 0, 0) in r
True

Relations support basic binary operators as sets of entries, restricted to operations having the same shape:

>>> a = Rel((2, 3, 4), [(0, 0, 0), (1, 2, 3)])
>>> b = Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1)])
>>> a&b # intersection
<Rel of shape (2, 3, 4) with 1 entries>
>>> list(a&b)
[(0, 0, 0)]
>>> a|b # union
<Rel of shape (2, 3, 4) with 3 entries>
>>> list(a|b)
>>> a^b # symmetric difference
<Rel of shape (2, 3, 4) with 2 entries>
>>> list(a^b)
[(1, 1, 1), (1, 2, 3)]
>>> a-b # difference
<Rel of shape (2, 3, 4) with 1 entries>
>>> list(a-b)
[(1, 2, 3)]

Relations support comparison as sets of entries, with subset comparison restricted to relations having the same shape:

>>> a == b # equality comparison
False
>>> a&b <= b # subset comparison
True
>>> a&b < b # strict subset comparison
True

Relations are mutable, with support for addition, removal and flipping of individual elements:

>>> a = Rel((2, 3, 4), [(0, 0, 0), (1, 2, 3)])
>>> a.add((1, 1, 1)) # add entry
>>> list(a)
[(0, 0, 0), (1, 1, 1), (1, 2, 3)]
>>> a.remove((1, 2, 3)) # remove entry
>>> list(a)
[(0, 0, 0), (1, 1, 1)]
>>> a.flip((0, 0, 0)) # flip on existing entry: remove
>>> list(a)
[(1, 1, 1)]
>>> a.flip((0, 0, 0)) # flip on missing entry: add
>>> list(a)
[(0, 0, 0), (1, 1, 1)]
>>> a.remove((1, 2, 3))
KeyError: (1, 2, 3)

The update operations enable addition, removal and flipping (symmetric difference) of multiple entries at once:

>>> a = Rel((2, 3, 4), [(0, 0, 0), (1, 2, 3)])
>>> a.update([(1, 1, 1), (1, 2, 2)]) # add multiple entries
>>> list(a)
[(0, 0, 0), (1, 1, 1), (1, 2, 2), (1, 2, 3)]
>>> a.difference_update([(0, 0, 0), (0, 1, 1)]) # remove multiple entries
>>> list(a)
[(1, 1, 1), (1, 2, 2), (1, 2, 3)]
>>> a.symmetric_difference_update([(1, 2, 3), (0, 1, 1)]) # flip multiple entries
>>> list(a)
[(0, 1, 1), (1, 1, 1), (1, 2, 2)]

Relations support inplace versions of the binary operation, mutating the lhs relation:

>>> a = Rel((2, 3, 4), [(0, 0, 0), (1, 2, 3)])
>>> b = Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1)])
>>> a ^= b
>>> list(a)
[(1, 1, 1), (1, 2, 3)]
>>> a &= b
>>> list(a)
[(1, 1, 1)]
>>> a |= b
>>> list(a)
[(0, 0, 0), (1, 1, 1)]
>>> a -= b
>>> list(a)
[]

The :meth:`~roaringrel.Rel.copy` method can be used to obtain an independently mutable copy of a relation:

>>> r = Rel((2, 3, 4), [(0, 0, 0), (1, 1, 1), (1, 2, 3)])
>>> s = r.copy()
>>> r == s
True
>>> list(r)
[(0, 0, 0), (1, 1, 1), (1, 2, 3)]
>>> list(s)
[(0, 0, 0), (1, 1, 1), (1, 2, 3)]
>>> r.remove((0, 0, 0))
>>> r == s
False
>>> list(r)
[(1, 1, 1), (1, 2, 3)]
>>> list(s)
[(0, 0, 0), (1, 1, 1), (1, 2, 3)]
