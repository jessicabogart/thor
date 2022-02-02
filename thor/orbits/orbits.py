import uuid
import logging
import numpy as np
import pandas as pd
from copy import deepcopy
from astropy.time import Time
from ..utils import (
    Indexable,
    getHorizonsVectors
)
from ..coordinates import (
    CartesianCoordinates,
    KeplerianCoordinates,
    SphericalCoordinates,
    transform_coordinates
)
from .classification import calc_orbit_class

logger = logging.getLogger(__name__)

__all__ = [
    "Orbits",
    "FittedOrbits"
]


class Orbits(Indexable):

    def __init__(self,
            coordinates,
            ids=None,
            obj_ids=None,
            classes=None,
        ):

        self._cartesian = None
        self._spherical = None
        self._keplerian = None

        if isinstance(coordinates, CartesianCoordinates):
            self._cartesian = deepcopy(coordinates)
        elif isinstance(coordinates, SphericalCoordinates):
            self._spherical = deepcopy(coordinates)
        elif isinstance(coordinates, KeplerianCoordinates):
            self._keplerian = deepcopy(coordinates)
        else:
            err = (
                "coordinates should be one of:\n"
                "  CartesianCoordinates\n"
                "  SphericalCoordinates\n"
                "  KeplerianCoordinates\n"
            )
            raise TypeError(err)

        if ids is not None:
            self._ids = ids
        else:
            self._ids = np.array([uuid.uuid4().hex for i in range(len(coordinates))])

        if obj_ids is not None:
            self._obj_ids = obj_ids
        else:
            self._obj_ids = np.array(["None" for i in range(len(coordinates))])

        if classes is not None:
            self._classes = classes
        else:
            self._classes = None

        return

    def __len__(self):

        if self._cartesian is not None:
            N = len(self._cartesian)
        elif self._keplerian is not None:
            N = len(self._keplerian)
        else: # self._spherical is not None:
            N = len(self._spherical)

        return N

    @property
    def ids(self):
        return self._ids

    @property
    def obj_ids(self):
        return self._obj_ids

    @property
    def cartesian(self):

        if self._cartesian is None:

            if self._keplerian is not None:
                self._cartesian = transform_coordinates(self._keplerian, "cartesian")
            elif self._spherical is not None:
                self._cartesian = transform_coordinates(self._spherical, "cartesian")

        return self._cartesian

    @property
    def spherical(self):

        if self._spherical is None:

            if self._cartesian is not None:
                self._spherical = transform_coordinates(self._cartesian, "spherical")
            elif self._keplerian is not None:
                self._spherical = transform_coordinates(self._keplerian, "spherical")

        return self._spherical

    @property
    def keplerian(self):

        if self._keplerian is None:

            if self._cartesian is not None:
                self._keplerian = transform_coordinates(self._cartesian, "keplerian")
            elif self._spherical is not None:
                self._keplerian = transform_coordinates(self._spherical, "keplerian")

        return self._keplerian

    @property
    def classes(self):

        if self._classes is None:
            self._classes = calc_orbit_class(self.keplerian)

        return self._classes

    @classmethod
    def from_horizons(cls, ids, times):

        assert len(times) == 1

        vectors = getHorizonsVectors(
            ids,
            times,
            location="@sun",
            id_type="smallbody",
            aberrations="geometric",
        )

        coordinates = CartesianCoordinates(
            times=Time(
                vectors["datetime_jd"].values,
                scale="tdb",
                format="jd"
            ),
            x=vectors["x"].values,
            y=vectors["y"].values,
            z=vectors["z"].values,
            vx=vectors["vx"].values,
            vy=vectors["vy"].values,
            vz=vectors["vz"].values,
            origin="heliocenter",
            frame="ecliptic"
        )
        obj_ids = vectors["targetname"].values

        return cls(coordinates, obj_ids=obj_ids)

    def to_df(self,
            time_scale: str = "tdb",
            coordinate_type: str = "cartesian",
        ) -> pd.DataFrame:
        """
        Represent Orbits as a `~pandas.DataFrame`.

        Parameters
        ----------
        time_scale : {"tdb", "tt", "utc"}
            Desired timescale of the output MJDs.
        coordinate_type : {"cartesian", "spherical", "keplerian"}
            Desired output representation of the orbits.

        Returns
        -------
        df : `~pandas.DataFrame`
            Pandas DataFrame containing orbits.
        """
        if coordinate_type == "cartesian":
            df = self.cartesian.to_df(
                time_scale=time_scale
            )
        elif coordinate_type == "keplerian":
            df = self.keplerian.to_df(
                time_scale=time_scale
            )
        elif coordinate_type == "spherical":
            df = self.spherical.to_df(
                time_scale=time_scale
            )
        else:
            err = (
                "coordinate_type should be one of:\n"
                "  cartesian\n"
                "  spherical\n"
                "  keplerian\n"
            )
            raise ValueError(err)

        df.insert(0, "orbit_id", self.ids)
        df.insert(1, "obj_id", self.obj_ids)
        if self._classes is not None:
            df.insert(len(df.columns), "class", self.classes)

        return df

class FittedOrbits(Orbits):

    def __init__(self,
            coordinates,
            ids=None,
            obj_ids=None,
            members=None,
            num_obs=None,
            arc_length=None,
            chi2=None,
            rchi2=None,
        ):
        Orbits.__init__(
            self,
            coordinates=coordinates,
            ids=ids,
            obj_ids=obj_ids,
        )

        N = len(self)
        if members is None:
            self._members = [np.array([]) for i in range(N)]
        else:
            assert len(members) == N
            self._members = members

        if num_obs is None:
            self._num_obs = np.zeros(N, dtype=int)
        else:
            assert len(num_obs) == N
            self._num_obs = num_obs

        if arc_length is None:
            self._arc_length = np.zeros(N, dtype=float)
        else:
            assert len(arc_length) == N
            self._arc_length = arc_length

        if chi2 is None:
            self._chi2 = np.array([np.NaN for i in range(N)])
        else:
            assert len(chi2) == N
            self._chi2 = chi2

        if rchi2 is None:
            self._rchi2 = np.array([np.NaN for i in range(N)])
        else:
            assert len(rchi2) == N
            self._rchi2 = rchi2

        return

    @property
    def members(self):
        return self._members

    @property
    def num_obs(self):
        return self._num_obs

    @property
    def arc_length(self):
        return self._arc_length

    @property
    def chi2(self):
        return self._chi2

    @property
    def rchi2(self):
        return self._rchi2

    def to_df(self, time_scale="tdb", coordinate_type="cartesian"):

        df = Orbits.to_df(self,
            time_scale=time_scale,
            coordinate_type=coordinate_type
        )
        df.insert(len(df.columns), "num_obs", self.num_obs)
        df.insert(len(df.columns), "arc_length", self.arc_length)
        df.insert(len(df.columns), "chi2", self.chi2)
        df.insert(len(df.columns), "rchi2", self.rchi2)
        return df
