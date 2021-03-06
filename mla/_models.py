"""
The classes in this file do preprocessing on data and monte carlo to be used
to do a point source analysis.
"""

__author__ = 'John Evans'
__copyright__ = 'Copyright 2020 John Evans'
__credits__ = ['John Evans', 'Jason Fan', 'Michael Larson']
__license__ = 'Apache License 2.0'
__version__ = '0.0.1'
__maintainer__ = 'John Evans'
__email__ = 'john.evans@icecube.wisc.edu'
__status__ = 'Development'

from typing import Optional, Tuple, Union

import copy
import scipy
import numpy as np
import numpy.lib.recfunctions as rf
from scipy.interpolate import UnivariateSpline as Spline

from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar

from . import sources
from . import time_profiles


def cross_matrix(mat: np.array) -> np.array:
    """Calculate cross product matrix.
    A[ij] = x_i * y_j - y_i * x_j
    Args:
        mat: A 2D array to take the cross product of.
    Returns:
        The cross matrix.
    """
    skv = np.roll(np.roll(np.diag(mat.ravel()), 1, 1), -1, 0)
    return skv - skv.T


def rotate(ra1: float, dec1: float, ra2: float, dec2: float,
           ra3: float, dec3: float) -> Tuple[float, float]:
    """Rotation matrix for rotation of (ra1, dec1) onto (ra2, dec2).

    The rotation is performed on (ra3, dec3).

    Args:
        ra1: The right ascension of the point to be rotated from.
        dec1: The declination of the point to be rotated from.
        ra2: the right ascension of the point to be rotated onto.
        dec2: the declination of the point to be rotated onto.
        ra3: the right ascension of the point that will actually be rotated.
        dec3: the declination of the point that will actually be rotated.

    Returns:
        The rotated ra3 and dec3.

    Raises:
        IndexError: Arguments must all have the same dimension.
    """
    ra1 = np.atleast_1d(ra1)
    dec1 = np.atleast_1d(dec1)
    ra2 = np.atleast_1d(ra2)
    dec2 = np.atleast_1d(dec2)
    ra3 = np.atleast_1d(ra3)
    dec3 = np.atleast_1d(dec3)

    if not (
        len(ra1) == len(dec1) == len(ra2) == len(dec2) == len(ra3) == len(dec3)
    ):
        raise IndexError('Arguments must all have the same dimension.')

    cos_alpha = np.cos(ra2 - ra1) * np.cos(dec1) * np.cos(dec2) \
        + np.sin(dec1) * np.sin(dec2)

    # correct rounding errors
    cos_alpha[cos_alpha > 1] = 1
    cos_alpha[cos_alpha < -1] = -1

    alpha = np.arccos(cos_alpha)
    vec1 = np.vstack([np.cos(ra1) * np.cos(dec1),
                      np.sin(ra1) * np.cos(dec1),
                      np.sin(dec1)]).T
    vec2 = np.vstack([np.cos(ra2) * np.cos(dec2),
                      np.sin(ra2) * np.cos(dec2),
                      np.sin(dec2)]).T
    vec3 = np.vstack([np.cos(ra3) * np.cos(dec3),
                      np.sin(ra3) * np.cos(dec3),
                      np.sin(dec3)]).T
    nvec = np.cross(vec1, vec2)
    norm = np.sqrt(np.sum(nvec**2, axis=1))
    nvec[norm > 0] /= norm[np.newaxis, norm > 0].T

    one = np.diagflat(np.ones(3))
    ntn = np.array([np.outer(nv, nv) for nv in nvec])
    nx = np.array([cross_matrix(nv) for nv in nvec])

    r = np.array([(1. - np.cos(a)) * ntn_i + np.cos(a) * one + np.sin(a) * nx_i
                  for a, ntn_i, nx_i in zip(alpha, ntn, nx)])
    vec = np.array([np.dot(r_i, vec_i.T) for r_i, vec_i in zip(r, vec3)])

    r_a = np.arctan2(vec[:, 1], vec[:, 0])
    dec = np.arcsin(vec[:, 2])

    r_a += np.where(r_a < 0., 2. * np.pi, 0.)

    return r_a, dec


@dataclass
class EventModelBase:
    """Stores the events and pre-processed parameters used in analyses.

    Currently, this class uses internal data and monte-carlo datasets. This
    will be updated before the first release to use the upcoming public data
    release.

    Attributes:
        data (np.ndarray): Real neutrino event data.
        sim (np.ndarray): Simulated neutrino events.
        grl (np.ndarray): A list of runs/times when the detector was working
            properly.
        reduced_sim (np.ndarray):
        gamma (float):
    """
    source: InitVar[sources.Source]
    data: InitVar[np.ndarray]
    sim: InitVar[np.ndarray]
    grl: InitVar[np.ndarray]
    gamma: InitVar[float]

    _source: sources.Source = field(init=False)
    _data: np.ndarray = field(init=False)
    _sim: np.ndarray = field(init=False)
    _gamma: float = field(init=False)
    _n_background: int = field(init=False)
    _grl: np.ndarray = field(init=False)
    _grl_rates: np.ndarray = field(init=False)
    _reduced_sim: np.ndarray = field(init=False)
    _background_dec_spline: Spline = field(init=False)
    _livetime: float = field(init=False)
    _sampling_width: Optional[float] = field(init=False)


@dataclass
class EventModelDefaultsBase:
    """Stores the events and pre-processed parameters used in analyses.

    Currently, this class uses internal data and monte-carlo datasets. This
    will be updated before the first release to use the upcoming public data
    release.

    Attributes:
        sampling_width:
        background_dec_spline: A spline fit of neutrino flux vs. sin(dec).
    """
    sampling_width: InitVar[Optional[float]] = field(default=np.deg2rad(3))
    background_sin_dec_bins: InitVar[Union[np.array, int]] = field(default=500)


@dataclass
class EventModel(EventModelDefaultsBase, EventModelBase):
    """Stores the events and pre-processed parameters used in analyses.

    Currently, this class uses internal data and monte-carlo datasets. This
    will be updated before the first release to use the upcoming public data
    release.
    """
    def __post_init__(
        self,
        source: sources.Source,
        data: np.ndarray,
        sim: np.ndarray,
        grl: np.ndarray,
        gamma: float,
        sampling_width: Optional[float],
        background_sin_dec_bins: Union[np.array, int],
    ) -> None:
        """Initializes EventModel and calculates energy sob maps.

        Args:
            source:
            grl:
            background_sin_dec_bins: If an int, then the number of bins
                spanning -1 -> 1, otherwise, a numpy array of bin edges.

        Raises:
            ValueError:
        """
        try:
            self._data = rf.append_fields(
                data,
                'sindec',
                np.sin(data['dec']),
                usemask=False,
            )
            # The full simulation set,this is for the overall normalization of
            # the Energy S/B ratio
        except ValueError:  # sindec already exist
            self._data = data

        try:
            self._sim = rf.append_fields(
                sim,
                'sindec',
                np.sin(sim['dec']),
                usemask=False,
            )
            # The full simulation set,this is for the overall normalization of
            # the Energy S/B ratio
        except ValueError:  # sindec already exist
            self._sim = sim

        self._source = source
        min_mjd = np.min(self._data['time'])
        max_mjd = np.max(self._data['time'])
        self._grl = grl[(grl['start'] < max_mjd) & (grl['stop'] > min_mjd)]

        self._gamma = gamma
        self._sampling_width = sampling_width
        self._init_reduced_sim(source)

        if isinstance(background_sin_dec_bins, int):
            background_sin_dec_bins = np.linspace(-1, 1,
                                                  1 + background_sin_dec_bins)

        self._background_dec_spline = self._init_background_dec_spline(
            background_sin_dec_bins)

        self._livetime = self._grl['livetime'].sum()
        self._n_background = self._grl['events'].sum()
        self._grl_rates = self._grl['events'] / self._grl['livetime']

    def _init_background_dec_spline(self, sin_dec_bins: np.array, *args,
                                    **kwargs) -> Spline:
        """Builds a histogram of neutrino flux vs. sin(dec) and splines it.

        The UnivariateSpline function call uses these default arguments:
        bbox=[-1.0, 1.0], s=1.5e-5, ext=1. To replace any of these defaults, or
        to pass any other args/kwargs to UnivariateSpline, just pass them to
        this function.

        Args:
            sin_dec_bins: A numpy array of bin edges to use to build the
                histogram to spline.

        Returns:
            A spline function of the neutrino flux vs. sin(dec) histogram.
        """
        # Our background PDF only depends on declination.
        # In order for us to capture the dec-dependent
        # behavior, we first take a look at the dec values
        # in the data. We can do this by histogramming them.
        hist, bins = np.histogram(self._data['sindec'], bins=sin_dec_bins,
                                  density=True)
        bin_centers = bins[:-1] + np.diff(bins) / 2

        # These values have a lot of "noise": they jump
        # up and down quite a lot. We could use fewer
        # bins, but that may hide some features that
        # we care about. We want something that captures
        # the right behavior, but is smooth and continuous.
        # The best way to do that is to use a "spline",
        # which will fit a continuous and differentiable
        # piecewise polynomial function to our data.
        # We can set a smoothing factor (s) to control
        # how smooth our spline is.

        if 'bbox' not in kwargs:
            kwargs['bbox'] = [-1.0, 1.0]
        if 's' not in kwargs:
            kwargs['s'] = 1.5e-5
        if 'ext' not in kwargs:
            kwargs['ext'] = 3

        return Spline(bin_centers, hist, *args, **kwargs)

    def _init_reduced_sim(self, source: sources.Source) -> None:
        """Gets a small simulation dataset to use for injecting signal.

        Prunes the simulation set to only events close to a given source and
        calculate the weight for each event. Adds the weights as a new column
        to the simulation set.

        Args:
            source:

        Returns:
            A reweighted simulation set around the source declination.
        """
        if self._sampling_width is not None:
            self._cut_sim_truedec(source)
        else:
            self._reduced_sim = self._sim.copy()
        self._reduced_sim = self._weight_reduced_sim(self._reduced_sim)
        self._randomize_sim_times()

    def _randomize_sim_times(self) -> None:
        """Docstring"""
        # Randomly assign times to the simulation events within the data time
        # range.
        min_time = np.min(self._data['time'])
        max_time = np.max(self._data['time'])
        self._reduced_sim['time'] = np.random.uniform(
            min_time, max_time, size=len(self._reduced_sim))

    def _cut_sim_truedec(self, source: sources.Source) -> None:
        """Select simulation events in a true dec band(for ns calculation)

        Args:
            source:
        """
        sindec_dist = np.abs(source.dec - self._sim['trueDec'])
        close = sindec_dist < self._sampling_width
        self._reduced_sim = self._sim[close].copy()

        omega = 2 * np.pi * (np.min(
            [np.sin(source.dec + self._sampling_width), 1]
        ) - np.max([np.sin(source.dec - self._sampling_width), -1]))
        self._reduced_sim['ow'] /= omega

    def _weight_reduced_sim(self, reduced_sim: np.ndarray) -> np.ndarray:
        """Docstring"""
        if 'weight' not in reduced_sim.dtype.names:
            reduced_sim = rf.append_fields(
                reduced_sim, 'weight',
                np.zeros(len(reduced_sim)),
                dtypes=np.float32
            )

        # Assign the weights using the newly defined "time profile"
        # classes above. If you want to make this a more complicated
        # shape, talk to me and we can work it out.
        rescaled_energy = (reduced_sim['trueE'] / 100.e3)**self._gamma
        reduced_sim['weight'] = reduced_sim['ow'] * rescaled_energy
        return reduced_sim

    def background_spatial_pdf(self, events: np.array) -> np.array:
        """Calculates the background probability of events based on their dec.

        Uses the background_dec_spline() function from the given event_model to
        get the probabilities.

        Args:
            events: An array of events including their declination.
            event_model: Preprocessed data and simulation.

        Returns:
            The value for the background space pdf for the given events decs.
        """
        bg_densities = self._background_dec_spline(events['sindec'])
        return (1 / (2 * np.pi)) * bg_densities

    def inject_background_events(self) -> np.ndarray:
        """Injects background events for a trial.

        Args:
            event_model: Preprocessed data and simulation.

        Returns:
            An array of injected background events.
        """
        # Get the number of events we see from these runs
        n_background_observed = np.random.poisson(self._n_background)

        # How many events should we add in? This will now be based on the
        # total number of events actually observed during these runs
        background = np.random.choice(self._data, n_background_observed).copy()

        # Randomize the background RA
        background['ra'] = np.random.uniform(0, 2 * np.pi, len(background))

        return background

    def inject_signal_events(
        self,
        flux_norm: float,
        n_signal_observed: Optional[int] = None,
    ) -> np.ndarray:
        """Injects signal events for a trial.

        Args:
            flux_norm:
            n_signal_observed:

        Returns:
            An array of injected signal events.
        """

        # Pick the signal events
        total = self._reduced_sim['weight'].sum()

        if n_signal_observed is None:
            n_signal_observed = scipy.stats.poisson.rvs(total * flux_norm)

        signal = np.random.choice(
            self._reduced_sim,
            n_signal_observed,
            p=self._reduced_sim['weight'] / total,
            replace=False,
        ).copy()

        if len(signal) > 0:
            ra, dec = self._source.sample_location(len(signal))

            signal['ra'], signal['dec'] = rotate(
                signal['trueRa'],
                signal['trueDec'],
                ra,
                dec,
                signal['ra'],
                signal['dec'],
            )

            signal['trueRa'], signal['trueDec'] = rotate(
                signal['trueRa'],
                signal['trueDec'],
                ra,
                dec,
                signal['trueRa'],
                signal['trueDec'],
            )

            signal['sindec'] = np.sin(signal['dec'])

        return signal

    def scramble_times(self, times: np.ndarray,
                       background: bool = True) -> np.ndarray:
        """Docstring"""
        p = None

        if background:
            p = self._grl_rates / self._grl_rates.sum()

        runs = np.random.choice(
            self._grl,
            size=len(times),
            replace=True,
            p=p,
        )

        return np.random.uniform(runs['start'], runs['stop'])

    @property
    def gamma(self) -> float:
        """Docstring"""
        return self._gamma

    @gamma.setter
    def gamma(self, new_gamma) -> None:
        """Docstring"""
        self._gamma = new_gamma
        self._reduced_sim = self._weight_reduced_sim(self._reduced_sim)

    @property
    def source(self) -> sources.Source:
        """Docstring"""
        return self._source

    @source.setter
    def source(self, new_source: sources.Source) -> None:
        """Docstring"""
        self._source = new_source
        self._init_reduced_sim(new_source)

    @property
    def data(self) -> np.ndarray:
        """Docstring"""
        return self._data

    @property
    def sim(self) -> np.ndarray:
        """Docstring"""
        return self._sim

    @property
    def livetime(self) -> float:
        """Docstring"""
        return self._livetime

    @property
    def sampling_width(self) -> float:
        """Docstring"""
        return self._sampling_width


@dataclass
class TdEventModelDefaultsBase(EventModelDefaultsBase):
    """Docstring"""
    background_time_profile: Optional[time_profiles.GenericProfile] = None
    signal_time_profile: Optional[time_profiles.GenericProfile] = None
    background_window: InitVar[float] = field(default=14)
    withinwindow: InitVar[bool] = field(default=False)


@dataclass
class TdEventModel(EventModel, TdEventModelDefaultsBase, EventModelBase):
    """Docstring"""
    def __post_init__(
        self,
        source: sources.Source,
        data: np.ndarray,
        sim: np.ndarray,
        grl: np.ndarray,
        gamma: np.ndarray,
        sampling_width: Optional[float],
        background_sin_dec_bins: Union[np.array, int],
        background_window: float,
        withinwindow: bool,
    ) -> None:
        """Initializes EventModel and calculates energy sob maps.

        Args:
            source:
            grl:
            background_sin_dec_bins: If an int, then the number of bins
                spanning -1 -> 1, otherwise, a numpy array of bin edges.
            background_window:
            withinwindow:

        Raises:
            RuntimeError:
        """
        super().__post_init__(
            source,
            data,
            sim,
            grl,
            gamma,
            sampling_width,
            background_sin_dec_bins,
        )

        if self.background_time_profile is None:
            self.background_time_profile = time_profiles.UniformProfile(
                start=np.min(data['time']),
                length=np.max(data['time']) - np.min(data['time']),
            )

        if self.signal_time_profile is None:
            self.signal_time_profile = copy.deepcopy(
                self.background_time_profile,
            )

        # Find the run contian in the background time window
        start, stop = self.background_time_profile.range
        return_stop_contained = True

        if not withinwindow:
            start -= background_window
            stop = start
            return_stop_contained = False

        background_run_mask = self._contained_run_mask(
            start,
            stop,
            return_stop_contained=return_stop_contained,
        )

        if not np.any(background_run_mask):
            print('ERROR: No runs found in GRL for calculation of '
                  'background rates!')
            raise RuntimeError

        background_grl = self._grl[background_run_mask]
        self._n_background = background_grl['events'].sum()
        self._n_background /= background_grl['livetime'].sum()
        self._n_background *= self._contained_livetime(
            *self.background_time_profile.range,
            background_grl,
        )

    def _contained_run_mask(
        self,
        start: float,
        stop: float,
        return_stop_contained: bool = True,
    ) -> np.ndarray:
        """Docstring"""
        fully_contained = (
            self._grl['start'] >= start
        ) & (self._grl['stop'] < stop)

        start_contained = (
            self._grl['start'] < start
        ) & (self._grl['stop'] > start)

        if not return_stop_contained:
            return fully_contained | start_contained

        stop_contained = (
            self._grl['start'] < stop
        ) & (self._grl['stop'] > stop)

        return fully_contained | start_contained | stop_contained

    def contained_livetime(self, start: float, stop: float) -> float:
        """Docstring"""
        contained_runs = self._grl[self._contained_run_mask(start, stop)]
        return self._contained_livetime(start, stop, contained_runs)

    def _contained_livetime(
        self,
        start: float,
        stop: float,
        contained_runs: np.ndarray,
    ) -> float:
        """Docstring"""
        runs_before_start = contained_runs[contained_runs['start'] < start]
        runs_after_stop = contained_runs[contained_runs['stop'] > stop]
        contained_livetime = contained_runs['livetime'].sum()

        if len(runs_before_start) == 1:
            contained_livetime -= start - runs_before_start['start'][0]

        if len(runs_after_stop) == 1:
            contained_livetime -= runs_after_stop['stop'][0] - stop

        return contained_livetime

    def scramble_times(self, times: np.ndarray,
                       background: bool = True) -> np.ndarray:
        """Docstring"""
        if background:
            profile = self.background_time_profile
        else:
            profile = self.signal_time_profile

        grl_start_cdf = profile.cdf(
            self._grl['start'])
        grl_stop_cdf = profile.cdf(
            self._grl['stop'])

        valid = np.logical_and(grl_start_cdf < 1, grl_stop_cdf > 0)
        grl_weighted_rates = grl_stop_cdf[valid] - grl_start_cdf[valid]

        if background:
            grl_weighted_rates *= self._grl_rates[valid]

        runs = np.random.choice(
            self._grl[valid],
            size=len(times),
            replace=True,
            p=grl_weighted_rates / grl_weighted_rates.sum(),
        )

        return profile.inverse_transform_sample(runs['start'], runs['stop'])
