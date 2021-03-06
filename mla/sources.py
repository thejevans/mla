"""
Docstring
"""

__author__ = 'John Evans'
__copyright__ = 'Copyright 2020 John Evans'
__credits__ = ['John Evans', 'Jason Fan', 'Michael Larson']
__license__ = 'Apache License 2.0'
__version__ = '0.0.1'
__maintainer__ = 'John Evans'
__email__ = 'john.evans@icecube.wisc.edu'
__status__ = 'Development'


import dataclasses

import numpy as np


@dataclasses.dataclass
class Source:
    """Stores a source object name and location"""
    name: str
    ra: float
    dec: float

    def sample_location(self, size: int):
        """Sample locations.

        Args:
            size: number of points to sample
        """
        return (np.ones(size) * self.ra, np.ones(size) * self.dec)

    def get_location(self):
        """return location of the source"""
        return (self.ra, self.dec)

    def get_sigma(self):
        """return 0 for point source"""
        return 0


@dataclasses.dataclass
class GaussianExtendedSource(Source):
    """Gaussian Extended Source"""
    sigma: float

    def sample_location(self, size: int):
        """Sample locations.

        Args:
            size: number of points to sample
        """
        return (np.random.normal(self.ra, self.sigma, size),
                np.random.normal(self.dec, self.sigma, size))

    def get_sigma(self):
        """return sigma for GaussianExtendedSource"""
        return self.sigma


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
