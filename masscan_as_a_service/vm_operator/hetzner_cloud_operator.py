from datetime import datetime, timedelta
from hcloud.images.domain import Image
from hcloud import Client
from hcloud.server_types.domain import ServerType
import logging
import pytz


class HetznerCloudOperator:
    """
    Wrapping the official Hetzner Cloud (HCloud) API client for required operations
    """

    def __init__(self, api_token):
        self.client = Client(token=api_token)
        self.logger = logging.getLogger('vm_operator')

    def delete_ssh_key(self, key_name):
        """Delete matching SSH key"""
        key = self.client.ssh_keys.get_by_name(key_name)
        self.client.ssh_keys.delete(key)

    def add_new_ssh_key(self, ssh_key_name, ssh_key):
        """
        Add new SSH key to Hetzner Cloud Project
        """
        self.client.ssh_keys.create(ssh_key_name, ssh_key)

    def create_vm(self, vm_name, vm_model, vm_os_image):
        """
        Provision a new VM
        """
        self.logger.debug(f"Creating VM {vm_name}")
        response = self.client.servers.create(
            name=vm_name,
            server_type=ServerType(vm_model),
            ssh_keys=self.client.ssh_keys.get_all(),
            image=Image(name=vm_os_image))
        response.action.wait_until_finished()
        return response.server

    def delete_vm(self, vm_name):
        """
        Delete an existing VM given its name
        """
        self._delete_vm(self.client.servers.get_by_name(vm_name))

    def purge_old_vms(self, max_age):
        """
        Delete all VMs which are older then {max_age}

        :params max_age: in seconds
        """
        for vm in self.client.servers.get_all():
            if (datetime.now(pytz.utc) - timedelta(seconds=max_age)) > vm.created:
                self._delete_vm(vm)

    def _delete_vm(self, vm):
        """
        Perform deletion of the VM
        """
        self.logger.info(f"Deleting VM {vm.name}")
        self.client.servers.delete(vm)
