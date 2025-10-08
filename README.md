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


# RepoReaper
A tool to extract secrets from git repositories and commit history. This tool allows you to:
- Clone the repositories from an organisation (_e.g. github.com/{organisation}/{repository-name}_)
- Run _detect-secrets_ run against the commit history of the git repositories
- Run _detect-secrets_ without verifying the secrets found. Else, there would be external calls made to verify the validity of the secrets.
- Save the output in csv files. These files should be available in the same folder as this tool.

## Pre-requisites
To run it in a Kali Linux environment, please install the following:

<pre lang="markdown">sudo apt install gh
sudo apt install pipx 
pipx install "git+https://github.com/ibm/detect-secrets.git@master#egg=detect-secrets"</pre>

Please ensure that you have read access to the repository's contents.

## How do i use it?
<pre lang="markdown">$ python3 reporeaper.py --help
usage: reporeaper.py [-h] [-f FOLDER] [-n] [-c]

options:
  -h, --help           show this help message and exit
  -f, --folder FOLDER  Specify the folder containing git repo(s).
  -n, --ninja_mode     For OPSEC purposes. Verifications of secrets via networks call is disabled.
  -c, --clone          Clones the repositories in an organisation.</pre>

### To run against a git folder that you have already cloned
If you have already cloned the git folder, please specify the folder's location:
<pre lang="markdown">$ python3 reporeaper.py -f ./folder-name</pre>

### To clone git repositories before running RepoReaper
If you have a multiple repositories to be cloned in your environment, create a text file filled with a list of repositories. Please ensure the accuracy with regards to the name of the repositories (including the <ins>upper and lower cases</ins>).
<pre lang="markdown">$ cat sample.txt 
ibm-test
IBM-CISO</pre>
Next, run the following command:
<pre lang="markdown">$ python3 reporeaper.py -c</pre>

