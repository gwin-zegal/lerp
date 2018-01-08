# -*- coding: utf-8 -*-
"""
This module delivers utilities to manipulate data meshes

"""

import numpy as np
from lerp.intern import logger, myPlot
from lerp.core import path2so
from lerp.core.config import get_option

from functools import (partial, wraps)
import pickle
from xarray import DataArray

import xml.etree.ElementTree as ET

from numpy.ctypeslib import (ndpointer, load_library)
from ctypes import (c_void_p, c_int, c_double, cdll, byref, POINTER, Structure)
import ctypes
from enum import IntEnum

import sys
from os.path import (dirname, join as pjoin)
from copy import (copy, deepcopy)


# Base class for creating enumerated constants that are
# also subclasses of int
#
# http://www.chriskrycho.com/2015/ctypes-structures-and-dll-exports.html
# Option 1: set the _as_parameter value at construction.
# def __init__(self, value):
#    self._as_parameter = int(value)
#
# Option 2: define the class method `from_param`.
# @classmethod
# def from_param(cls, obj):
#    return int(obj)
class LookUpEnum(IntEnum):
    @classmethod
    def from_param(cls, obj):
        return int(obj)

INTERP_METH = LookUpEnum('INTERP_METH',
                         'hold nearest linear akima fritsch_butland steffen')
EXTRAP_METH = LookUpEnum('EXTRAP_METH',
                         'hold linear')



libNDTable = load_library('libNDTable', path2so)

MAX_NDIMS = 32
ARRAY_MAX_NDIMS = c_int * MAX_NDIMS
POINTER_TO_DOUBLE = ndpointer(dtype=np.float64, flags='C_CONTIGUOUS')
POINTER_TO_BP = POINTER_TO_DOUBLE * MAX_NDIMS

class NDTable_t(Structure):
    """
    Parameter : Mesh object
    """
    _fields_ = [("shape", c_int * MAX_NDIMS),
                ("strides", c_int * MAX_NDIMS),
                ("ndim", c_int),
                ("data", POINTER_TO_DOUBLE),
                ("size", c_int),
                ("itemsize", c_int),
                ("breakpoints", POINTER_TO_BP)]

    def __init__(self, *args, **kwargs):
        if 'data' in kwargs:
            _mesh = kwargs['data']
            data = _mesh.data.astype(np.float64)
            kwargs['data'] = data.ctypes.data_as(POINTER_TO_DOUBLE)
            kwargs['shape'] = ARRAY_MAX_NDIMS(*data.shape)
            kwargs['strides'] = ARRAY_MAX_NDIMS(*data.strides)
            kwargs['itemsize'] = data.itemsize
            kwargs['ndim'] = data.ndim
            kwargs['size'] = data.size
            kwargs['breakpoints'] = POINTER_TO_BP(*[np.asanyarray(getattr(_mesh, elt),
                                 dtype=np.float64, order='C').ctypes.data
                           for elt in _mesh.dims])

        super(NDTable_t, self).__init__(*args, **kwargs)

    @classmethod
    def from_param(cls, obj):
        return byref(obj)


# Note: recipe #15.1
# Python Cookbook, D. Beazley
# O'Reilly
# Define a special type for the 'double *' argument
# The important element is from_param
class DoubleArrayType:
    def from_param(self, param):
        typename = type(param).__name__
        if hasattr(self, 'from_' + typename):
            return getattr(self, 'from_' + typename)(param)
        elif isinstance(param, ctypes.Array):
            return param
        else:
            raise TypeError("Can't convert %s" % typename)

    # Cast from array.array objects
    def from_array(self, param):
        if param.typecode != 'd':
            raise TypeError('must be an array of doubles')
        ptr, _ = param.buffer_info()
        return ctypes.cast(ptr, ctypes.POINTER(ctypes.c_double))

    # Cast from lists/tuples
    def from_list(self, param):
        val = ((ctypes.c_double)*len(param))(*param)
        return val

    from_tuple = from_list

    # Cast from a numpy array
    def from_ndarray(self, param):
        return param.ctypes.data_as(ctypes.POINTER(ctypes.c_double))

################################################################################
# Import evaluate_interpolation
################################################################################
evaluate_interpolation = libNDTable.evaluate_interpolation
evaluate_interpolation.argtypes = [NDTable_t, c_void_p, c_int,
                            c_int, c_int, c_int, c_void_p]
evaluate_interpolation.restype = c_int

evaluate_derivative = libNDTable.evaluate_derivative
evaluate_derivative.argtypes = [NDTable_t, c_void_p, c_void_p, c_int,
                            c_int, c_int, c_int, c_void_p]
evaluate_derivative.restype = c_int


NDT_eval = libNDTable.NDT_eval
NDT_eval.argtypes = [NDTable_t, c_int, c_void_p,
                     c_int, c_int, c_void_p]
NDT_eval.restype = c_int


# def _derivate(data, points, deltas, interp, extrap):
#     values = np.empty(points[0].shape)
#     # params
#     params = (c_void_p * len(points))()
#     delta_params = (c_void_p * len(points))()
#
#     for i, param in enumerate(points):
#         params[i] = param.ctypes.get_as_parameter()
#     for i, delta in enumerate(deltas):
#         delta_params[i] = delta.ctypes.get_as_parameter()
#
#
#     res = _myEvaluateD(byref(NDTable_t(data=data)),
#                           params,
#                           c_int(len(params)),
#                           c_int(INTERP_METH[interp]),
#                           c_int(EXTRAP_METH[extrap]),
#                           c_int(values.size),
#                           values.ctypes.get_as_parameter(),
#                           delta_params
#                           )
#     assert res == 0, 'An error occurred during interpolation'
#
#     return values



class Mesh(DataArray):
    """
    # Code example

    from lerp.mesh import Mesh

    np.random.seed(123)
    m3d = Mesh(x=[1, 2, 3, 6], y=[13, 454, 645, 1233, 1535],
               data=np.random.randn(4, 5),
               label="le label")


   with plt.style.context('ggplot'):
        plt.figure(figsize=(16,9))
        m3d.plot()
        plt.graphpaper(200, 1)

    """
    AXES = 'xyzvw'
    def __init__(self, *pargs, **kwargs):

        self._options = {
            "extrapolate": True,
            "step": False,
            "deepcopy": False
        }

        if 'coords' in kwargs:
            assert not bool(set(kwargs) & set(kwargs['coords'])), \
                "Redundant arguments in coords and kwargs"

        self.label = kwargs.pop('label') if 'label' in kwargs else None
        self.unit = kwargs.pop('unit') if 'unit' in kwargs else None

        # Intern to DataArray
        # See https://github.com/pydata/xarray/blob/master/xarray/core/dataarray.py
        if 'fastpath' not in kwargs:
            if 'coords' not in kwargs:
                kwargs['coords']= {}

            if 'data' not in kwargs:
                kwargs['data'] = pargs[-1]
                pargs = pargs[:-1]

            for _k, _v in zip(self.AXES, pargs):
                kwargs['coords'][_k] = _v
                pargs = []

            dims = set(self.AXES) & set(kwargs)

            if dims:
                for d in sorted(dims, key=lambda x : self.AXES.index(x)):
                    kwargs['coords'][d] = kwargs.pop(d)

            kwargs['dims'] = tuple(kwargs['coords'].keys())

        super(Mesh, self).__init__(*pargs, **kwargs)

    @property
    def options(self):
        from lerp.util import DictWrapper
        return DictWrapper(self._options)

    def __call__(self, *pargs, **kwargs):
        """
        Interpolate the function.

        Parameters
        ----------
        x  : 1D array
            x-coordinates of the mesh on which to interpolate.
        y : 1D array
            y-coordinates of the mesh on which to interpolate.

        Returns
        -------
            2D array with shape (len(x), len(y))
            The interpolated values.
        """
        if self.options.step:
            kwargs.pop('interp', None)
            kwargs.pop('extrap', None)
            return self.interpolation(interp="hold", extrap='hold',
                                      *pargs, **kwargs)
        else:
            if self.options.extrapolate and 'extrap' not in kwargs:
                kwargs.pop('extrap', None)
                return self.interpolation(extrap='linear', *pargs, **kwargs)
            else:
                return self.interpolation(*pargs, **kwargs)

    def interpolation(self, *points, interp='linear', extrap='hold', **kwargs):
        """Interpolation
        """

        assert len(set(self.dims) & set(kwargs)) + len(points) == self.ndim, \
            "Not enough dimensions for interpolation"

        # First:
        #   - convert points (tuple) to list,
        #   - clean-up arguments in case: mix usage points/kwargs
        #   - create a clean argument dict
        points = list(points)

        args = {_x : kwargs[_x] if _x in kwargs else points.pop(0)
                for _x in self.dims}

        # Compute args dimensions and check compatibility without
        # broadcasting rules.
        dims = np.array([len(args[_k]) if "__len__" in dir(args[_k])
                         else 1 for _k in args])
        assert all((dims == max(dims)) + (dims == 1)), "problème"

        _s = max(dims)

        args = [np.asarray(args[_x], np.float64)
                if "__len__" in dir(args[_x])
                else np.ones((max(dims),), np.float64) * args[_x]
                for _x in self.dims]

        # print([np.broadcast_to(np.ravel([args[_x]]), (_s,))

        values = np.empty(args[0].shape)

        c_params_p = c_void_p * len(self.dims)

        res = evaluate_interpolation(NDTable_t(data=self),
                            c_params_p(*[_a.ctypes.get_as_parameter()
                                           for _a in args]),
                              c_int(self.ndim),
                              INTERP_METH[interp],
                              EXTRAP_METH[extrap],
                              c_int(values.size),
                              values.ctypes.get_as_parameter()
                              )
        assert res == 0, 'An error occurred during interpolation'

        return values[0] if len(values) == 1 else values


    def derivate(self, *points, interp='linear', extrap='hold', **kwargs):
        """derivate
        """

        assert len(set(self.dims) & set(kwargs)) + len(points) == self.ndim, \
            "Not enough dimensions for interpolation"

        # First:
        #   - convert points (tuple) to list,
        #   - clean-up arguments in case: mix usage points/kwargs
        #   - create a clean argument dict
        points = list(points)

        args = {_x : kwargs[_x] if _x in kwargs else points.pop(0)
                for _x in self.dims}

        # Compute args dimensions and check compatibility without
        # broadcasting rules.
        dims = np.array([len(args[_k]) if "__len__" in dir(args[_k])
                         else 1 for _k in args])
        assert all((dims == max(dims)) + (dims == 1)), "problème"

        _s = max(dims)

        args = [np.asarray(args[_x], np.float64)
                if "__len__" in dir(args[_x])
                else np.ones((max(dims),), np.float64) * args[_x]
                for _x in self.dims]

        dxi = [np.ones_like(_x) for _x in args]

        # print(args)
        # print([np.broadcast_to(np.ravel([args[_x]]), (_s,))

        values = np.empty(args[0].shape)

        c_params_p = c_void_p * len(self.dims)

        res = evaluate_derivative(NDTable_t(data=self),
                              c_params_p(*[_a.ctypes.get_as_parameter()
                                           for _a in args]),
                              c_params_p(*[_a.ctypes.get_as_parameter()
                                           for _a in dxi]),
                              c_int(self.ndim),
                              INTERP_METH[interp],
                              EXTRAP_METH[extrap],
                              c_int(values.size),
                              values.ctypes.get_as_parameter()
                              )
        assert res == 0, 'An error occurred during interpolation'

        return values[0] if len(values) == 1 else values



    def interpolation_NDT_eval(self, *points,
                               interp='linear', extrap='hold', **kwargs):
        """Interpolation
        """

        assert len(set(self.dims) & set(kwargs)) + len(points) == self.ndim, \
            "Not enough dimensions for interpolation"

        # First:
        #   - convert points (tuple) to list,
        #   - clean-up arguments in case: mix usage points/kwargs
        #   - create a clean argument dict
        points = list(points)

        args = {_x : kwargs[_x] if _x in kwargs else points.pop(0)
                for _x in self.dims}

        # Compute args dimensions and check compatibility without
        # broadcasting rules.
        dims = np.array([len(args[_k]) if "__len__" in dir(args[_k])
                         else 1 for _k in args])
        assert all((dims == max(dims)) + (dims == 1)), "problème"

        _s = max(dims)

        args = [np.asarray(args[_x], np.float64)
                if "__len__" in dir(args[_x])
                else np.ones((max(dims),), np.float64) * args[_x]
                for _x in self.dims]

        # print([np.broadcast_to(np.ravel([args[_x]]), (_s,))

        values = np.empty(args[0].shape)
        value = c_double()

        params = np.empty(len(args))

        for index in np.ndindex(values.shape):
            for i, point in enumerate(args):
                params[i] = point[index]

            NDT_eval(NDTable_t(data=self),
                     c_int(self.ndim),
                     params.ctypes.get_as_parameter(),
                     INTERP_METH[interp],
                     EXTRAP_METH[extrap],
                      byref(value))
            values[index] = value.value

        #assert res == 0, 'An error occurred during interpolation'

        return values[0] if len(values) == 1 else values


    def resample(self, *points, interp='linear', extrap='hold', **kwargs):

        # First:
        #   - convert points (tuple) to list,
        #   - clean-up arguments in case: mix usage points/kwargs
        #   - create a clean argument dict

        points = list(points)
        args = {}
        for d in self.dims:
            if d in kwargs:
                args[d] = kwargs[d]
            else:
                try:
                    args[d] = points.pop(0)
                except IndexError:
                    args[d] = self.coords[d]

        mg = np.meshgrid(*args.values(), indexing='ij')
        #return args
        nv = self.interpolation(*mg, interp=interp, extrap=extrap)
        return Mesh(nv, **args)

    # Plot MAP as PDF in filename
    def plot(self, xy=False, filename=None, **kwargs):

        import matplotlib.pyplot as plt

        assert self.ndim <= 2, "More that two dimensions"

        if self.label is None:
            self.label = ""
        if self.unit is None:
            self.unit = ""

        x_axis = self.coords[self.dims[0]]
        y_axis = self.coords[self.dims[1]] if self.ndim > 1 else None

        plt.xlabel(f"{x_axis.label} [{x_axis.unit}]"
                   if x_axis.label is not None else "Label []")
        plt.ylabel(self.label + ' [' + self.unit + ']')

        if y_axis is not None:
            for _i, _y in enumerate(y_axis.data):
                # print("plot {}".format(_x))
                plt.plot(x_axis.data,
                         self.data.take(_i, axis=1),
                         '-', linewidth=1, label=f"{_y} {y_axis.unit}",
                         **kwargs)

        else:
            plt.plot(x_axis.data, self.data, '-', linewidth=1,
                     label=f"{x_axis.unit}", **kwargs)

        plt.legend(loc=2, borderaxespad=0., frameon=0)

        if filename is not None:
            print("Save file as " + filename)
            plt.savefig(filename, bbox_inches='tight')


# cdef struct ndtable:
#     int shape[MAX_NDIMS]
#     int ndim


#	int 	shape[MAX_NDIMS]    # Array of data array dimensions.
#	int 	strides[MAX_NDIMS]  # bytes to step in each dimension when
								# traversing an array.
#	int		ndim			    # Number of array dimensions.
#	double *data			    # Buffer object pointing to the start
								# of the array’s data.
#	int		size			    # Number of elements in the array.
#	int     itemsize		    # Length of one array element in bytes.
#	double *breakpoints[MAX_NDIMS]  # array of pointers to the scale values
