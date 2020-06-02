
import os.path
from urllib.parse import urlparse
from datetime import datetime, timedelta
from time import sleep
import json
import hashlib

from fairgraph.client import KGClient
from fairgraph.base import as_list, KGQuery
from fairgraph.core import Person
from fairgraph.minds import Dataset
from fairgraph.analysis import AnalysisScript, Analysis, AnalysisResult, AnalysisConfiguration
from fairgraph.electrophysiology import MultiChannelMultiTrialRecording

Person.namespace = Analysis.namespace
MultiChannelMultiTrialRecording.set_strict_mode(False, "generated_by")

def get_version(remote_name="origin"):  # move to utils.py?
    import git
    repo = git.Repo(search_parent_directories=True)
    sha = repo.head.object.hexsha
    remote_url = list(repo.remote(remote_name).urls)[0]
    # convert git@ URLs to https
    if remote_url.startswith("git"):
        url_fragments = remote_url.split(":")
        print(url_fragments)
        assert len(url_fragments) == 2, "Invalid github url " + remote_url
        remote_url = "https://github.com/" + url_fragments[1].replace(".git", "")
    relative_path = os.path.relpath(__file__, repo.working_dir)
    remote_file_url = f"{remote_url}/blob/{sha}/{relative_path}"
    # todo: check if repo is "dirty", get the diff if so
    return sha, remote_file_url


class SeafileDataStore:

    def __init__(self, base_dir, server_url, username):
        self.base_dir = base_dir
        self.server_url = server_url
        self.username = username

    def get_uri(self, path):
        relative_path = os.path.relpath(path, self.base_dir)
        server_name = urlparse(self.server_url).netloc
        #return f"seafile://{self.username}@{server_name}/{relative_path}"
        return f"https://seafile-proxy.brainsimulation.eu/{relative_path}?username={self.username}&server_name={server_name}"


def setup_prov_recording():
    start_timestamp = datetime.now()
    client = KGClient()  # expects environment variable HBP_AUTH_TOKEN
                         # token can be obtained from https://nexus-iam.humanbrainproject.org/v0/oauth2/authorize

    file_store = SeafileDataStore(
        base_dir="/Users/andrew/Seafile/My Library",
        server_url="https://drive.ebrains.eu",
        username="adavison")  # todo: take all of these from settings

    return start_timestamp, client, file_store


def retrieve_input_data(client, file_store, file_path, cls=AnalysisResult):

    input_data_uri = file_store.get_uri(os.path.realpath(file_path))  # resolve symlinks
    digest = file_hash(file_path)

    sleep(30)  # to allow the KG to become consistent. TODO: first try without sleep, retry after sleep on failure
    context = {}
    query = {
        "nexus": {
            "op": "and",
            "value": [
                {
                    "path": "schema:distribution / schema:downloadURL",
                    "op": "eq",
                    "value": input_data_uri
                },
                {
                    "path": "schema:distribution / nxv:digest / schema:value",
                    "op": "eq",
                    "value": digest
                }
            ]
        }
    }
    ## input_data = KGQuery(cls, query, context).resolve(client, api="nexus")
    ## if not input_data:
    ##    raise Exception(f"Matching input data file not found (file_path: {file_path}, digest: {digest})")
    # the above query doesn't work as expected, so use a more brute-force method
    query = {
        "nexus": {
            "path": "schema:distribution / schema:downloadURL",
            "op": "eq",
            "value": input_data_uri
        }
    }
    candidate_data_objects = KGQuery(cls, query, context).resolve(client, api="nexus")
    candidate_data_objects = [obj for obj in as_list(candidate_data_objects)
                              if obj.result_file.digest == digest]
    if len(candidate_data_objects) == 0:
        raise Exception(f"Matching input data file not found (file_path: {file_path}, digest: {digest})")
    candidate_data_objects.sort(key=lambda obj: obj.timestamp)
    input_data = candidate_data_objects[-1]
    return input_data


def retrieve_input_data_from_dataset(client, dataset_name, file_path):
    # todo: move dataset name or id to config
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
        if os.path.basename(file_path) in trace.data_location.location:
            input_data = trace
            print(input_data)
            break
    if input_data is None:
        raise Exception("Data file not found in Knowledge Graph")
    return input_data


def store_provenance_metadata(
        client,
        analysis_label,
        analysis_script_name,
        analysis_description,
        outputs,
        code_licence,
        config,
        start_timestamp,
        file_store,
        input_data,
    ):

    user = Person.me(client)
    version, remote_url = get_version("origin")

    script = AnalysisScript(
        name=f"{analysis_script_name}@{version}",
        script_file=remote_url,
        code_format="Python",
        license=code_licence
    )
    print(script)

    output_dir = os.path.dirname(outputs[0]["path"])
    config_file = os.path.join(output_dir,
                               f"config_{analysis_label}_{start_timestamp.isoformat()}.json")
    with open(config_file, "w") as fp:
        json.dump(config, fp, indent=4)
    # write config to JSON file, then store that file (in Seafile?) and get URL
    # alternatively, could store copy of snakemake config file used for this step

    config = AnalysisConfiguration(
        name=f"config for {analysis_label} run by {user.full_name} at {start_timestamp.isoformat()}",
        description="command-line arguments",
        config_file=config_file)
    print(config)

    input_ids = ", ".join([inp.id for inp in as_list(input_data)])
    results = []
    for output in outputs:
        output_file_url = file_store.get_uri(os.path.realpath(output["path"]))  # resolve symlinks
        end_timestamp = datetime.fromtimestamp(os.path.getmtime(output["path"]))

        result = AnalysisResult(  # could instead/also use Multitrace object?
            name=f"{output['data_type']}, generated from {input_ids}, in {output['file_type']} format at {start_timestamp.isoformat()}",
            description=output["description"],
            result_file=output_file_url,
            #data_type=output_file_type,
            attributed_to=user,
            derived_from=input_data,
            timestamp=end_timestamp)
        result.result_file.digest = file_hash(output["path"])  # todo: move this to fairgraph
        result.result_file.digest_method = "SHA-1"
        print(result)
        results.append(result)

    activity = Analysis(
        name=f"{analysis_label} run by {user.full_name} at {start_timestamp.isoformat()}",
        description=analysis_description,
        input_data=input_data,
        script=script,
        config=config,
        timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        result=results,
        started_by=user)
    print(activity)

    script.save(client)
    config.save(client)
    for result in results:
        result.save(client)
    activity.save(client)
    for result in results:
        result.generated_by = activity
        result.save(client)


def file_hash(file_path):

    BUFFER_SIZE = 1048576  # 1 MB
    fh = hashlib.sha1()

    with open(file_path, "rb") as fp:
        buffer = fp.read(BUFFER_SIZE)
        while len(buffer) > 0:
            fh.update(buffer)
            buffer = fp.read(BUFFER_SIZE)
    return fh.hexdigest()


class AnalysisProvenanceRecorder:

    def __init__(self, script_name, description, input_data, outputs,
                 code_licence=None, config=None):
        self.script_name = script_name
        self.description = description
        self.input_data = input_data
        if isinstance(input_data, str):
            self.input_data = [input_data]
        self.outputs = outputs
        self.code_licence = code_licence
        self.config = config

    def capture(self, func, args):
        start_timestamp, client, file_store = setup_prov_recording()
        input_data = [
            retrieve_input_data(client, file_store, file_path)
            for file_path in self.input_data
        ]

        func(args)

        analysis_label, ext = os.path.splitext(os.path.basename(self.script_name))
        store_provenance_metadata(
            client,
            analysis_label=analysis_label,
            analysis_script_name=self.script_name,
            analysis_description=f"Plot processed trace vs original trace.",
            outputs=self.outputs,
            code_licence=self.code_licence,
            config=self.config,
            start_timestamp=start_timestamp,
            file_store=file_store,
            input_data=input_data,
        )