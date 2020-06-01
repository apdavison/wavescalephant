import numpy as np
from elephant.signal_processing import hilbert
import argparse
import os
from utils import load_neo, write_neo
from prov_utils import (setup_prov_recording, retrieve_input_data,
                        store_provenance_metadata)


def main(args):
    block = load_neo(args.data)

    phase = np.angle(hilbert(block.segments[0].analogsignals[0]).as_array())

    asig = asig.duplicate_with_new_data(phase)
    asig.array_annotations = **block.segments[0].analogsignals[0].array_annotations

    asig.name += ""
    asig.description += "Phase signal ({}). "\
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
    args = CLI.parse_args()


    start_timestamp, client, file_store = setup_prov_recording()
    input_data = retrieve_input_data(client, file_store, args.data)

    main(args)

    analysis_label, ext = os.path.splitext(os.path.basename(__file__))
    store_provenance_metadata(
        client,
        analysis_label=analysis_label,
        analysis_script_name=__file__,
        analysis_description=f"Calculate phase signal.",
        outputs=[{
            "path": args.output,
            "data_type": "Phase",
            "file_type": "NIX:Neo",
            "description": f"Phase signal."
        }],
        code_licence="GNU General Public License v3.0",
        config=dict(args._get_kwargs()),
        start_timestamp=start_timestamp,
        file_store=file_store,
        input_data=input_data,
    )