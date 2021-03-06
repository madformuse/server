import asyncio

from .decorators import with_logger


@with_logger
class Subscribable:
    """
    Mixin for handling subscriptions to messages.

    The standard format of messages is as follows:
    >>> {
    >>>     "command_id": "some_command",
    >>>     "arguments": []
    >>> }

    Subscribable.notify dispatches messages to the subscriber, they are dispatched
    to the handle_{command_id} method on the subscriber, if it is there.
    """
    def __init__(self):
        self._subscriptions = {'_all': []}
        self._emissions = {}

    def subscribe(self, receiver, command_ids=None, filter=None):
        """
        Subscribe to messages from this GameConnection
        :param receiver: object to receive messages
        :param command_ids: Optional list of command_ids to subscribe to
        :param filter:
            Optional function to invoke with arguments to
            determine whether or not to forward message.
        :return: None
        """
        self._logger.debug("Subscribing {receiver} to {commands} on {self}".format(
            receiver=receiver,
            commands=command_ids,
            self=self
        ))
        if command_ids is None:
            command_ids = ['_all']
        sub = Subscription(self, receiver, command_ids, filter)
        for i in command_ids:
            if i in self._subscriptions:
                self._subscriptions[i].append(sub)
            else:
                self._subscriptions[i] = [sub]
        return sub

    def notify(self, message):
        """
        Notify subscribers that a message of interest arrived
        :param message:
        :return:
        """
        command_id = message.get("command_id")
        assert isinstance(command_id, str)
        if command_id in self._subscriptions:
            for sub in self._subscriptions[command_id]:
                sub.fire(message)
        for sub in self._subscriptions['_all']:
            sub.fire(message)

    def unsubscribe(self, receiver, command_ids=None):
        """
        Unusubscribe a given function from given message ids.

        Be careful to unsubscribe from exactly the messages that the receiver
        has subscribed to.
        :param receiver: function to unsubscribe
        :param command_ids: Command identifiers to unsubscribe from
        :return: None
        """
        self._logger.debug("Unsubscribing {receiver} from {commands} on {self}".format(
            receiver=receiver,
            commands=command_ids,
            self=self
        ))
        if not command_ids:
            command_ids = ['_all']
        for i in command_ids:
            if i in self._subscriptions:
                self._subscriptions[i] = [sub for sub in self._subscriptions[i]
                                          if sub.receiver != receiver]


@with_logger
class Subscription:
    """
    Tracks a subscription and automatically cancels it if used as a context manager.

    For use as a context manager
    """
    def __init__(self, source: Subscribable, receiver: object, command_ids: [str], filter=None):
        if not filter:
            filter = lambda args: True
        self.receiver = receiver
        self.command_ids = command_ids
        self.filter = filter
        self.source = source
        self._emissions = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.source.unsubscribe(self.receiver, self.command_ids)
        # TODO: Cleanup futures in _emissions?

    def fire(self, message):
        command_id = message['command_id']
        arguments = message['arguments']
        cmd_name = 'handle_{cmd_id}'.format(cmd_id=command_id)
        self._logger.debug("Notifying {receiver} of {command} on {self}".format(
            receiver=self.receiver,
            command=command_id,
            self=self
        ))
        if self.filter(arguments):
            if command_id in self._emissions and not self._emissions[command_id].done():
                self._logger.debug('Setting {} as fired'.format(command_id))
                self._emissions[command_id].set_result(True)
            if hasattr(self.receiver, cmd_name):
                self._logger.debug("Firing {} on {}".format(cmd_name, self.receiver))
                getattr(self.receiver, cmd_name)(arguments)
            else:
                self._logger.info("Receiver {} does not have event handler method {}".format(self.receiver, cmd_name))

    @asyncio.coroutine
    def wait_for(self, command_id, timeout=None):
        """
        Wait for the given command ID to be executed
        :param command_id: command identifier
        :return: future representing when a command has been executed
        """
        self._logger.debug("Awaiting {} with a timeout of {}".format(command_id, timeout))
        if command_id not in self._emissions:
            self._emissions[command_id] = asyncio.Future()
        yield from asyncio.wait_for(self._emissions[command_id], timeout=timeout)
        self._emissions[command_id] = asyncio.Future()
