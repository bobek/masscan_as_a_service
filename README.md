# Masscan as a Service

## VM Providers
### Hetzner Cloud

Create a project at [Hetzner cloud console](https://console.hetzner.cloud/projects). Open the project and go to `Access` section. Create a new API key under `API Tokens` tab.

## Example of execution

```bash
ssh-keygen -t ed25519 -f vm_key -q -N ""
mkdir /tmp/masscan_out

HCLOUD_TOKEN=VERY_LONG_STRING_WITH_API_TOKEN ./perform_masscan.py -d -e hcloud_example.yml --ssh-public-key vm_key.pub --ssh-private-key vm_key -o /tmp/masscan_out
```