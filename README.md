# Masscan as a Service

It happened to everyone --  forgotten rule in `iptables` caused open access to `docker` control port. Next thing you know, malicious containers running on your infrastructure, sending spam emails at best. Woudn't be great if you get notified, that something on a previously unseen TCP or UDP port started accepting connections on your server?

This project leverages an excellent [masscan](https://github.com/robertdavidgraham/masscan) which can scan whole IPv4 range under 6 minutes (if you really want to push your network). We will also add support for `nmap` as `masscan` [doesn't play nice with IPv6](https://github.com/robertdavidgraham/masscan/issues/7).

WARNING: commence port scanning from and to systems you operate, and you are allowed to send large volume of packets (e.g. TCP ACK) towards. Also make sure, that you have cleared permissions with your hosting providers. This will certainly trip various intrusion detection / anomaly detection systems.

## Theory of Operation
1. use some system to schedule regular executions. For example gitlab CD or github actions.
1. run `perform_masscan.py`, you will need
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

Token is than read from the environment variable, which is set in the configuration file (`api_token_env`). Example configuration is at [`hcloud_example.yml`](hcloud_example.yml).

## Example of execution

```bash
ssh-keygen -t ed25519 -f vm_key -q -N ""
mkdir /tmp/masscan_out
echo "127.0.0.1" > targets.list

HCLOUD_TOKEN=VERY_LONG_STRING_WITH_API_TOKEN ./perform_masscan.py -d -e hcloud_example.yml --ssh-public-key vm_key.pub --ssh-private-key vm_key -t tragets.list -o /tmp/masscan_out
```