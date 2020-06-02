"""
Divides all signals by their max/mean/median value.
"""
import numpy as np
import argparse
import neo
import os
import sys
from utils import write_neo, load_neo
from prov_utils import AnalysisProvenanceRecorder


def normalize(asig, normalize_by):
    if normalize_by == 'median':
        norm_function = np.median
    elif normalize_by == 'max':
        norm_function = np.max
    elif normalize_by == 'mean':
        norm_function = np.mean
    else:
        raise InputError("The method to normalize by is not recognized. "\
                       + "Please choose either 'mean', 'median', or 'max'.")

    dim_t, num_channels = asig.shape
    norm_asig = asig.as_array()
    for i in range(num_channels):
        norm_value = norm_function(norm_asig[:,i])
        if norm_value:
            norm_asig[:,i] /= norm_value
        else:
            print("Normalization factor is {} for channel {} "\
                  .format(nom_value, i) + "and was skipped.")
    for num in range(dim_t):
        asig[num] = norm_asig[num]
    del norm_asig
    return asig


def main(args):
    block = load_neo(args.data)

    asig = normalize(block.segments[0].analogsignals[0], args.normalize_by)

    asig.name += ""
    asig.description += "Normalized by {} ({})."\
                        .format(args.normalize_by, os.path.basename(__file__))
    block.segments[0].analogsignals[0] = asig

    write_neo(args.output, block)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data",    nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output",  nargs='?', type=str, required=True,
                     help="path of output file")
    CLI.add_argument("--normalize_by", nargs='?', type=str, default='mean',
                     help="division factor: 'max', 'mean', or 'median'")
    args = CLI.parse_args()

    prov_recorder = AnalysisProvenanceRecorder(
        script_name=__file__,
        description=f"Divides all signals by their {args.normalize_by} value.",
        input_data=args.data,
        outputs=[{
            "path": args.output,
            "data_type": "Multi-channel ECoG with annotations",
            "file_type": "NIX:Neo",
            "description": f"Signals divided by their {args.normalize_by} value."
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs())
    )

    prov_recorder.capture(main, args)
