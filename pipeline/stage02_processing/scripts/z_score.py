import argparse
from elephant.signal_processing import zscore
from utils import load_neo, write_neo
from prov_utils import AnalysisProvenanceRecorder


def main(args):
    block = load_neo(args.data)
    zscore(block.segments[0].analogsignals[0], inplace=True
    write_neo(args.output, block)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data", nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output",  nargs='?', type=str, required=True,
                     help="path of output file")

    args = CLI.parse_args()

    prov_recorder = AnalysisProvenanceRecorder(
        script_name=__file__,
        description="z-score",
        input_data=args.data,
        outputs=[{
            "path": args.output,
            "data_type": "z-score signal??",
            "file_type": "NIX:Neo",
            "description": "z-score signal??"
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs())
    )

    prov_recorder.capture(main, args)
