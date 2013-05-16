# Copyright (c) 2013, Wynand Winterbach
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# * Neither the name of the Dojo Foundation nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import asyncore
import asynchat
import socket
import cStringIO
import shlex
import logging
from functools import partial
import pytrie

logging.basicConfig()


class ClientSession(asynchat.async_chat):
    def __init__(self, server, conn, address):
        asynchat.async_chat.__init__(self, conn)
        self.server = server
        self.address = address
        self.listening = False

        self.buffer = cStringIO.StringIO()
        self.current_state = self.reset(self.state_command, '\n')

        self.subscriptions = set()

    def collect_incoming_data(self, data):
        self.buffer.write(data)

    def found_terminator(self):
        try:
            self.current_state = self.current_state()
        except:
            logging.exception("Exception in client {0}".format(self.address))
            self.current_state = self.state_command

    def reset(self, new_state, terminator):
        self.buffer.reset()
        self.buffer.truncate()
        self.set_terminator(terminator)
        return new_state

    def state_command(self):
        logging.debug('Processing command')
        buf = self.buffer.getvalue()
        lexer = shlex.shlex(buf)
        lexer.whitespace_split = True
        command = lexer.next()

        if command == 'send':
            buffer_size = int(lexer.next())
            self.push('ack send\n'.format(buffer_size))
            return self.reset(partial(self.state_send, lexer), buffer_size)
        elif command == 'sub':
            new_subscriptions = set(lexer)
            self.subscriptions |= new_subscriptions
            self.server.subscribe(new_subscriptions, self)
            self.push('ack sub\n')
        elif command == 'unsub':
            subscriptions_to_remove = set(lexer)
            self.subscriptions -= subscriptions_to_remove
            self.server.unsubscribe(subscriptions_to_remove, self)
            self.push('ack unsub\n')
        elif command == 'error':
            logging.debug('Received error from client {0}: {1}'.format(self.address, buf))
        elif command == 'ping':
            self.push('pong\n')
        elif command == 'listen':
            self.listening = True
            self.push('ack listen\n')
        elif command == 'unlisten':
            self.listening = False
            self.push('ack unlisten\n')
        else:
            self.push('error Received invalid command: {0}\n'.format(command))

        return self.reset(self.state_command, '\n')

    def state_send(self, addresses):
        logging.debug('Processing send')
        self.server.deliver(self, addresses, self.buffer.getvalue())
        self.push('ack send\n')
        return self.reset(self.state_command, '\n')

    def deliver(self, buf):
        if self.listening:
            self.push('recv {0}\n'.format(len(buf)))
            self.push_with_producer(asynchat.simple_producer(buf))

    def handle_close(self):
        self.server.remove_client(self)
        asynchat.async_chat.handle_close(self)


class Server(asyncore.dispatcher):
    def __init__(self, port):
        asyncore.dispatcher.__init__(self)

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', port))
        self.listen(5)

        self._clients = {}
        self._channels = pytrie.StringTrie()

    def remove_client(self, client):
        self.unsubscribe(client.subscriptions, client)
        del self._clients[client.address]

    def handle_accept(self):
        conn, address = self.accept()
        self._clients[address] = ClientSession(self, conn, address)

    def subscribe(self, keys, client):
        for key in keys:
            try:
                self._channels[key][client.addr] = client
            except KeyError:
                self._channels[key] = {client.addr: client}
            logging.debug("Subscribed %s to %s", client.addr, key)

    def unsubscribe(self, keys, client):
        for key in keys:
            try:
                del self._channels[key][client.addr]
                logging.debug("Unsubscribed %s from %s", client.addr, key)
                if len(self._channels[key]) == 0:
                    del self._channels[key]
            except KeyError:
                pass

    def deliver(self, sender, keys, data):
        delivery_targets = {}
        for key in keys:
            for client_dict in self._channels.itervalues(key):
                delivery_targets.update(client_dict)
        for client in delivery_targets.itervalues():
            if client != sender:
                client.deliver(data)


if __name__ == '__main__':
    server = Server(11111)
    asyncore.loop()
