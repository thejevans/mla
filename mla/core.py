"""
Top-level analysis code, and functions that are generic enough to not belong
in any class.
"""

__author__ = 'John Evans'
__copyright__ = 'Copyright 2020 John Evans'
__credits__ = ['John Evans', 'Jason Fan', 'Michael Larson']
__license__ = 'Apache License 2.0'
__version__ = '0.0.1'
__maintainer__ = 'John Evans'
__email__ = 'john.evans@icecube.wisc.edu'
__status__ = 'Development'

from typing import Callable, Dict, List, Optional, Tuple, Union, Sequence

import dataclasses
import numpy as np
import scipy.optimize


Minimizer = Callable[
    [Callable, np.ndarray, Union[Sequence, scipy.optimize.Bounds]],
    scipy.optimize.OptimizeResult,
]


@dataclasses.dataclass
class Source:
    """Stores a source object name and location"""
    name: str
    r_asc: float
    dec: float


@dataclasses.dataclass
class Analysis:
    """Stores the components of an analysis."""
    # These imports only exist for type checking. They are in here to ensure
    # no circular imports.
    from . import models  # pylint: disable=import-outside-toplevel
    from . import injectors  # pylint: disable=import-outside-toplevel
    from . import test_statistics  # pylint: disable=import-outside-toplevel
    from . import trial_generators  # pylint: disable=import-outside-toplevel
    model: models.EventModel
    injector: injectors.PsInjector
    ts_preprocessor: test_statistics.PsPreprocess
    test_statistic: test_statistics.TestStatistic
    trial_generator: trial_generators.PsTrialGenerator
    source: Source


def evaluate_ts(analysis: Analysis, events: np.ndarray, params: np.ndarray,
                *args, **kwargs) -> float:
    """Docstring"""
    return analysis.test_statistic(
        params,
        analysis.ts_preprocessor(
            analysis.model, analysis.injector, analysis.source, events),
        *args,
        **kwargs,
    )


def minimize_ts(analysis: Analysis, test_ns: float, test_gamma: float,
                gamma_bounds: Tuple[float] = (-4, -1),
                minimizer: Optional[Minimizer] = None) -> Dict[str, float]:
    """Calculates the params that minimize the ts for the given events.

    Accepts guess values for fitting the n_signal and spectral index, and
    bounds on the spectral index. Uses scipy.optimize.minimize() to fit.
    The default method is 'L-BFGS-B', but can be overwritten by passing
    kwargs to this fuction.

    Args:
        analysis:
        test_ns: An initial guess for the number of signal events (n_signal).
        test_gamma: An initial guess for the spectral index (gamma).
        gamma_bounds:
        minimizer:

    Returns:
        A dictionary containing the minimized overall test-statistic, the
        best-fit n_signal, and the best fit gamma.
    """
    pre_pro = analysis.ts_preprocessor
    test_stat = analysis.test_statistic

    if minimizer is None:
        def minimizer(func, x_0, bounds):
            return scipy.optimize.minimize(func, x0=x_0, args=(pre_pro),
                                           bounds=bounds, method='L-BFGS-B')

    pre_pro = analysis.ts_preprocessor
    test_stat = analysis.test_statistic

    output = {'ts': 0, 'n_signal': test_ns, 'gamma': test_gamma}
    max_ns = pre_pro.n_events - 1e-5

    if len(pre_pro.events) == 0:
        return output

    # Check: n_signal cannot be larger than n_events
    test_ns = max(test_ns, max_ns)

    with np.errstate(divide='ignore', invalid='ignore'):
        # Set the seed values, which tell the minimizer
        # where to start, and the bounds. First do the
        # shape parameters.
        x_0 = [test_ns, test_gamma]
        bounds = [(0, max_ns), gamma_bounds]  # gamma [min, max]
        result = minimizer(test_stat, x0=x_0, bounds=bounds)

        # Store the results in the output array
        output['ts'] = -1 * result.fun
        output['n_signal'] = result.x[0]
        output['gamma'] = result.x[1]

    return output


def produce_trial(analysis: Analysis, *args, **kwargs) -> np.ndarray:
    """Docstring"""
    return analysis.trial_generator.generate(
        analysis.model,
        analysis.injector,
        analysis.source,
        analysis.trial_generator.preprocess_trial(
            analysis.model, analysis.source, *args, **kwargs
        ),
        *args,
        **kwargs,
    )


def produce_and_minimize(analysis: Analysis, n_trials: int,
                         test_params: np.ndarray, *args,
                         **kwargs) -> List[Dict[str, float]]:
    """Docstring"""
    preprocessing = analysis.trial_generator.preprocess_trial(
        analysis.model, analysis.source, *args, **kwargs)

    return [
        minimize_ts(
            analysis,
            analysis.trial_generator.generate(
                analysis.model,
                analysis.injector,
                analysis.source,
                preprocessing,
                *args,
                **kwargs,
            ),
            test_params,
            *args,
            **kwargs,
        ) for _ in range(n_trials)
    ]


def ra_to_rad(hrs: float, mins: float, secs: float) -> float:
    """Converts right ascension to radians.

    Args:
        hrs: Hours.
        mins: Minutes.
        secs: Seconds.

    Returns:
        Radian representation of right ascension.
    """
    return (hrs * 15 + mins / 4 + secs / 240) * np.pi / 180


def dec_to_rad(sign: int, deg: float, mins: float, secs: float) -> float:
    """Converts declination to radians.

    Args:
        sign: A positive integer for a positive sign, a negative integer for a
            negative sign.
        deg: Degrees.
        mins: Minutes.
        secs: Seconds.

    Returns:
        Radian representation of declination.
    """
    return sign / np.abs(sign) * (deg + mins / 60 + secs / 3600) * np.pi / 180


def read(filelist: List[str]) -> np.ndarray:
    """Reads in and concatenates a list of numpy files.

    Args:
        fileList: A list of .npy file paths as strings.

    Returns:
        An array of data events.
    """
    data = []
    for filename in sorted(filelist):
        file_data = np.load(filename)
        if len(data) == 0:
            data = file_data.copy()
        else:
            data = np.concatenate([data, file_data])
    return data


def angular_distance(src_ra: float, src_dec: float, r_a: float,
                     dec: float) -> float:
    """Computes angular distance between source and location.

    Args:
        src_ra: The right ascension of the first point (radians).
        src_dec: The declination of the first point (radians).
        r_a: The right ascension of the second point (radians).
        dec: The declination of the second point (radians).

    Returns:
        The distance, in radians, between the two points.
    """
    sin_dec = np.sin(dec)

    cos_dec = np.sqrt(1. - sin_dec**2)

    cos_dist = (
        np.cos(src_ra - r_a) * np.cos(src_dec) * cos_dec
    ) + np.sin(src_dec) * sin_dec
    # handle possible floating precision errors
    cos_dist = np.clip(cos_dist, -1, 1)

    return np.arccos(cos_dist)


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


def rotate(ra1: float, dec1: float, ra2: float, dec2: float,  # This is fine for a first release... pylint: disable=too-many-arguments, too-many-locals
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
    """
    ra1 = np.atleast_1d(ra1)
    dec1 = np.atleast_1d(dec1)
    ra2 = np.atleast_1d(ra2)
    dec2 = np.atleast_1d(dec2)
    ra3 = np.atleast_1d(ra3)
    dec3 = np.atleast_1d(dec3)

    assert(
        len(ra1) == len(dec1) == len(ra2) == len(dec2) == len(ra3) == len(dec3)
    )

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
    ntn = np.array([np.outer(nv, nv) for nv in nvec])  # This is fine for a first release... pylint: disable=invalid-name
    nx = np.array([cross_matrix(nv) for nv in nvec])  # This is fine for a first release... pylint: disable=invalid-name

    R = np.array([(1. - np.cos(a)) * ntn_i + np.cos(a) * one + np.sin(a) * nx_i  # This is fine for a first release... pylint: disable=invalid-name
                  for a, ntn_i, nx_i in zip(alpha, ntn, nx)])
    vec = np.array([np.dot(r_i, vec_i.T) for r_i, vec_i in zip(R, vec3)])

    r_a = np.arctan2(vec[:, 1], vec[:, 0])
    dec = np.arcsin(vec[:, 2])

    r_a += np.where(r_a < 0., 2. * np.pi, 0.)

    return r_a, dec