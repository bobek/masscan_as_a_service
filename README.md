# Masscan as a Service

It happened to everyone --  forgotten rule in `iptables` caused open access to `docker` control port. Next thing you know, malicious containers running on your infrastructure, sending spam emails at best. Woudn't be great if you get notified, that something on a previously unseen TCP or UDP port started accepting connections on your server?

This project leverages an excellent [masscan](https://github.com/robertdavidgraham/masscan) which can scan whole IPv4 range under 6 minutes (if you really want to push your network). We will also add support for `nmap` as `masscan` [doesn't play nice with IPv6](https://github.com/robertdavidgraham/masscan/issues/7).

WARNING: commence port scanning from and to systems you operate, and you are allowed to send large volume of packets (e.g. TCP ACK) towards. Also make sure, that you have cleared permissions with your hosting providers. This will certainly trip various intrusion detection / anomaly detection systems.

## Installation

Whole project is distributed as a Python package to make it simple to include in your tooling. It is **not** yet on https://pypi.org. Example `Pipfile` for **your** project:

```pipfile
[[source]]
url = "https://pypi.python.org/simple"
verify_ssl = true
name = "pypi"

[packages]
masscan_as_a_service = {git = "https://github.com/bobek/masscan_as_a_service.git", editable = true}
```

This will give you `masscan_as_a_service` binary in your `bin` directory. As usual, `virtualenv` / `pipenv` is recommended.

## Theory of Operation
1. use some system to schedule regular executions. For example gitlab CD or github actions.
1. run `masscan_as_a_service masscan`, you will need
    - a list of targets (path passed as `--targets`). One target per line. It is up to you how you are going to generate it. For example, in our deployments, we fetch list servers to test from inventory management system (aka Machine DataBase).
    - access details based on your cloud provider (check below). Also prepare appropriate configuration file.
    - ssh key (private and public parts) to get access to worker.
    - clone repository which you use to store results and point scanner to it  (`--output_dir`)
1. scanner will update per host files in the output directory. You should now commit them to your repository and trigger audit in case anything changed.

Please make sure, that the provisioned VM is in the network which makes sense for your test. For example, we provision completely separete VM, which is not connected to our internal systems in any way (except control `ssh` connection). Thus is represents a random Internet user as close as possible as we are interested in ports being opened to the wild.

### Scan Result Storage
We have mentioned use of a repository (we use `git`) for storing the output files. Motivation behind it is that you will keep a history of changes within the version control. So you will know how the state looked in the past.

We also use version control as a way of detecting changes (e.g. new port being open). `git` will not let you make an empty commit. On the other side, if you successfully push to remote repository with a new commit, you can trigger an action. We use [Phabricator's Audits](https://secure.phabricator.com/book/phabricator/article/audit/) for this. Phabricator is watching repository with results and when a new commit appears, it will start a new audit. Responsible members of the team will either describe why is the new port being open as it is an intended behavior. Or they will start investigating the root cause of it being open. In any case, you have one central place for storing information about *why* is some port opened and accessible.

## VM Providers
### Hetzner Cloud
Create a project at [Hetzner cloud console](https://console.hetzner.cloud/projects). Open the project and go to `Access` section. Create a new API key under `API Tokens` tab.

Token is then read from the environment variable, which is set in the configuration file (`api_token_env`). Example configuration is at [`hcloud_example.yml`](examples/hcloud.yml).

## Usage `masscan_as_a_service`
When installed, you will get a `masscan_as_a_service` application. It can perform various commands based on the first positional argument.

### Global options
Some arguments can be defined only on the global level. For example, you turn debugging on for `cleanup` command with `masscan_as_a_service -d cleanup`.

```
usage: masscan_as_a_service [-h] [-d] -e ENV_CONFIG [-R] {masscan,cleanup} ...

Masscan in a box

positional arguments:
  {masscan,cleanup}

options:
  -h, --help            show this help message and exit
  -d, --debug           Enable debugging
  -e ENV_CONFIG, --environment-config ENV_CONFIG
                        YAML file describing execution environment
  -R, --no-resolve      Do not resolve IP address to FQDN

```

### Command `masscan`
```
usage: masscan_as_a_service masscan [-h] (-t TARGETS | -a API_KEYS)
                                    [-L [LABEL ...]] -o DESTINATION_DIR
                                    --ssh-public-key SSH_PUBLIC_KEY
                                    --ssh-private-key SSH_PRIVATE_KEY

options:
  -h, --help            show this help message and exit
  -t TARGETS, --targets TARGETS
                        File with targets (IP address) to scan. One per line.
  -a API_KEYS, --api_keys API_KEYS
                        File with API keys of projects to scan. YAML array.
  -L [LABEL ...], --label [LABEL ...]
                        Label to be added to the VM (key=value)
  -o DESTINATION_DIR, --output_dir DESTINATION_DIR
                        Directory to write results to
  --ssh-public-key SSH_PUBLIC_KEY
                        File with the public SSH key to be given access to
                        created VM
  --ssh-private-key SSH_PRIVATE_KEY
                        File with the private SSH key corresponding to the
                        ssh-public-key

```

### Command `cleanup`
```
usage: masscan_as_a_service cleanup [-h] -t THRESHOLD

options:
  -h, --help            show this help message and exit
  -t THRESHOLD, --threshold THRESHOLD
                        All VMs older then THRESHOLD seconds will be deleted.

```

## Example

I have provisioned 2 VM on Hetzner Cloud for this demo. Their IP addresses are `94.130.26.161` and `95.217.232.216`.

### Setup
You would normally automate following steps in your execution system. I will perform preparation steps manually.

First, we will need some ephemeral ssh key to access worker node. We will generate a new key stored in `vm_key` file with the following command:

```bash
ssh-keygen -t ed25519 -f /tmp/vm_key -q -N ""
```

We also need a list of targets to perform port scanning against. Let's store in the file named `targets.list`.

```bash
cat  <<EOF > /tmp/targets.list
94.130.26.161
95.217.232.216
EOF
```

Optionally you can specify list of api keys with name. `masscan_as_a_service` loads targets dynamically from Hetzner.

```bash
cat <<EOF > /tmp/api_tokens.yaml
- name: jbarton # project name, description, ...
  token: XfT5q...
EOF
```

Checkout a git repo to place results into:

```bash
git clone some_remote_repo_with_audits_enabled /tmp/out
```

### Initial scan

```bash
HCLOUD_TOKEN=VERY_LONG_STRING_WITH_API_TOKEN masscan_as_a_service -d -e examples/hcloud.yml masscan --ssh-public-key /tmp/vm_key.pub --ssh-private-key /tmp/vm_key -t /tmp/targets.list -o /tmp/out
# OR
HCLOUD_TOKEN=VERY_LONG_STRING_WITH_API_TOKEN masscan_as_a_service -d -e examples/hcloud.yml masscan --ssh-public-key /tmp/vm_key.pub --ssh-private-key /tmp/vm_key -a /tmp/api_tokens.yaml -o /tmp/out
```

After the successful scan we will get two new files, one per target. They have the same content as on `ssh` is currently open on these newly provisioned VMs.

```json
{
  "22/tcp": {
    "reason": "syn-ack",
    "status": "open"
  }
}
```

We can happily commit and push our scan results. Depending on your setup, this will trigger a source code audit as we have made changes to the repository. We will just resolved it with "provisioned 2 new VMs for demoing the masscan" and move on with our DevOps work.

### Opening some ports

Scan was executed multiple times as we are running it regularly from our scheduler. But one day this happens:

```diff
diff --git i/94.130.26.161.json w/94.130.26.161.json
index bceef26..fe5c4ee 100644
--- i/94.130.26.161.json
+++ w/94.130.26.161.json
@@ -1,6 +1,26 @@
 {
+  "10250/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
+  },
+  "10251/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
+  },
+  "10252/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
+  },
+  "10256/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
+  },
   "22/tcp": {
     "reason": "syn-ack",
     "status": "open"
+  },
+  "6443/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
   }
diff --git i/95.217.232.216.json w/95.217.232.216.json
index bceef26..45249f2 100644
--- i/95.217.232.216.json
+++ w/95.217.232.216.json
@@ -1,6 +1,14 @@
 {
+  "10250/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
+  },
+  "10256/tcp": {
+    "reason": "syn-ack",
+    "status": "open"
+  },
   "22/tcp": {
     "reason": "syn-ack",
     "status": "open"
   }
```

As usual, we automatically commit and push the changed files to the repository. Source-code audit is going to be triggered as we have a new commit. We see that new ports are now open to the wild Internet. Brief look suggests that somebody has installed a new Kubernetes cluster on these VMs, but had totally forgotten to take care of filtering access to its services from the outside world.
