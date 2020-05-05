
import os.path
from urllib.parse import urlparse


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
