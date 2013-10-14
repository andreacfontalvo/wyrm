
"""Data type definitions.

This module provides the basic data types for Wyrm, like the
:class:`Data` and :class:`RingBuffer` classes.

"""


from __future__ import division

import copy
import logging

import numpy as np


logging.basicConfig(level=logging.NOTSET)
logger = logging.getLogger(__name__)


class Data(object):
    """Generic, self-describing data container.

    This data structure is very generic on purpose. The goal here was to
    provide something which can fit the various different known and yet
    unknown requirements for BCI algorithms.

    At the core of ``Data`` is its n-dimensional ``.data`` attribute
    which holds the actual data. Along with the data, there is meta
    information about each axis of the data, contained in ``.axes``,
    ``.names``, and ``.units``.

    Most toolbox methods rely on a *convention* how specific data should
    be structured (i.e. they assume that the channels are always in the
    last dimension). You don't have to follow this convention (or
    sometimes it might not even be possible when trying out new things),
    and all methods, provide an optional parameter to tell them on which
    axis they should work on.

    Continuous Data:
        Continuous Data is usually EEG data and consists of a 2d array
        ``[time, channel]``. Whenever you have continuous data, time and
        channel should be the last two dimensions.

    Epoched Data:
        Epoched data can be seen as an array of (non-epoched) data. The
        epoch should always be the first dimension. Most commonly used is
        epoched continuous EEG data which looks like this: ``[class,
        time, channel]``.

    Feature Vector:
        Similar to Epoched Data, with classes in the first dimension.

    A :func:`__eq__` function is providet to test for equality of two
    Data objects (via ``==``). This method only checks for the known
    attributes and does not guaranty correct result if the Data object
    contains custom attributes. It is mainly used in unittests.

    Parameters
    ----------
    data : ndarray
    axes : nlist of 1darrays
    names : nlist of strings
    units : nlist of strings

    Attributes
    ----------
    data : ndarray
        n-dimensional data array
    axes : nlist of 1darrays
        each element of corresponds to a dimension of ``.data`` (i.e.
        the first one in ``.axes`` to the first dimension in ``.data``
        and so on). The 1-dimensional arrays contain the description of
        the data along the appropriate axis in ``.data``. For example if
        ``.data`` contains Continuous Data, then ``.axes[0]`` should be
        an array of timesteps and ``.axes[1]`` an array of channel names
    names : nlist of strings
        the human readable description of each axis, like 'time', or 'channel'
    units : nlist of strings
        the human readable description of the unit used for the data in
        ``.axes``

    """
    def __init__(self, data, axes, names, units):
        """Initialize a new ``Data`` object.

        Upon initialization we check if ``axes``, ``names``, and
        ``units`` have the same length and if their respective length
        matches the shape of ``data``.

        Raises
        ------
        AssertionError
            if the lengths of the parameters are not correct.

        """
        assert data.ndim == len(axes) == len(names) == len(units)
        for i in range(data.ndim):
            if data.shape[i] != len(axes[i]):
                raise AssertionError("Axis '%s' (%i) not as long as corresponding axis in 'data' (%i)" % (names[i], len(axes[i]), data.shape[i]))
        self.data = data
        self.axes = [np.array(i) for i in axes]
        self.names = names
        self.units = units

    def __eq__(self, other):
        """Test for equality.

        Don't trust this method it only checks for known attributes and
        assumes equality if those are equal. This method is heavily used
        in unittests.

        Parameters
        ----------
        other : Data

        Returns
        -------
        equal : Boolean
            True if ``self`` and ``other`` are equal, False if not.

        """
        if (sorted(self.__dict__.keys()) == sorted(other.__dict__.keys()) and
            np.array_equal(self.data, other.data) and
            len(self.axes) == len(other.axes) and
            all([self.axes[i].shape == other.axes[i].shape for i in range(len(self.axes))]) and
            all([(self.axes[i] == other.axes[i]).all() for i in range(len(self.axes))]) and
            self.names == other.names and
            self.units == other.units
           ):
            return True
        return False

    def copy(self, **kwargs):
        """Return a memory efficient deep copy of ``self``.

        It first creates a shallow copy of ``self``, sets the attributes
        in ``kwargs`` if necessary and returns a deep copy of the
        resulting object.

        Parameters
        ----------
        kwargs : dict, optional
            if provided ``copy`` will try to overwrite the name, value
            pairs after the shallow- and before the deep copy. If no
            ``kwargs`` are provided, it will just return the deep copy.

        Returns
        -------
        dat : Data
            a deep copy of ``self``.

        Examples
        --------
        >>> # perform an ordinary deep copy of dat
        >>> dat2 = dat.copy()
        >>> # perform a deep copy but overwrite .axes first
        >>> dat.axes
        ['time', 'channels']
        >>> dat3 = dat.copy(axes=['foo'], ['bar'])
        >>> dat3.axes
        ['foo', 'bar']
        >>> dat.axes
        ['time', 'channel']

        """
        obj = copy.copy(self)
        for name, value in kwargs.items():
            setattr(obj, name, value)
        return copy.deepcopy(obj)


class RingBuffer(object):
    """Circular Buffer implementation.

    This implementation has a guaranteed upper bound for read and write
    operations as well as a constant memory usage, which is the size of
    the maximum length of the buffer in memory.

    Reading and writing will take at most the time it takes to copy a
    continuous chunk of length ``MAXLEN`` in memory. E.g. for the
    extreme case of storing the last 60 seconds of 64bit data, sampled
    with 1kHz and 128 channels (~60MB), reading a full buffer will take
    ~25ms, as well as writing when storing more than than 60 seconds at
    once. Writing will be usually much faster, as one stores usually
    only a few milliseconds of data per run. In that case writing will
    be a fraction of a millisecond.

    Parameters
    ----------
    length : int
        the length of the ring buffer in samples

    Attributes
    ----------
    length : int
        the length of the ring buffer in samples
    data : ndarray
        the contents of the ring buffer
    full : boolean
        indicates if the buffer has at least ``length`` elements stored
    idx : int
        the starting position of the oldest data in the ring buffer

    Examples
    --------

    >>> rb = RingBuffer(length)
    >>> while True:
    ...     rb.append(amp.get_data())
    ...     buffered = rb.get()
    ...     # do something with buffered


    """
    def __init__(self, length):
        """Initialize the Ringbuffer.

        Parameters
        ----------
        length : int
            the length of the data and maximum length of the buffer

        """
        # the maximum length of the ring buffer
        self.length = length
        self.data = None
        # indicate if the buffer write was wrapped around at least once
        self.full = False
        # the index where to insert new data (= the start of the oldest
        # data)
        self.idx = 0

    def append(self, data):
        """Append data to the Ringbuffer, overwriting old data if necessary.

        Parameters
        ----------
        data : ndarray

        Raises
        ------
        ValueError
            if the [1:]-dimensions (all but the first one) of ``data``
            does not match the ring buffer dimensions

        """
        # we have nothing to append
        if len(data) == 0:
            return
        # we append the first time, initialize .data with the correct
        # shape
        if self.data is None:
            buffershape = list(data.shape)
            buffershape[0] = self.length
            self.data = np.empty(buffershape)
        # incoming data is bigger than the buffer's capacity
        if len(data) > self.length:
            data = data[-self.length:]
        # we can write without wrapping around the buffer's end
        if self.idx + len(data) < self.length:
            self.data[self.idx:self.idx+len(data)] = data
            self.idx += len(data)
        # we will wrap around the buffer's end
        else:
            self.full = True
            l1 = self.length - self.idx
            l2 = len(data) - l1
            self.data[-l1:] = data[:l1]
            self.data[:l2] = data[l1:]
            self.idx = l2

    def get(self):
        """Get all buffered data.

        Returns
        -------
        data : ndarray
            the full contents of the ring buffer if the buffer is emtpy
            an empty ndarray is returned

        """
        # no data has ever been appended to this ringbuffer
        if self.data is None:
            return np.array([])
        # the ringbuffer wrapped around at least once
        if self.full:
            return np.concatenate([self.data[self.idx:], self.data[:self.idx]], axis=0)
        # the ringbuffer hansn't been filled completely yet
        else:
            return self.data[:self.idx].copy()

