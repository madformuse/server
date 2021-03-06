import asyncio
from unittest import mock
import pytest

from server.connectivity import TestPeer, Connectivity, ConnectivityState

slow = pytest.mark.slow

@asyncio.coroutine
@slow
def test_TestPeer_tests_public(loop):
    identifier = '2'
    game_connection = mock.Mock()
    with TestPeer(game_connection, '127.0.0.1', 6112, identifier) as peer_test:
        connectivity = asyncio.async(peer_test.determine_connectivity())
        peer_test.handle_ProcessNatPacket(['Are you public? {}'.format(identifier)])
        yield from connectivity
        assert connectivity.result() == Connectivity(addr='127.0.0.1:6112', state=ConnectivityState.PUBLIC)

@asyncio.coroutine
@slow
def test_TestPeer_tests_stun(loop):
    identifier = '2'
    game_connection = mock.Mock()
    with TestPeer(game_connection, '127.0.0.1', 6112, identifier) as peer_test:
        connectivity = asyncio.async(peer_test.determine_connectivity())
        peer_test.handle_ProcessServerNatPacket(['127.0.0.1:6112', 'Hello {}'.format(identifier)])
        yield from connectivity
        assert connectivity.result() == Connectivity(addr='127.0.0.1:6112', state=ConnectivityState.STUN)

@asyncio.coroutine
@slow
def test_TestPeer_tests_proxy(loop):
    identifier = '2'
    game_connection = mock.Mock()
    with TestPeer(game_connection, '127.0.0.1', 6112, identifier) as peer_test:
        connectivity = yield from peer_test.determine_connectivity()
        assert connectivity == Connectivity(addr=None, state=ConnectivityState.PROXY)


