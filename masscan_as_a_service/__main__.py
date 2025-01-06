#!/usr/bin/env python3

import argparse
import datetime
import io
import json
import logging
import os
import socket
import sys
import tempfile
from json import JSONDecodeError
from typing import Any, List, Dict

import yaml

from .scan_worker.ssh_worker import SshWorker
from .vm_operator.hetzner_cloud_operator import HetznerCloudOperator

LOG_FORMAT = '%(asctime)s %(filename)s:%(lineno)d %(levelname)s %(message)s'


def _args_parser() -> Dict[str, argparse.ArgumentParser]:
    """
    Parse commandline arguments.
    :return: argparse.Namespace for simple use
    """
    parser = argparse.ArgumentParser(prog='masscan_as_a_service',
                                     description='Masscan in a box',
                                     )

    parser.add_argument('-d', '--debug',
                        dest='debug', action='store_true',
                        help='Enable debugging')

    parser.add_argument('-e', '--environment-config',
                        dest='env_config',
                        required=True,
                        help='YAML file describing execution environment')

    parser.add_argument('-R', '--no-resolve',
                        dest='no_resolve',
                        action="store_true",
                        help="Do not resolve IP address to FQDN",
                        default=False)

    subparsers = parser.add_subparsers(dest='command')

    parser_masscan = subparsers.add_parser('masscan')

    group = parser_masscan.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--targets',
                       dest='targets', type=str,
                       help='File with targets (IP address) to scan. One per line.')

    group.add_argument('-a', '--api_keys',
                       dest='api_keys', type=str,
                       help='File with API keys of projects to scan. YAML array.')

    parser_masscan.add_argument('-o', '--output_dir',
                                dest='destination_dir', type=str,
                                required=True,
                                help='Directory to write results to')

    parser_masscan.add_argument('--ssh-public-key',
                                dest='ssh_public_key', type=str,
                                required=True,
                                help='File with the public SSH key to be given access to created VM')

    parser_masscan.add_argument('--ssh-private-key',
                                dest='ssh_private_key', type=str,
                                required=True,
                                help='File with the private SSH key corresponding to the ssh-public-key')

    parser_cleanup = subparsers.add_parser('cleanup')
    parser_cleanup.add_argument('-t', '--threshold',
                                dest='threshold', type=int,
                                required=True,
                                help='All VMs older then THRESHOLD seconds will be deleted.')

    return {
        'global': parser,
        'masscan': parser_masscan,
        'cleanup': parser_cleanup,
    }


def _parse_args() -> argparse.Namespace:
    return _args_parser()['global'].parse_args()


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
        json_data = []
        try:
            json_data = json.loads(
                "".join(raw_data.split()).rstrip(",]") + str("]"))
        except JSONDecodeError as e:
            print(e)
    output = {}
    for event in json_data:
        dict_of_ports = convert_list_of_ports_to_dict(event['ports'])
        output.setdefault(event['ip'], {}).update(dict_of_ports)
    return output


def get_all_primary_ips(name: str, api_key: str) -> dict:
    hcloud = HetznerCloudOperator(api_key)

    machines = dict()

    logging.info("Scanning project: %s", name)

    for server in hcloud.client.servers.get_all():
        if server.public_net.primary_ipv4:
            host = {
                "project": name,
                "name": server.name,
            }
            machines[server.public_net.primary_ipv4.ip] = host
        else:
            logging.warning("Server %s does not have primary ipv4", server.name)

    return machines


def get_api_targets(api_keys_path: str) -> dict:
    with open(api_keys_path, "r") as api_keys:
        api_keys = yaml.safe_load(api_keys)

    targets = dict()
    for api_key in api_keys:
        targets.update(get_all_primary_ips(api_key['name'], api_key['token']))

    return targets


def resolve(ip):
    try:
        return socket.getfqdn(ip)
    except Exception as e:
        print(f'Failed to resolve: {e}')
        return ip

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

        if args.command == 'cleanup':
            hcloud.purge_old_vms(args.threshold)
        elif args.command == 'masscan':
            api_targets = None
            if args.api_keys:
                api_targets = get_api_targets(args.api_keys)
                args.targets = io.StringIO(
                        "\n".join(api_targets.keys())
                        + "\n")

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

                try:
                    assert ssh.connection.put(local=args.targets, remote='/tmp/targets.list')
                    assert ssh.masscan().ok
                    assert ssh.connection.get(local=tmp_output_file, remote='/tmp/output.json', preserve_mode=False)

                    results = process_masscan_results(tmp_output_file)
                    for ip in results:
                        if args.no_resolve:
                            name = ip
                        else:
                            name = resolve(ip)
                        output_file = os.path.join(args.destination_dir, f"{name}.json")
                        with open(output_file, 'w') as stream:
                            host = results[ip]
                            if api_targets and api_targets[ip]:
                                host['project'] = api_targets[ip]['project']
                                host['name'] = api_targets[ip]['name']
                            json.dump(host, stream, sort_keys=True, indent=2)
                except Exception as e:
                    print(e)

            hcloud.delete_vm(vm_name)
            hcloud.delete_ssh_key(ssh_key_name)


if __name__ == '__main__':
    main()
