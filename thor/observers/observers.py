import numpy as np
import pandas as pd
from typing import (
    List,
    Optional,
    Union
)
from astropy.time import Time
from collections import OrderedDict

from ..utils.indexable import Indexable
from ..utils.astropy import times_from_df
from ..coordinates.coordinates import Coordinates
from ..coordinates.cartesian import CartesianCoordinates
from ..coordinates.members import CoordinateMembers
from .state import get_observer_state

OBSERVER_CARTESIAN_COLS = OrderedDict()
OBSERVER_CARTESIAN_COLS["x"] = "obs_x"
OBSERVER_CARTESIAN_COLS["y"] = "obs_y"
OBSERVER_CARTESIAN_COLS["z"] = "obs_z"
OBSERVER_CARTESIAN_COLS["vx"] = "obs_vx"
OBSERVER_CARTESIAN_COLS["vy"] = "obs_vy"
OBSERVER_CARTESIAN_COLS["vz"] = "obs_vz"

class Observers(CoordinateMembers):
    """
    Observers

    Stores observation times and coordinates for observers.

    Observers can be defined in the following ways:
    observers = Observers(["I11"], times=observation_times)
    observers = Observers(["I11", "I41"], times=observation_times)
    observers = Observers(["I11", "I41"], times=[observation_times_I11, observation_times_I41])

    """
    def __init__(self,
        codes: List,
        times: Optional[Union[Time, List]] = None,
        coordinates: Optional[Coordinates] = None
    ):

        if isinstance(coordinates, Coordinates) and times is not None:
            if coordinates.times is not None:
                try:
                    np.testing.assert_equal(coordinates.times.tdb.mjd, times.tdb.mjd)
                except AssertionError as e:
                    err = (
                        "Coordinates times do not match the given times."
                    )
                    raise ValueError(err)
            else:
                if isinstance(times, Time):
                    assert len(times) == len(coordinates)
                    coordinates._times = times

        CoordinateMembers.__init__(self,
            coordinates=coordinates,
            cartesian=True,
            spherical=False,
            keplerian=False,
            cometary=False
        )

        # Case 1: codes and times are both a list -- each observatory code
        # has a list of unique observation times.
        if isinstance(codes, list) and isinstance(times, list):
            assert len(codes) == len(times)
            self._codes = np.array([c for c, t in zip(codes, times) for ti in t])
            self._times = Time(np.concatenate(times))

        # Case 2: codes is a list but times is a an astropy time object -- each observatory code
        # shares the same observation times (useful for testing).
        elif isinstance(codes, list) and isinstance(times, Time):
            self._codes = np.array([c for c in codes for i in range(len(times))])
            self._times = Time(
                np.concatenate([times for i in range(len(codes))])
            )

        # Case 3: codes is a numpy array and times is an astropy time object -- each observation time
        # has a corresponding observatory code (these codes can be duplicated)
        elif isinstance(codes, np.ndarray) and isinstance(times, Time):
            self._codes = codes
            self._times = times

        assert len(self._codes) == len(self._times)
        if self._cartesian is not None:
            assert len(self._codes) == len(self._cartesian)

        # Sort by observation times and then by observatory codes
        sorted_ind = np.lexsort((self._codes, self._times.mjd))
        self._times = self._times[sorted_ind]
        self._codes = self._codes[sorted_ind]
        if self._cartesian is not None:
            self._cartesian = self._cartesian[sorted_ind]

        index = np.arange(0, len(self._codes), 1)
        Indexable.__init__(self, index)
        return

    def iterate_unique(self):
        """
        Yield unique observatory codes and their coresponding
        unique observation times.

        Yield
        -----
        code : str
            MPC observatory code
        times : `~astropy.time.core.Time`
            Observation times for the specific observatory.
        """
        unique_code = np.unique(self.codes)
        for code in unique_code:
            times = Time(
                np.unique(self._times.mjd[np.where(self.codes == code)]),
                scale=self._times.scale,
                format="mjd"
            )
            yield code, times

    @property
    def codes(self):
        return self._codes

    @property
    def times(self):
        return self._times

    @property
    def cartesian(self):

        if self._cartesian is None:

            # Get observatory states for each unique observatory code
            # and their corresponding unique observation times
            codes = []
            unique_states = []
            for code, times in self.iterate_unique():
                codes_i, states_i = get_observer_state(
                    [code],
                    times,
                    origin="heliocenter",
                    frame="ecliptic"
                )
                codes.append(codes_i)
                unique_states.append(states_i)

            codes = np.hstack(codes)
            unique_states = np.vstack(unique_states)

            # Duplicate unique observer states for each repeated observation time
            # using pandas merge (significantly easier and faster than iterating over a numpy
            # array using a for loop and np.where)
            # TODO: evaluate https://stackoverflow.com/questions/49495344/numpy-equivalent-of-merge
            # as a potential alternative
            unique_states_df = pd.DataFrame({
                "observatory_code" : codes,
                "mjd_utc" : unique_states[:, 0],
                "x" : unique_states[:, 1],
                "y" : unique_states[:, 2],
                "z" : unique_states[:, 3],
                "vx" : unique_states[:, 4],
                "vy" : unique_states[:, 5],
                "vz" : unique_states[:, 6],
                })
            states_df = pd.DataFrame({
                "observatory_code" : self.codes,
                "mjd_utc" : self.times.utc.mjd,
                })
            states_df = states_df.merge(unique_states_df, on=["observatory_code", "mjd_utc"])
            states_df.sort_values(
                by=["mjd_utc", "observatory_code"],
                inplace=True
            )

            cartesian = CartesianCoordinates(
                times=Time(
                    states_df["mjd_utc"].values,
                    scale="utc",
                    format="mjd"
                ),
                x=states_df["x"].values,
                y=states_df["y"].values,
                z=states_df["z"].values,
                vx=states_df["vx"].values,
                vy=states_df["vy"].values,
                vz=states_df["vz"].values,
                origin="heliocenter",
                frame="ecliptic"
            )
            self._cartesian = cartesian
            self.default_coordinate_type = "cartesian"

        return self._cartesian

    def to_df(self,
            time_scale: str = "utc"
        ) -> pd.DataFrame:
        """
        Represent Observers as a `~pandas.DataFrame`.

        Parameters
        ----------
        time_scale : {"tdb", "tt", "utc"}
            Desired timescale of the output MJDs.

        Returns
        -------
        df : `~pandas.DataFrame`
            Pandas DataFrame containing observers.
        """
        df = CoordinateMembers.to_df(
            self,
            time_scale=time_scale,
            coordinate_type="cartesian"
        )
        obs_cols = {col : f"obs_{col}" for col in df.columns[1:]}
        df.insert(1, "observatory_code", self.codes)
        df.rename(columns=obs_cols, inplace=True)
        return df

    @classmethod
    def from_df(cls,
            df: pd.DataFrame,
            coord_cols: OrderedDict = OBSERVER_CARTESIAN_COLS,
            origin_col: str = "obs_origin",
            frame_col: str = "obs_frame"
        ) -> "Observers":
        """
        Create a Observers class from a DataFrame.

        Parameters
        ----------
        df : `~pandas.DataFrame`
            Pandas DataFrame containing Observers.
        coord_cols : OrderedDict
            Ordered dictionary containing the coordinate dimensions as keys and their equivalent columns
            as values. For example,
                coord_cols = OrderedDict()
                coord_cols["x"] = Column name of x distance values
                coord_cols["y"] = Column name of y distance values
                coord_cols["z"] = Column name of z distance values
                coord_cols["vx"] = Column name of x velocity values
                coord_cols["vy"] = Column name of y velocity values
                coord_cols["vz"] = Column name of z velocity values
        origin_col : str
            Name of the column containing the origin of each coordinate.
        frame_col : str
            Name of the column containing the coordinate frame.
        """
        data = {}
        data["codes"] = df["observatory_code"].values
        data["times"] = times_from_df(df)
        data["coordinates"] = cls._dict_from_df(
            df,
            cartesian=True,
            keplerian=False,
            cometary=False,
            spherical=False,
            coord_cols=coord_cols,
            origin_col=origin_col,
            frame_col=frame_col
        )["coordinates"]

        return cls(**data)

    @classmethod
    def from_observations_coordinates(cls,
            coords: Coordinates
        ) -> "Observers":
        """
        Instantiate an Observers class from observation coordinates. This
        assumes the origin and times have been correctly defined in the
        observations coordinates.

        Parameters
        ----------
        coords : `~thor.coordinates.coordinates.Coordinates`
            Observation coordinates.

        Returns
        -------
        observers : `~thor.observers.observers.Observers`
            Observers class.
        """
        data = {}
        data["codes"] = coords.origin
        data["times"] = coords.times
        return cls(**data)