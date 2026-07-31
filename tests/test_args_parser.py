"""Tests for the commandline interface."""

import pytest

from masscan_as_a_service.__main__ import _args_parser

PARSERS = ('global', 'masscan', 'cleanup', 'cleanup_expired')


@pytest.fixture()
def parser():
    return _args_parser()['global']


@pytest.mark.parametrize('name', PARSERS)
def test_every_subparser_is_exposed(name):
    """generate_readme.py renders the help of each of these."""
    assert _args_parser()[name].format_help()


def test_masscan_with_targets(parser):
    args = parser.parse_args(
        [
            '-e',
            'env.yaml',
            'masscan',
            '--targets',
            'targets.list',
            '--output_dir',
            'out',
            '--ssh-public-key',
            'id.pub',
            '--ssh-private-key',
            'id',
        ]
    )

    assert args.command == 'masscan'
    assert args.targets == 'targets.list'
    assert args.api_keys is None
    assert args.destination_dir == 'out'
    assert args.debug is False
    assert args.no_resolve is False
    assert args.label == []


def test_masscan_labels_are_collected(parser):
    args = parser.parse_args(
        [
            '-d',
            '-R',
            '-e',
            'env.yaml',
            'masscan',
            '--api_keys',
            'keys.yaml',
            '--output_dir',
            'out',
            '--ssh-public-key',
            'id.pub',
            '--ssh-private-key',
            'id',
            '-L',
            'owner=security',
            'delete_after=2026-01-01T00:00:00+00:00',
        ]
    )

    assert args.debug is True
    assert args.no_resolve is True
    assert args.label == ['owner=security', 'delete_after=2026-01-01T00:00:00+00:00']
    assert dict(label.split('=', 1) for label in args.label) == {
        'owner': 'security',
        'delete_after': '2026-01-01T00:00:00+00:00',
    }


def test_targets_and_api_keys_are_mutually_exclusive(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                '-e',
                'env.yaml',
                'masscan',
                '--targets',
                'targets.list',
                '--api_keys',
                'keys.yaml',
                '--output_dir',
                'out',
                '--ssh-public-key',
                'id.pub',
                '--ssh-private-key',
                'id',
            ]
        )


def test_environment_config_is_required(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(['cleanup', '--threshold', '3600'])


def test_cleanup(parser):
    args = parser.parse_args(['-e', 'env.yaml', 'cleanup', '--threshold', '3600'])

    assert args.command == 'cleanup'
    assert args.threshold == 3600


def test_cleanup_expired(parser):
    args = parser.parse_args(['-e', 'env.yaml', 'cleanup-expired', '--label', 'owner=security'])

    assert args.command == 'cleanup-expired'
    assert args.label == 'owner=security'
