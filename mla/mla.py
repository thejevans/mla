"""Functions that are generic enough to not belong in any class"""

__author__ = 'John Evans'
__copyright__ = 'Copyright 2020 John Evans'
__credits__ = ['John Evans', 'Jason Fan', 'Michael Larson']
__license__ = 'Apache License 2.0'
__version__ = '0.0.1'
__maintainer__ = 'John Evans'
__email__ = 'john.evans@icecube.wisc.edu'
__status__ = 'Development'

from typing import Callable, Dict, List, Tuple

import dataclasses
import numpy as np

from mla import models
from mla import injectors
from mla import test_statistics
from mla import trial_generators


@dataclasses.dataclass
class Analysis:
    """Stores the components of an analysis."""
    model: models.EventModel
    injector: injectors.PsInjector
    test_statistic: test_statistics.PsTestStatistic
    trial_generator: trial_generators.PsTrialGenerator


def evaluate_ts(analysis: Analysis, events: np.ndarray, *args,
                **kwargs) -> float:
    """Docstring"""
    return analysis.test_statistic.calculate_ts(
        events,
        analysis.test_statistic.preprocess_ts(
            analysis.model, analysis.injector, events),
        *args,
        **kwargs,
    )


def minimize_ts(analysis: Analysis, events: np.ndarray, *args,
                **kwargs) -> Dict[str, float]:
    """Docstring"""
    return analysis.test_statistic.minimize_ts(
        events,
        analysis.test_statistic.preprocess_ts(
            analysis.model, analysis.injector, events),
        *args,
        **kwargs,
    )


def produce_trial(analysis: Analysis, *args, **kwargs) -> np.ndarray:
    """Docstring"""
    return analysis.trial_generator.generate(
        analysis.model,
        analysis.injector,
        analysis.trial_generator.preprocess_trial(
            analysis.model, analysis.injector, *args, **kwargs),
        *args,
        **kwargs,
    )


def produce_and_minimize(analysis: Analysis, n_trials: int, *args,
                         **kwargs) -> List[Dict[str, float]]:
    """Docstring"""
    preprocessing = analysis.trial_generator.preprocess_trial(
        analysis.model, analysis.injector, *args, **kwargs)

    return [
        minimize_ts(
            analysis,
            analysis.trial_generator.generate(
                analysis.model,
                analysis.injector,
                preprocessing,
                *args,
                **kwargs,
            ),
            *args,
            **kwargs,
        ) for _ in n_trials
    ]


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


def to_unit_vector(r_a: float, dec: float) -> np.array:
    """Converts location on unit sphere to rectangular coordinates.

    Args:
        r_a: The right ascension of the point on the unit sphere.
        dec: The declination of the point on the unit sphere.

    Returns:
        A numpy array of the x, y, and z coordinates of the point.
    """
    return np.array([np.cos(r_a) * np.cos(dec),
                     np.sin(r_a) * np.cos(dec),
                     np.sin(dec)])


def angular_distance(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Calculates the angle between two points on the unit sphere.

    Args:
        ra1: The right ascension of the first point (radians).
        dec1: The declination of the first point (radians).
        ra2: The right ascension of the second point (radians).
        dec2: The declination of the second point (radians).

    Returns:
        The distance, in radians, between the two points.
    """
    unit1 = to_unit_vector(ra1, dec1)
    unit2 = to_unit_vector(ra2, dec2)

    if len(unit1.shape) != 1:
        return np.arccos(np.dot(unit1.T, unit2))
    return np.arccos(np.dot(unit1, unit2))


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
    nTn = np.array([np.outer(nv, nv) for nv in nvec])  # This is fine for a first release... pylint: disable=invalid-name
    nx = np.array([cross_matrix(nv) for nv in nvec])  # This is fine for a first release... pylint: disable=invalid-name

    R = np.array([(1. - np.cos(a)) * nTn_i + np.cos(a) * one + np.sin(a) * nx_i  # This is fine for a first release... pylint: disable=invalid-name
                  for a, nTn_i, nx_i in zip(alpha, nTn, nx)])
    vec = np.array([np.dot(R_i, vec_i.T) for R_i, vec_i in zip(R, vec3)])

    r_a = np.arctan2(vec[:, 1], vec[:, 0])
    dec = np.arcsin(vec[:, 2])

    r_a += np.where(r_a < 0., 2. * np.pi, 0.)

    return r_a, dec