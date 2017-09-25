import zmq
import time

POLL_TIMEOUT = 5000


def run_commands(commands, result=None, timeout=600):
    """
    Runs commands on remote servers by sending ZeroMQ messages to command
    execution agents. Os this agents must be installed and started before any
    command could be executed.
    commands is a list of (ip address, command) tuples.
    returns list of dictionaries with following keys:
      * address - IP address of machine that executed commands
      * start - time when server started to run commands
      * end - time when server completed to run commands
      * results - list of dictionaries with output key and error key which
                  contain standard output and error output respectevely
    """
    context = zmq.Context()

    bcast_socket = context.socket(zmq.PUB)
    bcast_socket.set(zmq.LINGER, 0)
    poll = zmq.Poller()
    sockets = {}

    grouped_commands = {}
    for address, command in commands:
        grouped_commands.setdefault(address, []).append(
            [str(c) for c in command])

    for address, commands in grouped_commands.items():
        bcast_socket.connect('tcp://%s:5501' % address)
        cmd_socket = context.socket(zmq.REQ)
        cmd_socket.set(zmq.LINGER, 0)
        cmd_socket.connect('tcp://%s:5500' % address)
        poll.register(cmd_socket, zmq.POLLIN)
        sockets[cmd_socket] = address
        cmd_socket.send_json(commands)

    deadline = time.time() + timeout
    while sockets and (timeout == 0 or time.time() < deadline):
        # Keep broadcasting 'start' command (in case some client missed it)
        bcast_socket.send_string('start')
        for socket, event in poll.poll(POLL_TIMEOUT):
            if event & zmq.POLLIN:
                address = sockets.pop(socket, None)
                if address is None:
                    continue
                response = socket.recv_json()
                response['address'] = address
                # TODO: store RAW response in persistent storage
                if result is not None:
                    result.append(response)

    return result
