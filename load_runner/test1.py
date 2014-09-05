# Copyright 2014 Symantec.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import time
import daemon
import zmq
import sys
import json


def recv_msg(socket):
    while True:
        data = socket.recv()
        message = json.loads(data)
        dest = message['ip']
        if dest is not None and dest != myip:
            continue
        return message

if __name__ == '__main__':
    with daemon.DaemonContext():
        myip = sys.argv[1]
        serverip = sys.argv[2]
        fd = open('/tmp/aaa', 'w')
        try:
            fd.write('Before rcv: %s:\n' % time.time())
            context = zmq.Context()
            socket = context.socket(zmq.SUB)
            socket.connect("tcp://" + serverip + ":5556")
            socket.setsockopt(zmq.SUBSCRIBE, '')
            message = recv_msg(socket)
            fd.write('%s: %s\n' % (time.time(), repr(message)))
        except Exception, exc:
            fd.write(str(exc))
            fd.flush()
            raise
