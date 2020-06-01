"""
Subtract the background of a given dataset by subtracting the mean of each channel.
"""
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
from utils import determine_spatial_scale, load_neo, write_neo, save_plot, \
                  none_or_str
from prov_utils import (setup_prov_recording, retrieve_input_data,
                        store_provenance_metadata)


def substract_background(asig, background):
    for num, frame in enumerate(asig):
        asig[num] = frame - background
    return asig


def shape_frame(value_array, coords):
    dim_x = np.max(coords[:,0]) + 1
    dim_y = np.max(coords[:,1]) + 1
    frame = np.empty((dim_x, dim_y)) * np.nan
    for pixel, xy in zip(value_array, coords):
        frame[int(xy[0]), int(xy[1])] = pixel
    return frame


def plot_frame(frame):
    fig, ax = plt.subplots()
    ax.imshow(frame, interpolation='nearest', cmap=plt.cm.gray)
    ax.axis('image')
    ax.set_xticks([])
    ax.set_yticks([])
    return ax


def main(args):
    block = load_neo(args.data)
    asig = block.segments[0].analogsignals[0]

    background = np.mean(asig, axis=0)

    asig = substract_background(asig, background)

    if args.output_img or args.output_array is not None:
        coords = np.array([(x,y) for x,y in
                           zip(asig.array_annotations['x_coords'],
                               asig.array_annotations['y_coords'])],
                          dtype=int)
        frame = shape_frame(background, coords)
        if args.output_array is not None:
            np.save(args.output_array, frame)
        if args.output_img is not None:
            plot_frame(frame)
            save_plot(args.output_img)

    asig.name += ""
    asig.description += "The mean of each channel was subtracted ({})."\
                        .format(os.path.basename(__file__))
    block.segments[0].analogsignals[0] = asig

    write_neo(args.output, block)


if __name__ == '__main__':
    CLI = argparse.ArgumentParser(description=__doc__,
                   formatter_class=argparse.RawDescriptionHelpFormatter)
    CLI.add_argument("--data",    nargs='?', type=str, required=True,
                     help="path to input data in neo format")
    CLI.add_argument("--output",  nargs='?', type=str, required=True,
                     help="path of output file")
    CLI.add_argument("--output_img",  nargs='?', type=none_or_str,
                     help="path of output image", default=None)
    CLI.add_argument("--output_array",  nargs='?', type=none_or_str,
                      help="path of output numpy array", default=None)
    args = CLI.parse_args()

    start_timestamp, client, file_store = setup_prov_recording()

    input_data = retrieve_input_data(client, file_store, args.data)

    main(args)

    analysis_label, ext = os.path.splitext(os.path.basename(__file__))
    outputs=[{
        "path": args.output,
        "data_type": "Multi-channel ECoG with annotations",
        "file_type": "NIX:Neo",
        "description": "Recording with background subtracted."
    }]
    if args.output_array is not None:
        outputs.append({
            "path": args.output_array,
            "data_type": "Frame array",
            "file_type": "numpy-binary",
            "description": "Frame used for background subtraction"
        })
    if args.output_img is not None:
        outputs.append({
            "path": args.output_img,
            "data_type": "Figure",
            "file_type": "application/png",
            "description": "Figure showing background subtraction"
        })

    store_provenance_metadata(
        client,
        analysis_label=analysis_label,
        analysis_script_name=__file__,
        analysis_description="Subtract the background of a given dataset by subtracting the mean of each channel.",
        outputs=outputs,
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs()),
        start_timestamp=start_timestamp,
        file_store=file_store,
        input_data=input_data,
    )