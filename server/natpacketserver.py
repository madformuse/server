import socket

from server.subscribable import Subscribable
from .decorators import with_logger


@with_logger
class NatPacketServer(Subscribable):
    def __init__(self, loop, port):
        super().__init__()
        self.loop = loop
        self.port = port
        self._logger.debug("{id} Listening on {port}".format(id=id(self), port=port))
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.setblocking(False)
        loop.add_reader(s.fileno(), self._recv)
        self._socket = s
        self._subscribers = {}

    def close(self):
        self.loop.remove_reader(self._recv())
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError as ex:
            self._logger.exception(ex)
        finally:
            self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _recv(self):
        try:
            data, addr = self._socket.recvfrom(512)
            self._logger.debug("Received UDP {} from {}".format(data, addr))
            if data[0] == 0x8:
                self._logger.debug("Emitting with: {} {} {} ".format(data[1:].decode(),
                    addr[0], addr[1]))
                self.notify({
                    'command_id': 'ProcessServerNatPacket',
                    'arguments': ["{}:{}".format(addr[0], addr[1]), data[1:].decode()]
                })
                self._socket.sendto(b"\x08OK", addr)
        except OSError as ex:
            if ex.errno == socket.EWOULDBLOCK:
                pass
            else:
                self._logger.critical(ex)
                raise ex
        except Exception as ex:
            self._logger.critical(ex)
            raise ex
