
import os.path
from urllib.parse import urlparse
from datetime import datetime
import json

from fairgraph.client import KGClient
from fairgraph.core import Person
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
        url_fragments = remote_url.split(':')
        print(url_fragments)
        assert len(url_fragments) == 2, "Invalid github url " + remote_url
        remote_url = "https://github.com/" + url_fragments[1].replace('.git', '')
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


def store_provenance_metadata(
        client,
        analysis_label,
        analysis_script_name,
        analysis_description,
        output_path,
        output_data_type,
        output_file_type,
        output_description,
        code_licence,
        config,
        start_timestamp,
        file_store,
        input_data,
    ):

    user = Person.me(client)
    end_timestamp = datetime.fromtimestamp(os.path.getmtime(output_path))
    version, remote_url = get_version("origin")

    script = AnalysisScript(
        name=f"{analysis_script_name}@{version}",
        script_file=remote_url,
        code_format="Python",
        license=code_licence
    )
    print(script)

    output_dir = os.path.dirname(output_path)
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

    output_file_url = file_store.get_uri(output_path)

    result = AnalysisResult(  # could instead/also use Multitrace object?
        name=f"{output_data_type}, generated from {input_data.id}, in {output_file_type} format at {start_timestamp.isoformat()}",
        description=output_description,
        result_file=output_file_url,
        #data_type=output_file_type,
        attributed_to=user,
        derived_from=input_data,
        timestamp=end_timestamp)
    print(result)

    activity = Analysis(
        name=f"{analysis_label} run by {user.full_name} at {start_timestamp.isoformat()}",
        description=analysis_description,
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