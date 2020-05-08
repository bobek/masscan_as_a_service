#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import os
import sys
import tempfile

import yaml

from typing import Any, List, Dict

from vm_operator.hetzner_cloud_operator import HetznerCloudOperator
from scan_worker.ssh_worker import SshWorker

LOG_FORMAT = '%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s'


def _parse_args() -> argparse.Namespace:
    """
    Parse commandline arguments.
    :return: argparse.Namespace for simple use
    """
    p = argparse.ArgumentParser()

    p.add_argument('-d', '--debug',
                   dest='debug', action='store_true',
                   help='Enable debugging')

    p.add_argument('-t4', '--targets-ipv4',
                   dest='targets_ipv4', type=str,
                   required=True,
                   help='File with targets (IPv4 address) to scan. One per line.')

    p.add_argument('-o', '--output_dir',
                   dest='destination_dir', type=str,
                   required=True,
                   help='Directory to write results to')

    p.add_argument('-e', '--environment-config',
                   dest='env_config',
                   required=True,
                   help='YAML file describing execution environment')

    p.add_argument('--ssh-public-key',
                   dest='ssh_public_key', type=str,
                   required=True,
                   help='File with the public SSH key to be given access to created VM')

    p.add_argument('--ssh-private-key',
                   dest='ssh_private_key', type=str,
                   required=True,
                   help='File with the private SSH key corresponding to the ssh-public-key')

    return p.parse_args()


def convert_list_of_ports_to_dict(list_of_ports: List[Dict[str, Any]]
                                  ) -> dict:
    """Helper to convert list of open ports to dict, e.g.:

    [{
      "port": 80,
      "proto": "tcp",
      "reason": "syn-ack",
      "status": "open",
      "ttl": 58
    },
    {
      "port": 22,
      "proto": "tcp",
      "reason": "syn-ack",
      "status": "open",
      "ttl": 58
    }]

    to

    { "80/tcp": { "reason": ..., }, "22/tcp": {} }

    :param list_of_ports: List containing dict of port results from masscan

    :return: Dict of port scan results converted into dict of dicts (see above)
    """
    dict_of_ports = {}
    for port in list_of_ports:
        dict_key = f"{port['port']}/{port['proto']}"
        port.pop('port')
        port.pop('proto')
        port.pop('ttl')
        dict_of_ports[dict_key] = port
    return dict_of_ports


def process_masscan_results(masscan_json_output_path: str) -> dict:
    """
    Parses output from masscan and groups it by IP address.
    """
    with open(masscan_json_output_path) as stream:
        raw_data = stream.read()
        # Remove the whistespaces and the last ",]", and restore the "]"
        # as masscan actually produces an invalid JSON.
        json_data = json.loads(
            "".join(raw_data.split()).rstrip(",]") + str("]"))
    output = {}
    for event in json_data:
        ip_address = event['ip']
        dict_of_ports = convert_list_of_ports_to_dict(event['ports'])
        output.setdefault(event['ip'], {}).update(dict_of_ports)
    return output


def main() -> None:
    """
    Magic happens here
    """
    args = _parse_args()

    logging.basicConfig(format=LOG_FORMAT, stream=sys.stderr)
    if args.debug:
        logging.getLogger("paramiko-ng").setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info("Masscan summons to an existence")
    with open(args.env_config, 'r') as stream:
        env_config = yaml.load(stream, Loader=yaml.FullLoader)

    if env_config['provider'] and env_config['provider']['type'] in ['hetzner_cloud', 'hcloud']:
        logging.debug('Hetzner cloud mode')
        provider = env_config['provider']
        api_token = os.environ.get(provider['api_token_env'])

        assert api_token, 'Missing Hetzner API token'
        hcloud = HetznerCloudOperator(os.environ.get(provider['api_token_env']))

        ssh_key_name = 'masscan-' + datetime.date.strftime(datetime.datetime.now(),
                                                           '%Y%m%d-%H%M%S')
        with open(args.ssh_public_key, 'r') as stream:
            key = stream.read()
            hcloud.add_new_ssh_key(ssh_key_name, key)

        vm_name = 'masscan-' + datetime.date.strftime(datetime.datetime.now(),
                                                      '%Y%m%d-%H%M%S')

        scan_server = hcloud.create_vm(vm_name, provider['vm_model'], provider['vm_os_image'])
        ssh = SshWorker(scan_server.public_net.ipv4.ip, args.ssh_private_key)
        assert ssh.is_alive()
        assert ssh.bootstrap_host().ok

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_output_file = os.path.join(temp_dir, 'output.json')

            assert ssh.connection.put(local=args.targets_ipv4, remote='/tmp/targets-ipv4.list')
            assert ssh.masscan().ok
            assert ssh.connection.get(local=tmp_output_file, remote='/tmp/output.json', preserve_mode=False)

            results = process_masscan_results(tmp_output_file)
            for ip in results:
                output_file = os.path.join(args.destination_dir, f"{ip}.json")
                with open(output_file, 'w') as stream:
                    json.dump(results[ip], stream, sort_keys=True, indent=2)

        hcloud.delete_vm(vm_name)
        # hcloud.purge_old_vms(provider['purge_time_seconds'])
        hcloud.delete_ssh_key(ssh_key_name)


if __name__ == '__main__':
    main()
