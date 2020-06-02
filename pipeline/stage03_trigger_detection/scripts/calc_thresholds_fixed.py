import neo
import numpy as np
import argparse
from utils import load_neo
from prov_utils import AnalysisProvenanceRecorder


def main(args):
    asig = load_neo(args.data, 'analogsignal')

    dim_t, channel_num = asig.shape

    np.save(args.output, np.ones(channel_num) * args.threshold)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data", nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output", nargs='?', type=str, required=True,
                     help="path of output thresholds (numpy array)")
    CLI.add_argument("--threshold", nargs='?', type=float, required=True)
    args = CLI.parse_args()

    prov_recorder = AnalysisProvenanceRecorder(
        script_name=__file__,
        description=f"Create array of fixed thresholds ({args.threshold})",
        input_data=args.data,
        outputs=[{
            "path": args.output,
            "data_type": "Per-channel thresholds",
            "file_type": "NumPy binary",
            "description": f"Array of per-channel thresholds"
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs())
    )

    prov_recorder.capture(main, args)
