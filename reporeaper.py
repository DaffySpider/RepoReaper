import os
import subprocess
import requests
from multiprocessing import Pool, Manager
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, TaskProgressColumn 
import argparse
import sys
import time
import json
import tempfile
from pathlib import Path
import shlex
import shutil

def user_input():
    """
    Grabbing user input of Github Host and the number of repositories to be cloned
    """
    print("Choose Github host:")
    print("1. github.com")
    print("2. github.testdomain.com")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        host = "github.com"

    elif choice == "2":
        host = "github.testdomain.com"

    else:
        print("Invalid choice.")
        sys.exit(1)

    org = input("Enter the GitHub organisation name (e.g. For github.testdomain.com/testrepo, enter testrepo): ").strip()

    print("Do you want to clone all, multiple, or just one of the repository in the organisation?")
    print("1. All")
    print("2. Multiple")
    print("3. Just one")
    choice_repo = input("Enter 1, 2 or 3: "). strip()

    if choice_repo == "2":
        print("Please input a text file containing the list of repositories, separated by newlines. Please ensure that the name of the repositories are accurate (including the upper/lower case).")
        repo_location = input("Enter the file name/location: ").strip()
        if not os.path.exists(repo_location):
            print(f"Error: '{repo_location} does not exist.")
            sys.exit(1)
        else:
            return (host, org, False, repo_location, False)

    elif choice_repo == "3":
        repo_name = input("Please input the name of the repository (*This is case sensitive): ").strip()
        return (host, org, False, False, repo_name)

    elif choice_repo == "1":
        ALL = True
        return (host, org, True, False, False)

    else:
        print("Invalid Choice")
        sys.exit(1)


def zoomin_clone(repoz):
    """
    Cloning all those repos. This is running in parallel to speed things up. 
    """
    repo, clone_dir, host, counter, success = repoz
    full_name = repo["full_name"]
    clone_url = f"https://{host}/{full_name}"
    name = repo["name"]
    combine = os.path.join(clone_dir, name)

    try:
        clone = "gh repo clone %s %s" % (clone_url, combine)
        p_clone = subprocess.run(clone, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,)

    except subprocess.CalledProcessError:
        print(f"{RED}Failed to clone {full_name}{RESET}")

    else:
        success.append(full_name)

    finally:
        counter.value += 1           


def clone():
    """
    Main function to clone repos :)
    """
    host, org, ALL, repo_location, repo_name = user_input()

    env = os.environ.copy()
    env["GH_HOST"] = host

    try:
        print(f"\nChecking Github CLI auth for {host}...")
        status = "gh auth status --hostname %s" % (host)
        subprocess.run(status, shell=True, check=True)
    except subprocess.CalledProcessError:
        print(f"You are not authenticated with {host}. Please log in.")
        login = "gh auth login --hostname %s" % (host)
        subprocess.run(login, shell=True, check=True)
    print(f"Fetching repositories from organisation: {org} on {host}...")

    if ALL == True:
        try:
            api = "gh api /orgs/%s/repos --paginate --hostname %s" % (org, host)
            p_api = subprocess.run(api, shell=True, check=True, capture_output=True, text=True)
            repos = json.loads(p_api.stdout)
        except subprocess.CalledProcessError as e:
            print(f" Failed to fetch repositories:\n{e.stderr}")
            sys.exit(1)

    elif repo_location != False and repo_location:
        repos = []
        with open(repo_location, "r") as cs:
            for line in cs:
                name = line.strip()
                full_name = f"{org}/{name}"
                repos.append({"full_name": full_name, "name": name})

    elif repo_name != False and repo_name:
        full_name = f"{org}/{repo_name}"
        repos = [{"full_name": full_name, "name": repo_name}]

    # clone folders into ~./Documents
    home = os.path.expanduser("~")
    documents = os.path.join(home, "Documents")
    os.chdir(documents)
    clone_dir = f"./{org}_repos"
    os.makedirs(clone_dir, exist_ok=True)

    manager = Manager()
    counter = manager.Value('i', 0)
    success = manager.list()

    repo_list = [(repo, clone_dir, host, counter, success) for repo in repos] 

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Cloning repos...", total=len(repos))

            with Pool(4) as pool:
                results = []
                for repoz in repo_list:
                    result = pool.apply_async(zoomin_clone, (repoz,))
                    results.append(result)

                while any(not r.ready() for r in results):
                    progress.update(task, completed=counter.value)
                    time.sleep(0.5)

                for r in results:
                    r.wait()

                progress.update(task, completed=counter.value)

    if success:
        print(f"{GREEN}Successfully cloned the following repositories:{RESET}")
        for repo_name in success:
            print(f"{GREEN} - {repo_name}{RESET}")
        print()

    path = f"{documents}/{org}_repos/"

    return path

            
def find_git_repos(root_path='.'):
    """ 
    Iterates through path to count and list the number of git repos
    """
    git_repos = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        if '.git' in dirnames:
            git_repos.append(dirpath)
            # prevent walking into nested git repos
            dirnames.remove('.git')
    return git_repos


def extract_commit_files(commit_hash, dest_dir):
    """
    Extract all old files via commit id. Only extract the files that were modified and place them in /tmp.
    """
    os.chdir(repo_path)
    cmd = "git diff-tree --no-commit-id --name-only -r %s" % (commit_hash)
    git_ls = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    files = git_ls.stdout.strip().split('\n')

    for file_path in files:
        output_path = Path(dest_dir) / file_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path = shlex.quote(f"{commit_hash}:{file_path}")
        cmd = "git show %s" % (safe_path)
        git_s = subprocess.run(cmd, shell=True, capture_output=True)
        if git_s.returncode != 0:
#            print(f"Failed to extract {file_path}: {git_s.stderr.decode(errors='ignore')}")
            continue
        try:
            content = git_s.stdout.decode("utf-8")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

        except UnicodeDecodeError:
#            print(f"Skipping {file_path}: binary or non-UT-8 content.")
            pass


def scan_with_detect_secrets(scan_dir):
    """
    Run detect-secrets scan against the extracted files in commit history
    """
    os.chdir("/tmp")
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        output_path = temp.name

    if args.ninja_mode:
        cmd_detect = "detect-secrets scan --all-files --output-raw --output-verified-false --no-verify %s > %s" % (scan_dir, output_path)
    else:
        cmd_detect = "detect-secrets scan --all-files --output-raw --output-verified-false %s > %s" % (scan_dir, output_path)
    
    detect_p = subprocess.run(cmd_detect, shell=True, capture_output=True, text=True)

    try:
        with open(output_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}
    finally:
        os.remove(output_path)


def pretty_results(results):
    """
    Print out and save results in a prettier version :) Results are saved in CSV files.
    """
    for outer in results:
        for item in outer:
            commit_value = item.get("commit", "N/A")
            secrets = item.get("secrets", {})

            if isinstance(secrets, dict):
                for key, secrets_list in secrets.items():
                    if isinstance(secrets_list, list):
                        for secret in secrets_list:
                            # is_verified => are the secrets verified? Returns True or False
                            # verified_result => if the secrets are verified, are the secrets/keys valid? 
                            # ^ Returns True or False
                            if secret.get("verified_result") is True and secret.get("is_verified") is True:
                                print(f"Commit: {commit_value}")
                                print(f"    Filename: {key}")
                                print(f"    Secret: {RED}{secret.get('secret')}{RESET}")
                                print(f"    Type: {secret.get('type')}")
                                with open('verified.csv', 'a') as v:
                                    v.write(f"{commit_value}, {key}, {secret.get('secret')}, {secret.get('type')}\n")
                            else:
                                with open('not_verified.csv', 'a') as v2:
                                    v2.write(f"{commit_value}, {key}, {secret.get('secret')}, {secret.get('type')}\n")


def for_processing(commit_line):
    """
    For loop, iterating through all commits. These run asynchronously via pool.map_async to speed up the process.
    """
    temp_results = []
    commit_hash, commit_title = commit_line.split('\x01',1)

    with tempfile.TemporaryDirectory() as temp_dir:
        extract_commit_files(commit_hash, temp_dir)
        result = scan_with_detect_secrets(temp_dir)
    
        if result.get("results"):
            temp_results.append({
                "commit": commit_hash,
                "secrets": result["results"]
            })
        
    return temp_results


def check_commits_for_secrets(folder_path):
    """
    Main function to check for secrets in commit history :)
    """
    global repo_path

    repos = find_git_repos(folder_path)

    for repo in repos:
        if len(repos)==0:
            print(f"No valid .git repositories are available in {folder_path}")
        elif len(repos)>1:
            repo_path = os.path.join(folder_path, repo)
        else:
            repo_path = repo
        cmd = ['git', '-C', repo_path, 'log', '--pretty=format:%H%x01%s']
        result = subprocess.run(cmd, capture_output=True, text=True)
        commits = result.stdout.strip().split('\n')

        results = []

        with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
        ) as progress:
            task_id = progress.add_task(f"Scanning repository: {repo}", total=len(commits))

            with Pool(4) as pool:
                def update(result):
                    results.append(result)
                    progress.update(task_id, advance=1)

                for commit_line in commits:
                    pool.apply_async(for_processing, args=(commit_line,), callback=update)

                pool.close()
                pool.join()

        # remove falsy values
        all_results = [r for r in results if r] 

        if all_results:

            print(f"\n{BLUE}Invalid and unverified secrets are saved in not_verified.csv.{RESET}")
            # if ninja_mode is not called
            if not args.ninja_mode:
                print(f"{BLUE}Verified secrets are saved in verified.csv.{RESET}")
                print(f"{BLUE}Verified secrets detected in history:{RESET}")
                with open("verified.csv", "w") as v1:
                    v1.write("Commit Hash, Filename, Secret, Type\n")

            with open("not_verified.csv", "w") as v2:
                v2.write("Commit Hash, Filename, Secret, Type\n")

            pretty_results(all_results)

        else:
            print(f"{BLUE}No secrets found in any commit.{RESET}")
     

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--folder", type=str, help="Specify the folder containing git repo(s).", required=False)
    parser.add_argument("-n", "--ninja_mode", action="store_true", help="For OPSEC purposes. Verifications of secrets via networks call is disabled.", required=False)
    parser.add_argument("-c", "--clone", action="store_true" , help="Clones the repositories in an organisation.", required=False)

    args = parser.parse_args()

    if args.folder is None and not args.clone:
        print("Error: At least --folder or --clone needs to be set as an argument.")
        sys.exit(1)

    if shutil.which("detect-secrets") is None:
        print("Detect-secrets has not been installed. Please run the following command(s) to install it:")
        print(f"sudo apt install pipx")
        print(f'pipx install "git+https://github.com/ibm/detect-secrets.git@master#egg=detect-secrets"')
        sys.exit(1)

    print(r"""
           ______
        .-'      '-.
       /            \
      |              |
      |,  .-.  .-.  ,|
      | )(_o/  \o_)( |
      |/     /\     \|
      (_     ^^     _)
       \__|IIIIII|__/
        | \IIIIII/ |
        \          /
         `--------`
      RepoReaper: Harvest the Leaks
          """)

    RED = "\033[31m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    RESET = "\033[0m" # Resets all formatting

    
    if args.clone:
        folder_path = clone()
    
    if args.folder:
        folder_path = os.path.abspath(args.folder)
        if not os.path.isdir(folder_path):
            print(f"Error: '{folder_path} is not a valid directory.")
            sys.exit(1)

    check_commits_for_secrets(folder_path)
