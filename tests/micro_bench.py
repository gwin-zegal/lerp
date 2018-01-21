# the inclusion of the tests module is not meant to offer best practices for
# testing in general, but rather to support the `find_packages` example in
# setup.py that excludes installing the "tests" package

from numpy import (random, array, arange, linspace, interp)
from lerp.mesh import Mesh
from time import time
import numpy as np
import pandas as pd

def tiny_bench():

    x = np.linspace(0, 2 * np.pi, 10)
    y = np.sin(x)

    m2d = Mesh(x,y)
    x = m2d.x.data
    y = m2d.data

    results = {}
    _range = np.arange(0,1_050_000, 50_000)

    for N in _range:
        _xi = np.random.randint(1, 10000, N).astype(np.float64) + np.random.random(N)
        _xi.sort()
        t1 = time()
        res1 = m2d.interpolation(_xi, interp='linear', extrap='hold')
        t2 = time()
        res2 = interp(_xi, x, y)
        t3 = time()
        results[N] = [t1, t2, t3]

    all_runs = pd.DataFrame(results) * 1000
    all_runs = all_runs.T.diff(axis=1).loc[:,1:]
    all_runs.columns = ["Mesh", "Numpy"]
    all_runs.index.name = "Interpolated array size"

    return all_runs

print("*"*80)
print("Tiny bench")
print("*"*80)
print(tiny_bench())
