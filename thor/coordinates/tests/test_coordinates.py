import pytest
import numpy as np
import numpy.testing as npt
from astropy.time import Time

from ..coordinates import _ingest_coordinate
from ..cartesian import CartesianCoordinates
from ..spherical import SphericalCoordinates

### Tests last updated: 2022-08-25

def test__ingest_coordinate():
    # Create 6 random arrays and test that
    # _ingest_coordinate correctly places these
    # arrays into the returned masked array
    N, D = 1000, 6

    coord_arrays = []
    for d in range(D):
        coord_arrays.append(np.random.rand(N))

    coords = None
    for d, q in enumerate(coord_arrays):
        coords = _ingest_coordinate(q, d, coords=coords)

    for d in range(D):
        npt.assert_equal(coords[:, d], coord_arrays[d])

    return


def test__ingest_coordinate_raises():
    # Create 2 random arrays of varying lengths
    # and test that _ingest_coordinate raises
    # a ValueError
    N1 = 500
    N2 = 501

    coord_arrays = []
    for d, n in enumerate([N1, N2]):
        coord_arrays.append(np.random.rand(n))

    coords = None
    for d, q in enumerate(coord_arrays):
        if d == 0:
            coords = _ingest_coordinate(q, d, coords=coords)
        else:
            with pytest.raises(ValueError):
                coords = _ingest_coordinate(q, d, coords=coords)

    return


def test__ingest_coordinate_masks():
    # Create 6 random arrays with varying NaN values
    # to represent missing measurements and test that
    # _ingest_coordinate correctly places these
    # arrays into the returned masked array
    N, D = 1000, 6

    coord_arrays = []
    mask_arrays = []
    for d in range(D):
        q = np.random.rand(N)
        inds = np.random.choice(np.arange(0, N), 50, replace=False)
        q[inds] = np.NaN
        mask = np.zeros(N, dtype=bool)
        mask[inds] = 1

        coord_arrays.append(q)
        mask_arrays.append(mask)

    coords = None
    for d, q in enumerate(coord_arrays):
        coords = _ingest_coordinate(q, d, coords=coords)

    for d in range(D):
        npt.assert_equal(coords[:, d], coord_arrays[d])
        npt.assert_equal(coords.mask[:, d], mask_arrays[d])

    return

def test_CartesianCoordinates_slicing():
    # Create Cartesian coordinates and test that slicing the CartesianCoordinates
    # objects preserves the coordinates themselves, their masks, and their filled
    # arrays and all their remaining slicable attributes
    N = 10
    data = {}
    for i, c in enumerate(["x", "y", "z", "vx", "vy", "vz"]):
        data[c] = np.arange(i * N, (i + 1)*N)

    data["times"] = Time(np.linspace(59000, 59000 + N, N), scale="utc", format="mjd")

    coords = CartesianCoordinates(**data)
    for s in [slice(0, N, 1), slice(2, 4, 1), slice(-5, -2, 1)]:
        # Test coordinate axes for each slice
        for i, c in enumerate(["x", "y", "z", "vx", "vy", "vz"]):
            npt.assert_equal(coords[s].values[:, i], coords.values[s, i])
            npt.assert_equal(coords[s].values.mask[:, i], coords.values.mask[s, i])
            npt.assert_equal(coords[s].values.filled()[:, i], coords.values.filled()[s, i])

        # Test times (which are astropy time objects)
        npt.assert_equal(coords[s].times.value, coords.times[s].value)

        # Test frames and origins are correct
        assert coords[s].frame == coords.frame
        assert np.all(coords[s].origin == coords.origin[0])

def test_SphericalCoordinates_slicing():
    # Create Spherical coordinates and test that slicing the SphericalCoordinates
    # objects preserves the coordinates themselves, their masks, and their filled
    # arrays and all their remaining slicable attributes
    N = 10
    data = {}
    for i, c in enumerate(["rho", "lon", "lat", "vrho", "vlon", "vlat"]):
        data[c] = np.arange(i * N, (i + 1)*N)

    data["times"] = Time(np.linspace(59000, 59000 + N, N), scale="utc", format="mjd")

    coords = SphericalCoordinates(**data)
    for s in [slice(0, N, 1), slice(2, 4, 1), slice(-5, -2, 1)]:
        # Test coordinate axes for each slice
        for i, c in enumerate(["rho", "lon", "lat", "vrho", "vlon", "vlat"]):
            npt.assert_equal(coords[s].values[:, i], coords.values[s, i])
            npt.assert_equal(coords[s].values.mask[:, i], coords.values.mask[s, i])
            npt.assert_equal(coords[s].values.filled()[:, i], coords.values.filled()[s, i])

        # Test times (which are astropy time objects)
        npt.assert_equal(coords[s].times.value, coords.times[s].value)

        # Test frames and origins are correct
        assert coords[s].frame == coords.frame
        assert np.all(coords[s].origin == coords.origin[0])