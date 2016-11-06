"""
Tests for connecting to a client, logging in, state changes, and whether the
respective callbacks are made, and events triggered.
"""
from __future__ import absolute_import, division, print_function, with_statement
from __future__ import unicode_literals

from deepstreampy.message import message_builder, message_parser
from deepstreampy.constants import actions, connection_state
from deepstreampy.constants import topic as topic_constants
from deepstreampy.constants import event as event_constants
from deepstreampy import client
from tornado import testing
import sys

if sys.version_info[0] < 3:
    import mock
else:
    from unittest import mock

HOST = "localhost"
PORT = 6029

test_server_exceptions = []


class ConnectionTest(testing.AsyncTestCase):

    def setUp(self):
        super(ConnectionTest, self).setUp()
        self.client = mock.Mock()
        self.iostream = mock.Mock()
        self.auth_callback = mock.Mock()

    def _get_connection_state_changes(self):
        count = 0
        for call_args in self.client.emit.call_args_list:
            if call_args[0][0] == event_constants.CONNECTION_STATE_CHANGED:
                count += 1
        return count

    def _get_sent_messages(self):
        for call_args in self.iostream.write.call_args_list:
            yield call_args[0]

    def _get_last_sent_message(self):
        return self.iostream.write.call_args[0][0]

    def test_connects(self):
        connection = client._Connection(self.client, 'localhost', 6666)
        assert connection.state == connection_state.CLOSED
        self.assertEquals(self._get_connection_state_changes(), 0)
        connect_future = connection.connect()
        connect_future.set_result(self.iostream)
        connection._on_open(connect_future)
        self.assertEquals(connection.state,
                          connection_state.AWAITING_CONNECTION)
        self.assertEquals(self._get_connection_state_changes(), 1)
        connection._on_data('C{0}A{1}'.format(chr(31), chr(30)))
        self.assertEquals(connection.state,
                          connection_state.AWAITING_AUTHENTICATION)
        self.iostream.write.assert_not_called()

        connection.authenticate({'user': 'Anon'}, self.auth_callback)
        self.assertEquals(connection.state,
                          connection_state.AUTHENTICATING)
        self.assertEquals(self._get_last_sent_message(),
                          "A{0}REQ{0}{{\"user\":\"Anon\"}}{1}".format(
                              chr(31), chr(30)).encode())
        self.assertEquals(self._get_connection_state_changes(), 3)
        self.auth_callback.assert_not_called()

        connection._on_data('A{0}A{1}'.format(chr(31), chr(30)))
        self.assertEquals(connection.state,
                          connection_state.OPEN)
        self.auth_callback.assert_called_once_with(True, None, None)
        self.assertEquals(self._get_connection_state_changes(), 4)

        connection.send_message('R', 'S', ['test1'])
        self.iostream.write.assert_called_with(
            'R{0}S{0}test1{1}'.format(chr(31), chr(30)).encode())

        closed_callback = self.iostream.set_close_callback.call_args[0][0]
        connection.close()
        closed_callback()
        self.assertEquals(connection.state,
                          connection_state.CLOSED)
        self.assertEquals(self._get_connection_state_changes(), 5)


if __name__ == '__main__':
    testing.unittest.main()