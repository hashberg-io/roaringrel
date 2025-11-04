==========
RoaringRel
==========

.. image:: https://img.shields.io/badge/python-3.13+-green.svg
    :target: https://docs.python.org/3.13/
    :alt: Python versions

.. image:: https://img.shields.io/pypi/v/roaringrel.svg
    :target: https://pypi.python.org/pypi/roaringrel/
    :alt: PyPI version

.. image:: https://img.shields.io/pypi/status/roaringrel.svg
    :target: https://pypi.python.org/pypi/roaringrel/
    :alt: PyPI status

.. image:: http://www.mypy-lang.org/static/mypy_badge.svg
    :target: https://github.com/python/mypy
    :alt: Checked with Mypy

.. image:: https://readthedocs.org/projects/roaringrel/badge/?version=latest
    :target: https://roaringrel.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status


.. contents::

This library implements as low-level mutable data structure to store a finite relation between finite sets:

    .. math::

        R \subseteq X_1 \times ... \times X_n

It presumes that the *component sets* :math:`X_1,...,X_n` are finite zero-based contiguous integer ranges, in the form :math:`X_j = {0,...,s_j-1}`.
The tuple :math:`(s_1,...,s_n)` of component set sizes is referred to as the *shape* of the relation :math:`R`,
while the tuples :math:`(x_1,...x_n) \in R` are referred to as its *entries*.

Relations are implemented using a 64-bit `roaring bitmaps <http://roaringbitmap.org/>`_. to store the underlying set of entries.

Install
=======

You can install the latest release from `PyPI <https://pypi.org/project/roaringrel/>`_ as follows:

.. code-block:: console

    $ pip install roaringrel


Usage
=====

For an overview of library features and usage, see https://roaringrel.readthedocs.io/en/latest/getting-started.html


API
===

For the full API documentation, see https://roaringrel.readthedocs.io/


License
=======

`LGPLv3 © Hashberg. <LICENSE>`_
