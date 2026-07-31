"""Tests for the label/expiration logic of the Hetzner Cloud operator.

Nothing here talks to the API - the hcloud client is replaced by a fake.
"""

from datetime import datetime, timedelta, timezone

import pytest

from masscan_as_a_service.vm_operator.hetzner_cloud_operator import HetznerCloudOperator

LABEL = 'app=masscan'


def _iso(**delta):
    """Timezone-aware UTC timestamp, offset from now."""
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


def _naive_iso(**delta):
    """Same instant, but without the explicit offset - must be read as UTC."""
    return (datetime.now(timezone.utc) + timedelta(**delta)).replace(tzinfo=None).isoformat()


class FakeResource:
    def __init__(self, name, labels):
        self.name = name
        self.labels = labels


class FakeCollection:
    """Stands in for client.servers / client.ssh_keys."""

    def __init__(self, resources):
        self._resources = resources
        self.deleted = []

    def get_all(self):
        return list(self._resources)

    def get_by_name(self, name):
        return next((r for r in self._resources if r.name == name), None)

    def delete(self, resource):
        self.deleted.append(resource.name)


class FakeClient:
    def __init__(self, servers=(), ssh_keys=()):
        self.servers = FakeCollection(list(servers))
        self.ssh_keys = FakeCollection(list(ssh_keys))


@pytest.fixture()
def operator():
    op = HetznerCloudOperator('dummy-token')
    op.client = FakeClient()
    return op


@pytest.mark.parametrize(
    'labels',
    [
        {},
        {'app': 'masscan'},
        {'delete_after': _iso(hours=1)},
        {'delete_after': _naive_iso(hours=1)},
    ],
)
def test_not_expired(operator, labels):
    assert operator.object_is_expired(labels) is False


@pytest.mark.parametrize(
    'labels',
    [
        {'delete_after': _iso(hours=-1)},
        {'delete_after': _naive_iso(hours=-1)},
    ],
)
def test_expired(operator, labels):
    assert operator.object_is_expired(labels) is True


def test_purge_expired_vms_only_deletes_expired_and_labelled(operator):
    operator.client.servers = FakeCollection(
        [
            FakeResource('expired-and-labelled', {'app': 'masscan', 'delete_after': _iso(hours=-1)}),
            FakeResource('labelled-but-fresh', {'app': 'masscan', 'delete_after': _iso(hours=1)}),
            FakeResource('expired-but-foreign', {'app': 'production', 'delete_after': _iso(hours=-1)}),
            FakeResource('no-delete-after', {'app': 'masscan'}),
            FakeResource('unlabelled', {}),
        ]
    )

    operator.purge_expired_vms(LABEL)

    assert operator.client.servers.deleted == ['expired-and-labelled']


def test_purge_expired_ssh_keys_only_deletes_expired_and_labelled(operator):
    operator.client.ssh_keys = FakeCollection(
        [
            FakeResource('expired-and-labelled', {'app': 'masscan', 'delete_after': _iso(hours=-1)}),
            FakeResource('labelled-but-fresh', {'app': 'masscan', 'delete_after': _iso(hours=1)}),
            FakeResource('expired-but-foreign', {'app': 'production', 'delete_after': _iso(hours=-1)}),
        ]
    )

    operator.purge_expired_ssh_keys(LABEL)

    assert operator.client.ssh_keys.deleted == ['expired-and-labelled']


def test_delete_vm_ignores_missing_vm(operator):
    operator.client.servers = FakeCollection([FakeResource('other', {})])

    operator.delete_vm('gone-already')

    assert operator.client.servers.deleted == []


def test_delete_ssh_key_ignores_missing_key(operator):
    operator.client.ssh_keys = FakeCollection([FakeResource('other', {})])

    operator.delete_ssh_key('gone-already')

    assert operator.client.ssh_keys.deleted == []


def test_delete_vm_by_name(operator):
    operator.client.servers = FakeCollection([FakeResource('masscan-worker', {})])

    operator.delete_vm('masscan-worker')

    assert operator.client.servers.deleted == ['masscan-worker']
