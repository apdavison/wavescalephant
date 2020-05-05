import numpy as np
import argparse
import quantities as pq
import re
import os
import sys
from datetime import datetime
import json
import neo
from utils import load_neo, write_neo, none_or_float, none_or_str, time_slice,\
                  parse_string2dict

from fairgraph.client import KGClient
from fairgraph.minds import Dataset
from fairgraph.core import Person
from fairgraph.electrophysiology import MultiChannelMultiTrialRecording
from fairgraph.analysis import AnalysisScript, Analysis, AnalysisResult, AnalysisConfiguration

from prov_utils import get_version, SeafileDataStore

# fairgraph settings
#Person.namespace = MultiChannelMultiTrialRecording.namespace
Person.namespace = Analysis.namespace
###MultiChannelMultiTrialRecording._path = "/electrophysiology/multitrace/v0.1.2"
MultiChannelMultiTrialRecording.set_strict_mode(False, "generated_by")


def merge_analogsingals(asigs):
    min_length = np.min([len(asig.times) for asig in asigs])
    max_length = np.max([len(asig.times) for asig in asigs])
    if min_length != max_length:
        print('Warning: the length of the analog signals differs '\
            + 'between {} and {} '.format(min_length, max_length)\
            + 'All signals will be cut to the same length and merged '\
            + 'into one AnalogSignal object.')

    if len(np.unique([asig.sampling_rate for asig in asigs])) > 1:
        raise ValueError('The AnalogSignal objects have different '\
                       + 'sampling rates!')

    asig_array = np.zeros((min_length, len(asigs)))

    for channel_number, asig in enumerate(asigs):
        asig_array[:, channel_number] = np.squeeze(asig.as_array()[:min_length])

    merged_asig = neo.AnalogSignal(asig_array*asigs[0].units,
                                sampling_rate=asigs[0].sampling_rate,
                                t_start=asigs[0].t_start)
    for key in asigs[0].annotations.keys():
        try:
            merged_asig.array_annotations[key] = np.array([a.annotations[key]
                                                           for a in asigs])
        except:
            print('Can not merge annotation ', key)
    return merged_asig


def main(args):
    try:
        block = load_neo(args.data, try_signal_grouping=True)
    except Exception as e:
        print(e)
        block = load_neo(args.data, try_signal_grouping=False)

    asigs = block.segments[0].analogsignals

    if len(asigs) > 1:
        print(f'Merging {len(asigs)} AnalogSignals into one.')
        asig = merge_analogsingals(asigs)
    else:
        asig = asigs[0]

    asig = time_slice(asig, args.t_start, args.t_stop)

    # add metadata
    kwargs = parse_string2dict(args.kwargs)

    channels = asig.array_annotations[kwargs['ELECTRODE_ANNOTATION_NAME']]

    coords = np.array([kwargs['NAME2COORDS'][str(channel)] for channel in channels.astype(int)])
    asig.array_annotations.update(x_coords=coords[:,0])
    asig.array_annotations.update(y_coords=coords[:,1])

    # locations = []
    # for channel in channels:
    #     locations.append([loc for loc in kwargs['ELECTRODE_LOCATION'].keys()
    #                       if channel in kwargs['ELECTRODE_LOCATION'][loc]][0])
    # asig.array_annotations.update(electrode_location=locations)

    # colors = [kwargs['ELECTRODE_COLOR'][loc] for loc in
    #           asig.array_annotations['electrode_location']]
    # asig.array_annotations.update(electrode_color=colors)

    asig.annotations.update(parse_string2dict(args.annotations))
    asig.annotations.update(spatial_scale=args.spatial_scale*pq.mm)

    # dim_t, channel_num = asig.as_array().shape
    # chidx = neo.ChannelIndex(name=asig.name,
    #                          channel_ids=np.arange(channel_num),
    #                          index=np.arange(channel_num),
    #                          coordinates=coords*args.spatial_scale*pq.mm)
    # chidx.annotations.update(asig.array_annotations)

    block.name = args.data_name
    block.segments[0].name = 'Segment 1'
    block.segments[0].description = 'Loaded with neo.Spike2IO (neo version {})'\
                                    .format(neo.__version__)
    if asig.description is None:
        asig.description = ''
    asig.description += 'ECoG signal. '

    block.segments[0].analogsignals = [asig]

    # block.channel_indexes.append(chidx)
    # block.segments[0].analogsignals[0].channel_index = chidx
    # chidx.analogsignals.append(asig)
    block.channel_indexes = []

    write_neo(args.output, block)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data", nargs='?', type=str, required=True,
                     help="path to input data")
    CLI.add_argument("--output", nargs='?', type=str, required=True,
                     help="path of output file")
    CLI.add_argument("--sampling_rate", nargs='?', type=none_or_float,
                     default=None, help="sampling rate in Hz")
    CLI.add_argument("--spatial_scale", nargs='?', type=float, required=True,
                     help="distance between electrodes or pixels in mm")
    CLI.add_argument("--data_name", nargs='?', type=str, default='None',
                     help="chosen name of the dataset")
    CLI.add_argument("--t_start", nargs='?', type=none_or_float, default=None,
                     help="start time in seconds")
    CLI.add_argument("--t_stop",  nargs='?', type=none_or_float, default=None,
                     help="stop time in seconds")
    CLI.add_argument("--annotations", nargs='+', type=none_or_str, default=None,
                     help="metadata of the dataset")
    CLI.add_argument("--array_annotations", nargs='+', type=none_or_str,
                     default=None, help="channel-wise metadata")
    CLI.add_argument("--kwargs", nargs='+', type=none_or_str, default=None,
                     help="additional optional arguments")
    args = CLI.parse_args()

    # === Get data and metadata from KG ===

    start_timestamp = datetime.now()

    client = KGClient()  # expects environment variable HBP_AUTH_TOKEN
                         # token can be obtained from https://nexus-iam.humanbrainproject.org/v0/oauth2/authorize

    user = Person.me(client)
    # todo: move dataset name or id to config
    dataset_name = "Cortical activity features in transgenic mouse models of cognitive deficits (Williams Beuren Syndrome)"
    dataset = Dataset.by_name(dataset_name, client, resolved=True)

    # get list of traces belonging to the dataset
    traces = MultiChannelMultiTrialRecording.list(client,
                                                  part_of=dataset,
                                                  api="nexus",
                                                  use_cache=False,
                                                  size=10000)

    # extract trace that matches the input filename
    #   todo: specify either the MCMTR object id in DATA_SETS, rather than hard-coding the URL,
    #         or specify filters to be applied to the trace query (e.g. wild-type, V1, ...)
    input_data = None
    for trace in traces:
        if os.path.basename(args.data) in trace.data_location.location:
            input_data = trace
            print(input_data)
            break
    if input_data is None:
        raise Exception("Data file not found in Knowledge Graph")


    # === Run the actual pre-processing ===
    main(args)


    # === Now store provenance metadata in KG ===
    end_timestamp = datetime.fromtimestamp(os.path.getmtime(args.output))
    #end_timestamp = datetime.now()
    version, remote_url = get_version("origin")

    script = AnalysisScript(
        name=f"curate_IDIBAPS_data.py@{version}",
        script_file=remote_url,
        code_format="Python",
        license="GNU General Public License v3.0"
    )
    print(script)

    config = dict(args._get_kwargs())
    output_dir = os.path.dirname(args.output)
    config_file = os.path.join(output_dir,
                               f"config_curate_IDIBAPS_data_{start_timestamp.isoformat()}.json")
    with open(config_file, "w") as fp:
        json.dump(config, fp, indent=4)
    # write config to JSON file, then store that file (in Seafile?) and get URL
    # alternatively, could store copy of snakemake config file used for this step

    config = AnalysisConfiguration(
        name=f"config for curate_IDIBAPS_data run by {user.full_name} at {start_timestamp.isoformat()}",
        description="command-line arguments",
        config_file=config_file)
    print(config)

    output_store = SeafileDataStore(
        base_dir="/Users/andrew/Seafile/My Library",
        server_url="https://drive.ebrains.eu",
        username="adavison")  # todo: take all of these from settings
    nix_file_url = output_store.get_uri(args.output)

    result = AnalysisResult(  # could instead/also use Multitrace object?
        name=f"Multi-channel ECoG with annotations, constructed from {input_data.name}, in NIX:Neo format at {start_timestamp.isoformat()}",
        description="NIX file contains a single block containing a single segment containing a single analog signal",
        result_file=nix_file_url,
        #data_type="NIX:Neo",
        #generated_by=activity,
        attributed_to=user,
        derived_from=input_data,
        timestamp=end_timestamp)
    print(result)

    activity = Analysis(
        name=f"curate_IDIBAPS_data run by {user.full_name} at {start_timestamp.isoformat()}",
        description="preprocess datafiles, to convert them into the format needed for subsequent steps, and add necessary annotations",
        input_data=input_data,
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


"""
Example Seafile links obtained from Desktop client
https://drive.ebrains.eu/f/076de9c19e0c4447a95e/
https://drive.ebrains.eu/f/076de9c19e0c4447a95e/?dl=1
"""
