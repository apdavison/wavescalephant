"""

"""

import os
from time import sleep
import numpy as np
import argparse
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import seaborn as sns
import quantities as pq
import random
from utils import load_neo, save_plot, time_slice, parse_plot_channels,\
                  none_or_int

from prov_utils import (setup_prov_recording, retrieve_input_data,
                        store_provenance_metadata)


def plot_traces(asig, channels):
    sns.set(style='ticks', palette="deep", context="notebook")
    fig, ax = plt.subplots()

    offset = np.max(np.abs(asig.as_array()[:,channels]))

    for i, signal in enumerate(asig.as_array()[:,channels].T):
        ax.plot(asig.times, signal + i*offset)

    annotations = [f'{k}: {v}' for k,v in asig.annotations.items()
                               if k not in ['nix_name', 'neo_name']]
    array_annotations = [f'{k}: {v[channels]}'
                        for k,v in asig.array_annotations.items()]

    ax.text(ax.get_xlim()[1]*1.05, ax.get_ylim()[0],
            f'ANNOTATIONS FOR CHANNEL(s) {channels} \n'\
            + '\n ANNOTATIONS:\n' + '\n'.join(annotations) \
            + '\n\n ARRAY ANNOTATIONS:\n' + '\n'.join(array_annotations))

    ax.set_xlabel(f'time [{asig.times.units.dimensionality.string}]')
    ax.set_ylabel(f'channels [in {asig.units.dimensionality.string}]')
    ax.set_yticks([i*offset for i in range(len(channels))])
    ax.set_yticklabels(channels)
    return fig


def main(args):
    asig = load_neo(args.data, 'analogsignal', lazy=True)
    channels = parse_plot_channels(args.channels, args.data)
    asig = time_slice(asig, t_start=args.t_start, t_stop=args.t_stop,
                      lazy=True, channel_indexes=channels)
    fig = plot_traces(asig, channels)
    save_plot(args.output)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data",    nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output",  nargs='?', type=str, required=True,
                     help="path of output figure")
    CLI.add_argument("--t_start", nargs='?', type=float, default=0,
                     help="start time in seconds")
    CLI.add_argument("--t_stop",  nargs='?', type=float, default=10,
                     help="stop time in seconds")
    CLI.add_argument("--channels", nargs='+', type=none_or_int, default=0,
                     help="list of channels to plot")
    args = CLI.parse_args()

    start_timestamp, client, file_store = setup_prov_recording()
    input_data = retrieve_input_data(client, file_store, args.data)

    # === Plot the figure ===
    main(args)

    # === Now store provenance metadata in KG ===

    analysis_label, ext = os.path.splitext(os.path.basename(__file__))

    store_provenance_metadata(
        client,
        analysis_label=analysis_label,
        analysis_script_name=__file__,
        analysis_description="Plot pre-processed datafiles",
        outputs=[{
            "path": args.output,
            "data_type": "Figure",
            "file_type": "application/png",
            "description": "Plot of pre-processed input data"
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs()),
        start_timestamp=start_timestamp,
        file_store=file_store,
        input_data=input_data,
    )
