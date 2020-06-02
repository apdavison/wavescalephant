import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import os
import random
from utils import load_neo, save_plot, time_slice
from prov_utils import AnalysisProvenanceRecorder


def plot_traces(original_asig, processed_asig, channel):
    sns.set(style='ticks', palette="deep", context="notebook")
    fig, ax1 = plt.subplots()
    palette = sns.color_palette()

    ax1.plot(original_asig.times,
            original_asig.as_array()[:,args.channel],
            color=palette[0])
    ax1.set_ylabel('original signal', color=palette[0])
    ax1.tick_params('y', colors=palette[0])

    ax2 = ax1.twinx()
    ax2.plot(processed_asig.times,
            processed_asig.as_array()[:,args.channel],
            color=palette[1])
    ax2.set_ylabel('processed signal', color=palette[1])
    ax2.tick_params('y', colors=palette[1])

    ax1.set_title('Channel {}'.format(args.channel))
    ax1.set_xlabel('time [{}]'.format(original_asig.times.units.dimensionality.string))

    return ax1, ax2


def main(args):
    orig_asig = load_neo(args.original_data, 'analogsignal', lazy=True)
    orig_asig = time_slice(orig_asig, t_start=args.t_start, t_stop=args.t_stop,
                           lazy=True, channel_indexes=args.channel)

    proc_asig = load_neo(args.processed_data, 'analogsignal', lazy=True)
    proc_asig = time_slice(proc_asig, t_start=args.t_start, t_stop=args.t_stop,
                           lazy=True, channel_indexes=args.channel)

    plot_traces(orig_asig, proc_asig, args.channel)

    save_plot(args.output)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--original_data", nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--processed_data", nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output",  nargs='?', type=str, required=True,
                     help="path of output figure")
    CLI.add_argument("--t_start", nargs='?', type=float, default=0,
                     help="start time in seconds")
    CLI.add_argument("--t_stop",  nargs='?', type=float, default=10,
                     help="stop time in seconds")
    CLI.add_argument("--channel", nargs='?', type=int, default=0,
                     help="channel to plot")
    args = CLI.parse_args()

    prov_recorder = AnalysisProvenanceRecorder(
        script_name=__file__,
        description="Plot processed trace vs original trace.",
        input_data=(args.original_data, args.processed_data),
        outputs=[{
            "path": args.output,
            "data_type": "Figure",
            "file_type": "application/png",
            "description": "Plot of processed trace vs original trace"
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs())
    )

    prov_recorder.capture(main, args)
