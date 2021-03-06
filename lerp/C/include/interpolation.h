/*

*/

#ifndef INTERPOLATION_H
#define INTERPOLATION_H

#include "Mesh.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ARRAYD64(a) (PyArrayObject*) PyArray_ContiguousFromAny(a, NPY_DOUBLE, 0, 0)


npy_intp evaluate_interpolation(Mesh_t mesh, const npy_double **params, npy_intp params_size,
                           NDTable_InterpMethod_t interp_method,
                           NDTable_ExtrapMethod_t extrap_method,
                           npy_double *result);

static PyObject *interpolation(PyObject *self, PyObject *args, PyObject *kwargs);


#ifdef __cplusplus
}
#endif

#endif
