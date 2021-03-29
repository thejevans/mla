"""Docstring"""

__author__ = 'John Evans'
__copyright__ = 'Copyright 2020 John Evans'
__credits__ = ['John Evans', 'Jason Fan', 'Michael Larson']
__license__ = 'Apache License 2.0'
__version__ = '0.0.1'
__maintainer__ = 'John Evans'
__email__ = 'john.evans@icecube.wisc.edu'
__status__ = 'Development'

import unittest
import sys
import copy
import pickle
import numpy as np

from context import mla
import internal_args

if __name__ == '__main__':
    args = internal_args.parse(sys.argv)

    # Example source object
    source = mla.Source(
        name='TXS',
        ra=np.radians(77.3583),
        dec=np.radians(5.6931),
    )

    # Example time profile object
    uniform_profile = mla.UniformProfile(
        start=56224,
        length=158,
    )

    # Load or generate model based on command line arguments
    if args['model'] is not None:
        model = args['model']
    else:
        if args['verbose']:
            print('Generating model...', end='', flush=True)

        model = mla.I3EventModel(
            source=source,
            data=args['data'],
            sim=args['sim'],
            grl=args['grl'],
            gamma=-2,
            background_time_profile=copy.deepcopy(uniform_profile),
            signal_time_profile=copy.deepcopy(uniform_profile),
            sampling_width=np.radians(3),
            withinwindow=True,
        )
        model_file_loc = ''.join([args['outdir'], 'example_model.pkl'])

        if args['verbose']:
            print(
                f'done.\nSaving model to {model_file_loc}...',
                end='',
                flush=True,
            )

        with open(model_file_loc, 'wb') as f:
            pickle.dump(model, f)

        if args['verbose']:
            print('done.')

    # Example test statistic object
    ts = mla.LLHTestStatistic([
        mla.SpatialTerm(),
        mla.TimeTerm(
            background_time_profile=copy.deepcopy(uniform_profile),
            signal_time_profile=copy.deepcopy(uniform_profile),
        ),
        mla.I3EnergyTerm(gamma=-2),
    ])

    # Put it all together into an analysis object
    analysis = mla.Analysis(
        model=model,
        test_statistic=ts,
        source=source,
    )

    unittest.main()
