import numpy as np
from astropy.time import Time
from astropy import units as u
from typing import (
    List,
    Optional,
    Union
)
from ..utils import (
    Indexable
)

__all__ = [
    "_ingest_coordinate",
    "_ingest_covariance",
    "Coordinates",
]

def _ingest_coordinate(
        q: Union[list, np.ndarray],
        d: int,
        coords: Optional[np.ma.core.MaskedArray] = None
    ) -> np.ma.core.MaskedArray:
    """
    Ingest coordinates along an axis (like the x, y, z) and add them to an existing masked array
    of coordinate measurements if that object already exists. If that object doesn't exist then
    create it and return it. Any missing values in q should be represented with NaNs.

    Parameters
    ----------
    q : list or `~numpy.ndarray` (N)
        List or 1-D array of coordinate measurements.
    d : int
        The coordinate axis (as an index). For example, for a 6D Cartesian
        state vector, the x-axis takes the 0th index, the y-axis takes the 1st index,
        the z axis takes the 2nd index, the x-velocity takes the 3rd index, etc..
    coords : `~numpy.ma.ndarray` (N, D), optional
        If coordinates (ie, other axes) have already been defined then pass them here
        so that current axis of coordinates can be added.

    Returns
    -------
    coords : `~numpy.ma.array` (N, 6)
        Masked array of 6D coordinate measurements with q measurements ingested.

    Raises
    ------
    ValueError
        If the length of q doesn't match the length of coords.
    """
    if q is not None:
        q_ = np.asarray(q)
        N_ = len(q_)
        if coords is None:
            coords = np.ma.zeros((N_, 6), dtype=np.float64, fill_value=np.NaN)
            coords.mask = 1
        else:
            N, D = coords.shape
            if N != N_:
                err = (
                    "q needs to be the same length as the existing coordinates.\n"
                    f"q has length {N_} while coords has {N} coordinates in 6 dimensions."
                )
                raise ValueError(err)

        coords[:, d] = q_
        coords.mask[:, d] = np.where(np.isnan(q_), 1, 0)

    return coords

def _ingest_covariance(
        coords: np.ma.core.MaskedArray,
        covariance: Union[np.ndarray, np.ma.core.MaskedArray],
    ) -> np.ma.core.MaskedArray:
    """
    Ingest a set of covariance matrices.

    Parameters
    ----------
    coords : `~numpy.ma.array` (N, 6)
        Masked array of 6D coordinate measurements with q measurements ingested.
    covariance : `~numpy.ndarray` or `~numpy.ma.array` (N, <=6, <=6)
        Covariance matrices for each coordinate. These matrices may have fewer dimensions
        than 6. If so, additional dimensions will be added for each masked or missing coordinate
        dimension.

    Returns
    -------
    covariance : `~numpy.ma.array` (N, 6, 6)
        Masked array of covariance matrices.

    Raises
    ------
    ValueError
        If not every coordinate has an associated covariance.
        If the number of covariance dimensions does not match
            the number of unmasked or missing coordinate dimensions.
    """
    axes = coords.shape[1] - np.sum(coords.mask.all(axis=0))
    if covariance.shape[0] != len(coords):
        err = (
            "Every coordinate in coords should have an associated covariance."
        )
        raise ValueError(err)

    if covariance.shape[1] != covariance.shape[2] != axes:
        err = (
            f"Coordinates have {axes} defined dimensions, expected covariance matrix\n",
            f"shapes of (N, {axes}, {axes}."
        )
        raise ValueError(err)

    if isinstance(covariance, np.ma.core.MaskedArray) and (covariance.shape[1] == covariance.shape[2] == coords.shape[1]):
        return covariance

    covariance_ = np.ma.zeros((len(coords), 6, 6), dtype=np.float64, fill_value=np.NaN)
    covariance_.mask = np.zeros_like(covariance_, dtype=bool)

    for n in range(len(coords)):
        covariance_[n].mask[coords[n].mask, :] = 1
        covariance_[n].mask[:, coords[n].mask] = 1
        covariance_[n][~covariance_[n].mask] = covariance[n].flatten()

    return covariance_

class Coordinates(Indexable):

    def __init__(
            self,
            *args,
            covariances: Optional[Union[np.ndarray, np.ma.array]] = None,
            times: Optional[Time] = None,
            origin: str = "heliocentric",
            frame: str = "ecliptic",
            names: List[str] = [],
        ):
        coords = None
        for d, q in enumerate(args):
            coords = _ingest_coordinate(q, d, coords)

        self._times = times
        self._coords = coords
        self._origin = origin
        self._frame = frame
        self._names = names

        if covariances is not None:
            self._covariances = _ingest_covariance(coords, covariances)
        else:
            self._covariances = None
        return

    def __len__(self):
        return len(self.coords)

    @property
    def times(self):
        return self._times

    @property
    def coords(self):
        return self._coords

    @property
    def covariances(self):
        return self._covariances

    @property
    def origin(self):
        return self._origin

    @property
    def frame(self):
        return self._frame

    @property
    def names(self):
        return self._names

    def to_cartesian(self):
        raise NotImplementedError

    @classmethod
    def from_cartesian(cls, cartesian):
        raise NotImplementedError