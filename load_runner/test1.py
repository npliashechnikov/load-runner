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
