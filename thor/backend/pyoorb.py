import os
import warnings
import numpy as np
import pyoorb as oo
from astropy.time import Time

from ..coordinates.cartesian import CartesianCoordinates
from ..coordinates.spherical import SphericalCoordinates
from ..orbits.orbits import Orbits
from ..orbits.ephemeris import Ephemeris
from ..observers.observers import Observers
from ..utils.indexable import concatenate
from .backend import Backend

PYOORB_CONFIG = {
    "dynamical_model" : "N",
    "ephemeris_file" : "de430.dat"
}

class PYOORB(Backend):

    def __init__(self, **kwargs):
        # Make sure only the correct kwargs
        # are passed to the constructor
        allowed_kwargs = PYOORB_CONFIG.keys()
        for k in kwargs:
            if k not in allowed_kwargs:
                raise ValueError()

        # If an allowed kwarg is missing, add the
        # default
        for k in allowed_kwargs:
            if k not in kwargs:
                kwargs[k] = PYOORB_CONFIG[k]

        super().__init__(name="OpenOrb", **kwargs)

        self.setup()
        return

    def setup(self):
        """
        Initialize PYOORB with the designated JPL ephemeris file.

        """
        env_var = f"THOR_PYOORB"
        if env_var in os.environ.keys() and os.environ[env_var] == "True":
            pass
        else:
            if os.environ.get("OORB_DATA") == None:
                os.environ["OORB_DATA"] = os.path.join(os.environ["CONDA_PREFIX"], "share/openorb")
            # Prepare pyoorb
            ephfile = os.path.join(os.getenv('OORB_DATA'), self.ephemeris_file)
            err = oo.pyoorb.oorb_init(ephfile)
            if err == 0:
                os.environ[env_var] = "True"
                self.__env_var = env_var
                self.is_setup = True
            else:
                warnings.warn("PYOORB returned error code: {}".format(err))

        return

    def _configure_orbits(self, orbits, t0, orbit_type, time_scale, magnitude, slope):
        """
        Convert an array of orbits into the format expected by PYOORB.

        Parameters
        ----------
        orbits : `~numpy.ndarray` (N, 6)
            Orbits to convert. See orbit_type for expected input format.
        t0 : `~numpy.ndarray` (N)
            Epoch in MJD at which the orbits are defined.
        orbit_type : {'cartesian', 'keplerian', 'cometary'}, optional
            Orbital element representation of the provided orbits.
            If cartesian:
                x : heliocentric ecliptic J2000 x position in AU
                y : heliocentric ecliptic J2000 y position in AU
                z : heliocentric ecliptic J2000 z position in AU
                vx : heliocentric ecliptic J2000 x velocity in AU per day
                vy : heliocentric ecliptic J2000 y velocity in AU per day
                vz : heliocentric ecliptic J2000 z velocity in AU per day
            If keplerian:
                a : semi-major axis in AU
                e : eccentricity in degrees
                i : inclination in degrees
                Omega : longitude of the ascending node in degrees
                omega : argument of periapsis in degrees
                M0 : mean anomaly in degrees
            If cometary:
                p : perihelion distance in AU
                e : eccentricity in degrees
                i : inclination in degrees
                Omega : longitude of the ascending node in degrees
                omega : argument of periapsis in degrees
                T0 : time of perihelion passage in MJD
        time_scale : {'UTC', 'UT1', 'TT', 'TAI'}, optional
            Time scale of the MJD epochs.
        magnitude : float or `~numpy.ndarray` (N), optional
            Absolute H-magnitude or M1 magnitude.
        slope : float or `~numpy.ndarray` (N), optional
            Photometric slope parameter G or K1.

        Returns
        -------
        orbits_pyoorb : `~numpy.ndarray` (N, 12)
            Orbits formatted in the format expected by PYOORB.
                orbit_id : index of input orbits
                elements x6: orbital elements of propagated orbits
                orbit_type : orbit type
                epoch_mjd : epoch of the propagate orbit
                time_scale : time scale of output epochs
                H/M1 : absolute magnitude
                G/K1 : photometric slope parameter
        """
        orbits_ = orbits.copy()
        if orbits_.shape == (6,):
            num_orbits = 1
        else:
            num_orbits = orbits_.shape[0]

        if orbit_type == "cartesian":
            orbit_type = [1 for i in range(num_orbits)]
        elif orbit_type == "cometary":
            orbit_type = [2 for i in range(num_orbits)]
            #H = M1
            #G = K1
            orbits_[:, 1:5] = np.radians(orbits_[:, 1:5])
        elif orbit_type == "keplerian":
            orbit_type = [3 for i in range(num_orbits)]
            orbits_[:, 1:] = np.radians(orbits_[:, 1:])
        else:
            raise ValueError("orbit_type should be one of {'cartesian', 'keplerian', 'cometary'}")

        if time_scale == "UTC":
            time_scale = [1 for i in range(num_orbits)]
        elif time_scale == "UT1":
            time_scale = [2 for i in range(num_orbits)]
        elif time_scale == "TT":
            time_scale = [3 for i in range(num_orbits)]
        elif time_scale == "TAI":
            time_scale = [4 for i in range(num_orbits)]
        else:
            raise ValueError("time_scale should be one of {'UTC', 'UT1', 'TT', 'TAI'}")

        if slope is not None:
            if not isinstance(slope, np.ndarray):
                slope = np.array([slope for i in range(num_orbits)])
        else:
            slope = [0.15 for i in range(num_orbits)]

        if magnitude is not None:
            if not isinstance(magnitude, np.ndarray):
                magnitude = np.array([magnitude for i in range(num_orbits)])
        else:
            magnitude = [20.0 for i in range(num_orbits)]

        ids = [i for i in range(num_orbits)]

        if num_orbits > 1:
            orbits_pyoorb = np.array(
                np.array([
                    ids,
                    *list(orbits_.T),
                     orbit_type,
                     t0,
                     time_scale,
                     magnitude,
                     slope
                ]).T,
                dtype=np.double,
                order='F'
            )
        else:
            orbits_pyoorb = np.array([
                [
                    ids[0],
                    *list(orbits_.T),
                    orbit_type[0],
                    t0[0],
                    time_scale[0],
                    magnitude[0],
                    slope[0]]
                ],
                dtype=np.double,
                order='F'
            )

        return orbits_pyoorb

    def _configure_epochs(self, epochs, time_scale):
        """
        Convert an array of orbits into the format expected by PYOORB.

        Parameters
        ----------
        epochs : `~numpy.ndarray` (N)
            Epoch in MJD to convert.
        time_scale : {'UTC', 'UT1', 'TT', 'TAI'}
            Time scale of the MJD epochs.

        Returns
        -------
        epochs_pyoorb : `~numpy.ndarray (N, 2)
            Epochs converted into the PYOORB format.
        """
        num_times = len(epochs)
        if time_scale == "UTC":
            time_scale = [1 for i in range(num_times)]
        elif time_scale == "UT1":
            time_scale = [2 for i in range(num_times)]
        elif time_scale == "TT":
            time_scale = [3 for i in range(num_times)]
        elif time_scale == "TAI":
            time_scale = [4 for i in range(num_times)]
        else:
            raise ValueError("time_scale should be one of {'UTC', 'UT1', 'TT', 'TAI'}")

        epochs_pyoorb = np.array(list(np.vstack([epochs, time_scale]).T), dtype=np.double, order='F')
        return epochs_pyoorb

    def _propagate_orbits(self,
            orbits: Orbits,
            times: Time
        ) -> Orbits:
        """
        Propagate orbits using PYOORB.

        Parameters
        ----------
        orbits : `~thor.orbits.orbits.Orbits` (N)
            Orbits to propagate.
        times : `~astropy.time.core.Time` (M)
            Times to which to propagate orbits.

        Returns
        -------
        propagated : `~thor.orbits.orbits.Orbits` (N * M)
            Orbits propagated to each time in times.
        """
        # Convert orbits into PYOORB format
        orbits_pyoorb = self._configure_orbits(
            orbits.cartesian.values.filled(),
            orbits.cartesian.times.tt.mjd,
            "cartesian",
            "TT",
            magnitude=None,
            slope=None,
        )

        # Convert epochs into PYOORB format
        epochs_pyoorb = self._configure_epochs(times.tt.mjd, "TT")

        # Propagate orbits to each epoch and append to list
        # of new states
        states = []
        orbits_pyoorb_i = orbits_pyoorb.copy()
        for epoch in epochs_pyoorb:
            orbits_pyoorb_i, err = oo.pyoorb.oorb_propagation(
                in_orbits=orbits_pyoorb_i,
                in_epoch=epoch,
                in_dynmodel=self.dynamical_model
            )
            states.append(orbits_pyoorb_i)

        # Convert list of new states into a pandas data frame
        # These states at the moment will always be return as cartesian
        # state vectors
        # elements = ["x", "y", "z", "vx", "vy", "vz"]
        # Other PYOORB state vector representations:
        #"keplerian":
        #    elements = ["a", "e", "i", "Omega", "omega", "M0"]
        #"cometary":
        #    elements = ["q", "e", "i", "Omega", "omega", "T0"]
        states = np.concatenate(states)

        # Extract cartesian states from PYOORB results
        orbit_ids_ = states[:, 0].astype(int)
        x = states[:, 1]
        y = states[:, 2]
        z = states[:, 3]
        vx = states[:, 4]
        vy = states[:, 5]
        vz = states[:, 6]
        mjd_tt = states[:, 8]

        # Convert output epochs to TDB
        times_ = Time(
            mjd_tt,
            format="mjd",
            scale="tt"
        )
        times_ = times_.tdb

        if orbits.object_ids is not None:
            object_ids = orbits.object_ids[orbit_ids_]
        else:
            object_ids = None

        if orbits.orbit_ids is not None:
            orbit_ids = orbits.orbit_ids[orbit_ids_]
        else:
            orbit_ids = None

        propagated_orbits = Orbits(
            CartesianCoordinates(
                x=x,
                y=y,
                z=z,
                vx=vx,
                vy=vy,
                vz=vz,
                times=times_,
                origin="heliocenter",
                frame="ecliptic"
            ),
            orbit_ids=orbit_ids,
            object_ids=object_ids
        )
        return propagated_orbits

    def _generate_ephemeris(self,
            orbits: Orbits,
            observers: Observers
        ) -> Ephemeris:
        """
        Generate ephemeris using PYOORB.

        Parameters
        ----------
        orbits : `~thor.orbits.orbits.Orbits` (N)
            Orbits for which to generate ephemerides.
        observers : `~thor.observers.observers.Observers` (M)
            Observers for which to generate the ephemerides of each
            orbit.

        Returns
        -------
        ephemeris : `~thor.orbits.classes.Ephemeris` (N * M)
            Predicted ephemerides for each orbit observed by each
            observer.
        """
        # Convert orbits into PYOORB format
        orbits_pyoorb = self._configure_orbits(
            orbits.cartesian.values.filled(),
            orbits.cartesian.times.tt.mjd,
            "cartesian",
            "TT",
            magnitude=None,
            slope=None
        )

        # columns = [
        #     "mjd_utc",
        #     "RA_deg",
        #     "Dec_deg",
        #     "vRAcosDec",
        #     "vDec",
        #     "PhaseAngle_deg",
        #     "SolarElon_deg",
        #     "r_au",
        #     "delta_au",
        #     "VMag",
        #     "PosAngle_deg",
        #     "TLon_deg",
        #     "TLat_deg",
        #     "TOCLon_deg",
        #     "TOCLat_deg",
        #     "HLon_deg",
        #     "HLat_deg",
        #     "HOCLon_deg",
        #     "HOCLat_deg",
        #     "Alt_deg",
        #     "SolarAlt_deg",
        #     "LunarAlt_deg",
        #     "LunarPhase",
        #     "LunarElon_deg",
        #     "obj_x",
        #     "obj_y",
        #     "obj_z",
        #     "obj_vx",
        #     "obj_vy",
        #     "obj_vz",
        #     "obs_x",
        #     "obs_y",
        #     "obs_z",
        #     "TrueAnom"
        # ]

        ephemeris_list = []
        for observatory_code, observation_times in observers.iterate_unique():
            # Convert epochs into PYOORB format
            epochs_pyoorb = self._configure_epochs(observation_times.utc.mjd, "UTC")

            # Generate ephemeris
            ephemeris, err = oo.pyoorb.oorb_ephemeris_full(
              in_orbits=orbits_pyoorb,
              in_obscode=observatory_code,
              in_date_ephems=epochs_pyoorb,
              in_dynmodel=self.dynamical_model
            )

            if err == 1:
                warnings.warn("PYOORB has returned an error!", UserWarning)

            ephemeris = np.vstack(ephemeris)

            ids = np.arange(0, len(orbits))
            orbit_ids = np.array([i for i in ids for j in observation_times.utc.mjd])
            observatory_codes = np.array([observatory_code for i in range(len(ephemeris))])

            if orbits.object_ids is not None:
                object_ids = orbits.object_ids[orbit_ids]
            else:
                object_ids = None

            if orbits.orbit_ids is not None:
                orbit_ids = orbits.orbit_ids[orbit_ids]

            ephemeris = Ephemeris(
                SphericalCoordinates(
                    rho=ephemeris[:, 8],
                    lon=ephemeris[:, 1],
                    lat=ephemeris[:, 2],
                    vrho=None,
                    vlon=ephemeris[:, 3] / np.cos(np.radians(ephemeris[:, 4])),
                    vlat=ephemeris[:, 4],
                    times=Time(
                        ephemeris[:, 0],
                        scale="utc",
                        format="mjd"
                    ),
                    origin=observatory_codes,
                    frame="equatorial"
                ),
                orbit_ids=orbit_ids,
                object_ids=object_ids
            )

            ephemeris_list.append(ephemeris)

        ephemeris = concatenate(ephemeris_list)
        return ephemeris
