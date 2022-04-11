import numpy as np
import jax.numpy as jnp
from jax import (
    config,
    jit
)
from jax.experimental import loops
from astropy.time import Time
from astropy import units as u
from typing import (
    List,
    Optional,
    Union
)
from collections import OrderedDict

config.update("jax_enable_x64", True)
config.update('jax_platform_name', 'cpu')

from ..constants import Constants as c
from .coordinates import Coordinates
from .cartesian import CartesianCoordinates
from .keplerian import (
    _cartesian_to_keplerian,
    _keplerian_to_cartesian
)
from .covariances import transform_covariances_jacobian

__all__ = [
    "_cartesian_to_cometary",
    "cartesian_to_cometary",
    "_cometary_to_cartesian",
    "cometary_to_cartesian",
    "CometaryCoordinates"
]

COMETARY_COLS = OrderedDict()
COMETARY_UNITS = OrderedDict()
for i in ["q", "e", "i", "raan", "ap", "tp"]:
    COMETARY_COLS[i] = i
COMETARY_UNITS["q"] = u.au
COMETARY_UNITS["e"] = u.dimensionless_unscaled
COMETARY_UNITS["i"] = u.deg
COMETARY_UNITS["raan"] = u.deg
COMETARY_UNITS["ap"] = u.deg
COMETARY_UNITS["tp"] = u.d

MU = c.MU
Z_AXIS = jnp.array([0., 0., 1.])

@jit
def _cartesian_to_cometary(
        coords_cartesian: Union[np.ndarray, jnp.ndarray],
        t0: float,
        mu: float = MU,
    ) -> jnp.ndarray:
    """
    Convert Cartesian coordinates to Cometary coordinates.

    Parameters
    ----------
    coords_cartesian : {`~numpy.ndarray`, `~jax.numpy.ndarray`} (6)
        3D Cartesian coordinate including time derivatives.
        x : x-position in units of au.
        y : y-position in units of au.
        z : z-position in units of au.
        vx : x-velocity in units of au per day.
        vy : y-velocity in units of au per day.
        vz : z-velocity in units of au per day.
    t0 : float (1)
        Epoch at which cometary elements are defined in MJD TDB.
    mu : float, optional
        Gravitational parameter (GM) of the attracting body in units of
        au**3 / d**2.

    Returns
    -------
    coords_cometary : `~jax.numpy.ndarray` (6)
        6D Cometary coordinate.
        q : periapsis distance in au.
        e : eccentricity.
        i : inclination in degrees.
        raan : Right ascension (longitude) of the ascending node in degrees.
        ap : argument of periapsis in degrees.
        tp : time of periapse passage in days.
    """
    coords_cometary = _cartesian_to_keplerian(coords_cartesian, t0, mu=mu)
    return coords_cometary[jnp.array([1, 2, 3, 4, 5, -1])]

@jit
def cartesian_to_cometary(
        coords_cartesian: Union[np.ndarray, jnp.ndarray],
        t0: Union[np.ndarray, jnp.ndarray],
        mu: float = MU,
    ) -> jnp.ndarray:
    """
    Convert Cartesian coordinates to Keplerian coordinates.

    Parameters
    ----------
    coords_cartesian : {`~numpy.ndarray`, `~jax.numpy.ndarray`} (N, 6)
        3D Cartesian coordinates including time derivatives.
        x : x-position in units of au.
        y : y-position in units of au.
        z : z-position in units of au.
        vx : x-velocity in units of au per day.
        vy : y-velocity in units of au per day.
        vz : z-velocity in units of au per day.
    t0 : {`~numpy.ndarray`, `~jax.numpy.ndarray`} (N)
        Epoch at which cometary elements are defined in MJD TDB.
    mu : float, optional
        Gravitational parameter (GM) of the attracting body in units of
        au**3 / d**2.

    Returns
    -------
    coords_cometary : `~jax.numpy.ndarray` (N, 6)
        6D Cometary coordinates.
        q : periapsis distance in au.
        e : eccentricity.
        i : inclination in degrees.
        raan : Right ascension (longitude) of the ascending node in degrees.
        ap : argument of periapsis in degrees.
        tp : time of periapse passage in days.
    """
    with loops.Scope() as s:
        N = len(coords_cartesian)
        s.arr = jnp.zeros((N, 6), dtype=jnp.float64)

        for i in s.range(s.arr.shape[0]):
            s.arr = s.arr.at[i].set(
                _cartesian_to_cometary(
                    coords_cartesian[i],
                    t0[i],
                    mu=mu
                )
            )

        coords_cometary = s.arr

    return coords_cometary

@jit
def _cometary_to_cartesian(
        coords_cometary: Union[np.ndarray, jnp.ndarray],
        t0: float,
        mu: float = MU,
        max_iter: int = 100,
        tol: float = 1e-15
    ) -> jnp.ndarray:
    """
    Convert a single Cometary coordinate to a Cartesian coordinate.

    Parameters
    ----------
    coords_cometary : {`~numpy.ndarray`, `~jax.numpy.ndarray`} (6)
        6D Cometary coordinate.
        q : periapsis distance in au.
        e : eccentricity.
        i : inclination in degrees.
        raan : Right ascension (longitude) of the ascending node in degrees.
        ap : argument of periapsis in degrees.
        tp : time of periapse passage in days.
    t0 : float (1)
        Epoch at which cometary elements are defined in MJD TDB.
    mu : float, optional
        Gravitational parameter (GM) of the attracting body in units of
        au**3 / d**2.
    max_iter : int, optional
        Maximum number of iterations over which to converge. If number of iterations is
        exceeded, will use the value of the relevant anomaly at the last iteration.
    tol : float, optional
        Numerical tolerance to which to compute anomalies using the Newtown-Raphson
        method.

    Returns
    -------
    coords_cartesian : `~jax.numpy.ndarray` (6)
        3D Cartesian coordinate including time derivatives.
        x : x-position in units of au.
        y : y-position in units of au.
        z : z-position in units of au.
        vx : x-velocity in units of au per day.
        vy : y-velocity in units of au per day.
        vz : z-velocity in units of au per day.
    """
    coords_keplerian = jnp.zeros(6, dtype=jnp.float64)

    q = coords_cometary[0]
    e = coords_cometary[1]
    i = coords_cometary[2]
    raan = coords_cometary[3]
    ap = coords_cometary[4]
    tp = coords_cometary[5]
    a = q / (1 - e)

    n = jnp.sqrt(mu / jnp.abs(a)**3)
    P = 2*jnp.pi / n
    dtp = tp - t0
    M = jnp.where(dtp < 0, 2*jnp.pi * -dtp / P, 2 * jnp.pi * (P - dtp) / P)
    M = jnp.degrees(M)

    coords_keplerian = coords_keplerian.at[0].set(a)
    coords_keplerian = coords_keplerian.at[1].set(e)
    coords_keplerian = coords_keplerian.at[2].set(i)
    coords_keplerian = coords_keplerian.at[3].set(raan)
    coords_keplerian = coords_keplerian.at[4].set(ap)
    coords_keplerian = coords_keplerian.at[5].set(M)

    coords_cartesian = _keplerian_to_cartesian(
        coords_keplerian,
        mu=mu,
        max_iter=max_iter,
        tol=tol
    )

    return coords_cartesian

@jit
def cometary_to_cartesian(
        coords_cometary: Union[np.ndarray, jnp.ndarray],
        t0: Union[np.ndarray, jnp.ndarray],
        mu: float = MU,
        max_iter: int = 100,
        tol: float = 1e-15
    ) -> jnp.ndarray:
    """
    Convert Cometary coordinates to Cartesian coordinates.

    Parameters
    ----------
    coords_cometary : {`~numpy.ndarray`, `~jax.numpy.ndarray`} (N, 6)
        6D Cometary coordinate.
        q : periapsis distance in au.
        e : eccentricity.
        i : inclination in degrees.
        raan : Right ascension (longitude) of the ascending node in degrees.
        ap : argument of periapsis in degrees.
        tp : time of periapse passage in days.
    t0 : {`~numpy.ndarray`, `~jax.numpy.ndarray`} (N)
        Epoch at which cometary elements are defined in MJD TDB.
    mu : float, optional
        Gravitational parameter (GM) of the attracting body in units of
        au**3 / d**2.
    max_iter : int, optional
        Maximum number of iterations over which to converge. If number of iterations is
        exceeded, will use the value of the relevant anomaly at the last iteration.
    tol : float, optional
        Numerical tolerance to which to compute anomalies using the Newtown-Raphson
        method.

    Returns
    -------
    coords_cartesian : `~jax.numpy.ndarray` (N, 6)
        3D Cartesian coordinates including time derivatives.
        x : x-position in units of au.
        y : y-position in units of au.
        z : z-position in units of au.
        vx : x-velocity in units of au per day.
        vy : y-velocity in units of au per day.
        vz : z-velocity in units of au per day.
    """
    with loops.Scope() as s:
        N = len(coords_cometary)
        s.arr = jnp.zeros((N, 6), dtype=jnp.float64)

        for i in s.range(s.arr.shape[0]):
            s.arr = s.arr.at[i].set(
                _cometary_to_cartesian(
                    coords_cometary[i],
                    t0=t0[i],
                    mu=mu,
                    max_iter=max_iter,
                    tol=tol
                )
            )

        coords_cartesian = s.arr

    return coords_cartesian


class CometaryCoordinates(Coordinates):

    def __init__(
            self,
            q: Optional[np.ndarray] = None,
            e: Optional[np.ndarray] = None,
            i: Optional[np.ndarray] = None,
            raan: Optional[np.ndarray] = None,
            ap: Optional[np.ndarray] = None,
            tp: Optional[np.ndarray] = None,
            times: Optional[Time] = None,
            covariances: Optional[np.ndarray] = None,
            origin: str = "heliocentric",
            frame: str = "ecliptic",
            names: OrderedDict = COMETARY_COLS,
            units: OrderedDict = COMETARY_UNITS,
            mu: float = MU,
        ):
        Coordinates.__init__(self,
            q,
            e,
            i,
            raan,
            ap,
            tp,
            covariances=covariances,
            times=times,
            origin=origin,
            frame=frame,
            names=names,
            units=units
        )
        self._mu = mu

        return

    @property
    def q(self):
        return self._values[:, 0]

    @property
    def e(self):
        return self._values[:, 1]

    @property
    def i(self):
        return self._values[:, 2]

    @property
    def raan(self):
        return self._values[:, 3]

    @property
    def ap(self):
        return self._values[:, 4]

    @property
    def tp(self):
        return self._values[:, 5]

    @property
    def a(self):
        # pericenter distance
        return self.q / (1 - self.e)

    @property
    def p(self):
        # apocenter distance
        return self.a * (1 + self.e)

    @property
    def mu(self):
        return self._mu

    def to_cartesian(self) -> CartesianCoordinates:

        coords_cartesian = cometary_to_cartesian(
            self.values.filled(),
            t0=self.times.tdb.mjd,
            mu=self.mu,
            max_iter=100,
            tol=1e-15,
        )
        coords_cartesian = np.array(coords_cartesian)

        if self.covariances is not None:
            covariances_cartesian = transform_covariances_jacobian(
                self.values.filled(),
                self.covariances.filled(),
                _cometary_to_cartesian,
                t0=self.times.tdb.mjd,
                mu=self.mu,
                max_iter=100,
                tol=1e-15,
            )
        else:
            covariances_cartesian = None

        coords = CartesianCoordinates(
            x=coords_cartesian[:, 0],
            y=coords_cartesian[:, 1],
            z=coords_cartesian[:, 2],
            vx=coords_cartesian[:, 3],
            vy=coords_cartesian[:, 4],
            vz=coords_cartesian[:, 5],
            covariances=covariances_cartesian,
            origin=self.origin,
            frame=self.frame
        )

        return coords

    @classmethod
    def from_cartesian(cls, cartesian: CartesianCoordinates, mu=MU):

        coords_cometary = cartesian_to_cometary(
            cartesian.values.filled(),
            cartesian.times.tdb.mjd,
            mu=mu,
        )
        coords_cometary = np.array(coords_cometary)

        if cartesian.covariances is not None:
            covariances_keplerian = transform_covariances_jacobian(
                cartesian.values.filled(),
                cartesian.covariances.filled(),
                _cartesian_to_cometary,
                t0=cartesian.times.tdb.mjd,
                mu=mu,
            )
        else:
            covariances_keplerian = None

        coords = cls(
            q=coords_cometary[:, 0],
            e=coords_cometary[:, 1],
            i=coords_cometary[:, 2],
            raan=coords_cometary[:, 3],
            ap=coords_cometary[:, 4],
            tp=coords_cometary[:, 5],
            times=cartesian.times,
            covariances=covariances_keplerian,
            origin=cartesian.origin,
            frame=cartesian.frame,
            mu=mu
        )

        return coords

    @classmethod
    def from_df(cls,
            df,
            coord_cols={
                "q" : "q",
                "e" : "e",
                "i" : "i",
                "raan" : "raan",
                "ap" : "ap",
                "tp" : "tp"
            },
            origin_col="origin"
        ):
        """
        Create a KeplerianCoordinates class from a dataframe.

        Parameters
        ----------
        df : `~pandas.DataFrame`
            Pandas DataFrame containing Keplerian coordinates and optionally their
            times and covariances.
        coord_cols : OrderedDict
            Ordered dictionary containing as keys the coordinate dimensions and their equivalent columns
            as values. For example,
                coord_cols = OrderedDict()
                coord_cols["q"] = Column name of pericenter distance values
                coord_cols["e"] = Column name of eccentricity values
                coord_cols["i"] = Column name of inclination values
                coord_cols["raan"] = Column name of longitude of ascending node values
                coord_cols["ap"] = Column name of argument of pericenter values
                coord_cols["tp"] = Column name of time of pericenter passage values.
        origin_col : str
            Name of the column containing the origin of each coordinate.
        """
        data = Coordinates._dict_from_df(
            df,
            coord_cols=coord_cols,
            origin_col=origin_col
        )
        return cls(**data)