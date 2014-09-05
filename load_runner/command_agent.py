import time
import zmq
import subprocess

commands = []
POLL_TIMEOUT = 5


def run_commands():
    global commands

    commands, executing = [], commands

    start_time = time.time()

    processes = []
    for command in executing:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        processes.append((proc, command))

    print 'Waiting for', len(executing), 'commands to complete.'

    results = []
    for proc, command in processes:
        out, error = proc.communicate()
        results.append(dict(output=out, error=error, command=command))

    return dict(start=start_time, end=time.time(), results=results)


def main():
    context = zmq.Context()

    poll = zmq.Poller()

    cmd_socket = context.socket(zmq.REP)
    cmd_socket.bind("tcp://*:5500")

    bcast_socket = context.socket(zmq.SUB)
    bcast_socket.setsockopt(zmq.SUBSCRIBE, '')
    bcast_socket.bind("tcp://*:5501")

    poll.register(cmd_socket, zmq.POLLIN)
    poll.register(bcast_socket, zmq.POLLIN)

    while True:
        socks = dict(poll.poll(POLL_TIMEOUT))

        if socks.get(cmd_socket) == zmq.POLLIN:
            cmds = cmd_socket.recv_json()
            for command in cmds:
                print 'Adding command: %s' % command
                commands.append(command)

        if socks.get(bcast_socket) == zmq.POLLIN:
            bcast_cmd = bcast_socket.recv_string()
            if bcast_cmd == 'start' and commands:
                output = run_commands()
                cmd_socket.send_json(output)


if __name__ == '__main__':
    main()
