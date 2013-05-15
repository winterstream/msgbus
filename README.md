Simple pubsub message bus
=========================

msgbus is a simple message bus that should run with a stock Python installation.
Other than being written in Python, it is in no way tied to Python and it should
be easy enough to use from any program.

Clients register themselves on a number of channels. A channel is simply a string.
Clients on a channel c will receive all messages sent to c or substrings of c.
In other words, if a client is registered on channel ``fooquux``, it will receive
messages sent to ``fooquux`` as well as ``foo`` (and all other substrings of
``fooquux``).

Protocol
--------

The protocol is somewhat ad-hoc but should be simple enough to parse. Clients
can subscribe and unsubscribe to channels. They can send messages containing
arbitrary bytes to each other. In order for a client to start receiving messages,
it must notify the server with the ``listen`` message. It can stop receiving
messages with the ``unlisten`` command.

### Subscribing

To subscribe to channels channel_1, channel_2, ..., channel_t, a client
sends a line of the form:
``sub channel_1 channel_2 ... channel_t\n``

The server responds with:
``ack sub\n``

### Unsubscribing

To unsubscribe from channels channel_1, channel_2, ..., channel_t, a client
sends a line of the form:
``unsub channel_1 channel_2 ... channel_t\n``

The server responds with:
``ack unsub\n``

### Ping message

The client may send the message ``ping\n`` to which the server responds
with ``pong\n``.

### Sending messages

To send a message of _x_ bytes to channels channel_1, channel_2, ..., channel_t,
a client first sends a line of the form:
``send _x_ channel_1 channel_2 ... channel_t\n``
After this, the client sends _x_ bytes of the message are transmitted.

Clients that are registered on channels channel_1, channel_2, ..., channel_t
*and* that are listening will first receive the line:
``recv _x_\n``
followed by _x_ bytes.

In order to receive messages, a client must first send the ``listen`` message.
The client can stop receiving messages by sending the ``unlisten`` message.

### Listen message

To start receiving data messages from the server, the client states its intent
by sending the message:
``listen\n``
to which the server responds:
``ack listen\n``

### Unlisten message

To stop receiving data messages from the server, the client states its intent
by sending the message:
``unlisten\n``
to which the server responds:
``ack unlisten\n``

### Error reporting

If the client sends an invalid command, the server responds with the line:
``error xxx\n``
where ``xxx`` is an error message (without newlines).

