"""

"""

import os
from time import sleep
import numpy as np
import argparse
from datetime import datetime, timedelta
import json
import matplotlib.pyplot as plt
import seaborn as sns
import quantities as pq
import random
from utils import load_neo, save_plot, time_slice, parse_plot_channels,\
                  none_or_int

from prov_utils import get_version, SeafileDataStore

from fairgraph.client import KGClient
from fairgraph.base import KGQuery
from fairgraph.core import Person
from fairgraph.analysis import AnalysisScript, Analysis, AnalysisResult, AnalysisConfiguration
Person.namespace = Analysis.namespace


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

    start_timestamp = datetime.now()
    client = KGClient()
    user = Person.me(client)

    file_store = SeafileDataStore(
        base_dir="/Users/andrew/Seafile/My Library",
        server_url="https://drive.ebrains.eu",
        username="adavison")  # todo: take all of these from settings
    input_data_uri = file_store.get_uri(args.data)

    print(f"\n**** {args.data} ****\n")
    print(f"\n**** {input_data_uri} ****\n")

    sleep(30)  # to allow the KG to become consistent
    candidate_data_objects = KGQuery(AnalysisResult,
                                     {"nexus": {
                                         'path': 'schema:distribution / schema:downloadURL',
                                         'op': 'eq',
                                         'value': input_data_uri
                                         }
                                     }, {}).resolve(client, api="nexus")
    input_data_timestamp = datetime.fromtimestamp(os.path.getmtime(args.data))
    min_delta = timedelta(days=1)
    selected_input_data_object = None
    for obj in candidate_data_objects:
        delta = input_data_timestamp - obj.timestamp  # may not be zero due to "check_input" step, which touches the output file and so changes the mtime
        if delta < min_delta:
            min_delta = delta
            selected_input_data_object = obj
    if selected_input_data_object is None:
        raise Exception("Matching input data file not found")
    if min_delta > timedelta(seconds=120):
        raise Exception(f"Mismatched timestamps: {input_data_timestamp} and {selected_input_data_object.timestamp}")

    main(args)

    # === Now store provenance metadata in KG ===
    end_timestamp = datetime.fromtimestamp(os.path.getmtime(args.output))
    #end_timestamp = datetime.now()
    version, remote_url = get_version("origin")

    script = AnalysisScript(
        name=f"plot_traces.py@{version}",
        script_file=remote_url,
        code_format="Python",
        license="GNU General Public License v3.0"
    )
    print(script)

    config = dict(args._get_kwargs())
    output_dir = os.path.dirname(args.output)
    config_file = os.path.join(output_dir,
                               f"config_plot_traces_{start_timestamp.isoformat()}.json")
    with open(config_file, "w") as fp:
        json.dump(config, fp, indent=4)
    # write config to JSON file, then store that file (in Seafile?) and get URL
    # alternatively, could store copy of snakemake config file used for this step

    config = AnalysisConfiguration(
        name=f"config for plot_traces run by {user.full_name} at {start_timestamp.isoformat()}",
        description="command-line arguments",
        config_file=config_file)
    print(config)

    output_file_url = file_store.get_uri(args.output)

    result = AnalysisResult(  # could instead/also use Multitrace object?
        name=f"Figure plotted from {selected_input_data_object.id}, in PNG format at {start_timestamp.isoformat()}",
        description="Plot of pre-processed input data",
        result_file=output_file_url,
        #data_type="application/png",
        #generated_by=activity,
        attributed_to=user,
        derived_from=selected_input_data_object,
        timestamp=end_timestamp)
    print(result)

    activity = Analysis(
        name=f"plot_traces run by {user.full_name} at {start_timestamp.isoformat()}",
        description="Plot pre-processed datafiles",
        input_data=selected_input_data_object,
        script=script,
        config=config,
        timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        result=result,
        started_by=user)
    print(activity)

    script.save(client)
    config.save(client)
    result.save(client)
    activity.save(client)
    result.generated_by = activity
    result.save(client)
