"""
Filters the given signals between a highpass and a lowpass frequency using
a butterworth filter.
"""
import argparse
import quantities as pq
import os
from elephant.signal_processing import butter
from utils import load_neo, write_neo, none_or_float
from prov_utils import AnalysisProvenanceRecorder


def main(args):
    block = load_neo(args.data)

    asig = butter(block.segments[0].analogsignals[0],
                  highpass_freq=args.highpass_freq*pq.Hz,
                  lowpass_freq=args.lowpass_freq*pq.Hz,
                  order=args.order,
                  filter_function=args.filter_function)

    asig.array_annotations = block.segments[0].analogsignals[0].array_annotations

    asig.name += ""
    asig.description += "Frequency filtered with [{}, {}]Hz order {} "\
                        .format(args.highpass_freq,
                                args.lowpass_freq,
                                args.order)\
                      + " using {} scipy algorithm.({}). "\
                        .format(args.filter_function,
                                os.path.basename(__file__))
    block.segments[0].analogsignals[0] = asig

    write_neo(args.output, block)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data",    nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output",  nargs='?', type=str, required=True,
                     help="path of output file")
    CLI.add_argument("--highpass_freq", nargs='?', type=none_or_float,
                     default=None, help="lower bound of frequency band in Hz")
    CLI.add_argument("--lowpass_freq", nargs='?', type=none_or_float,
                     default=None, help="upper bound of frequency band in Hz")
    CLI.add_argument("--order", nargs='?', type=int, default=2,
                     help="order of the filter function")
    CLI.add_argument("--filter_function", nargs='?', type=str, default='filtfilt',
                     help="filterfunction used in the scipy backend")
    args = CLI.parse_args()


    prov_recorder = AnalysisProvenanceRecorder(
        script_name=__file__,
        description=("Filters the given signals between a highpass and a lowpass"
                     " frequency using a butterworth filter."),
        input_data=args.data,
        outputs=[{
            "path": args.output,
            "data_type": "Multi-channel ECoG with annotations",
            "file_type": "NIX:Neo",
            "description": "Band-pass filtered recording"
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs())
    )

    prov_recorder.capture(main, args)
