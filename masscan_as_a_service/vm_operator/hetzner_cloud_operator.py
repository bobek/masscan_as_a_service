from datetime import datetime, timedelta, timezone
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
        if key:
            self.logger.info(f"Deleting SSH key {key_name}")
            # Delete the SSH key
            self._delete_ssh_key(key)

    def add_new_ssh_key(self, ssh_key_name, ssh_key, labels):
        """
        Add new SSH key to Hetzner Cloud Project
        """
        self.client.ssh_keys.create(ssh_key_name, ssh_key, labels=labels)

    def create_vm(self, vm_name, vm_model, vm_os_image, labels):
        """
        Provision a new VM
        """
        self.logger.debug(f"Creating VM {vm_name}")
        response = self.client.servers.create(
            name=vm_name,
            server_type=ServerType(vm_model),
            ssh_keys=self.client.ssh_keys.get_all(),
            image=Image(name=vm_os_image),
            labels=labels)
        response.action.wait_until_finished()
        return response.server

    def delete_vm(self, vm_name):
        """
        Delete an existing VM given its name
        """
        vm = self.client.servers.get_by_name(vm_name)
        if vm:
            self._delete_vm(vm)

    def purge_old_vms(self, max_age):
        """
        Delete all VMs which are older then {max_age}

        :params max_age: in seconds
        """
        for vm in self.client.servers.get_all():
            if (datetime.now(pytz.utc) - timedelta(seconds=max_age)) > vm.created:
                self._delete_vm(vm)

    def object_is_expired(self, object_labels):
        if 'delete_after' in object_labels:
            # parse delete_after label (use UTC if label has no explicit timezone)
            delete_after = datetime.fromisoformat(object_labels['delete_after'])
            if delete_after.tzinfo is None:
                delete_after.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) > delete_after:
                return True
        
        return False

    def purge_expired_vms(self, label):
        """
        Delete all expired VMs (expired delete_after label) matching {label}
        """
        label_key, label_value = label.split("=")

        for vm in self.client.servers.get_all():
            # only consider masscan's VMs for deletion
            if label_key in vm.labels and vm.labels[label_key] == label_value:
                if self.object_is_expired(vm.labels):
                    self.logger.info("VM '%s' has expired delete_after label - deleting the VM", vm.name)
                    self._delete_vm(vm)

    def purge_expired_ssh_keys(self, label):
        """
        Delete all expired SSH keys (expired delete_after label) matching {label}
        """
        label_key, label_value = label.split("=")

        for key in self.client.ssh_keys.get_all():
            # only consider SSH keys matching the specified label
            if label_key in key.labels and key.labels[label_key] == label_value:
                if self.object_is_expired(key.labels):
                    self.logger.info("SSH key '%s' has expired delete_after label - deleting the key", key.name)
                    self._delete_ssh_key(key)

    def _delete_vm(self, vm):
        """
        Perform deletion of the VM
        """
        self.logger.info(f"Deleting VM {vm.name}")
        self.client.servers.delete(vm)

    def _delete_ssh_key(self, key):
        """
        Perform deletion of the ssh key
        """
        self.logger.info(f"Deleting ssh key {key.name}")
        self.client.ssh_keys.delete(key)
