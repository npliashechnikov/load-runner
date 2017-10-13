import itertools
import json
import random
import os
import time

from load_runner import remote
from load_runner import settings
from load_runner.data import iperf3, fio
from load_runner.data import ping


def random_pairs(clients, servers, extend=False):
    clients = list(clients)
    servers = list(servers)

    if len(clients) == 0 or len(servers) == 0:
        return []

    if extend:
        if len(servers) > len(clients):
            servers = list(itertools.cycle(servers)[0:len(clients)])
        elif len(servers) < len(clients):
            clients = list(itertools.cycle(clients)[0:len(servers)])
    random.shuffle(clients)
    random.shuffle(servers)
    return zip(clients, servers)


def iperf_pairs_zmq(test):
    tenants = test.tenants

    kill_commands = []
    run_kill = ['killall', 'iperf3']
    for group in test.group_servers_by_role().values():
        for server in group:
            kill_commands.append((server.management_ip, run_kill))
    remote.run_commands(
        kill_commands, timeout=test.args.get('server_timeout', 30))

    # Prepare servers...
    clients = {}
    server_commands = []
    run_server = ['/usr/local/bin/iperf3', '-s', '-D', '-p', '8200']
    for tenant in tenants:
        grouped_servers = tenant.group_servers_by_role()
        for server, client in random_pairs(grouped_servers['server'],
                                           grouped_servers['client']):
            clients[server.management_ip] = (client, server)
            server_commands.append(
                (server.management_ip,
                 ['ping', '-c', '1', '-W', '1', client.private_ip]))
            server_commands.append((server.management_ip, run_server))
    server_results = remote.run_commands(
        server_commands, [], test.args.get('server_timeout', 30))

    # Run clients...
    client_commands = []
    additional_args = test.args.get('iperf_args', [])
    for server_address in set(r['address'] for r in server_results):
        client, server = clients[server_address]
        run_client = ['/usr/local/bin/iperf3', '-c', server.private_ip, '-p',
                      '8200', '--json']
        run_client.extend(additional_args)
        client_commands.append((client.management_ip, run_client))

    print 'Running iperf...'
    client_results = remote.run_commands(
        client_commands, iperf3.Iperf3Stats(test),
        test.args.get('client_timeout', 600))

    client_results.output()


def ping_pairs(test):
    ping_count = test.args.get('ping_count', 10)
    tenants = test.tenants

    # Prepare servers...
    commands = []
    for tenant in tenants:
        grouped_servers = tenant.group_servers_by_role()
        for server, client in random_pairs(grouped_servers['server'],
                                           grouped_servers['client']):
            commands.append(
                (client.management_ip,
                 ['ping', '-c', ping_count, '-W', '1', server.private_ip]))
            commands.append(
                (server.management_ip,
                 ['ping', '-c', ping_count, '-W', '1', client.private_ip]))

    print 'Running pings...'
    results = remote.run_commands(
        commands, ping.PingStats(test),
        test.args.get('timeout', ping_count * 2))

    results.output()


def iperf_gateway(test):
    # Generate list of servers
    def server_list():
        ips = ['10.119.150.' + str(i) for i in range(194, 213)]
        for port in range(5200, 5300, 2):
            for ip in ips:
                yield {'ip': ip, 'port': port}
    servers = server_list()

    # Prepare servers...
    client_commands = []
    additional_args = test.args.get('iperf_args', [])
    for tenant in test.tenants:
        grouped_servers = tenant.group_servers_by_role()
        for client, server in zip(grouped_servers['client'], servers):
            run_client1 = ['/usr/local/bin/iperf3', '-c', server['ip'],
                           '-p', server['port'], '--json']
            run_client1.extend(additional_args)
            client_commands.append((client.management_ip, run_client1))

    print len(client_commands), 'pairs generated.'

    print 'Running iperf...'
    client_results = remote.run_commands(
        client_commands, iperf3.Iperf3Stats(test),
        test.args.get('client_timeout', 600))

    client_results.output()


def iperf_pairs_duplex(test):
    tenants = test.tenants

    kill_commands = []
    run_kill = ['killall', 'iperf3']
    for group in test.group_servers_by_role().values():
        for server in group:
            kill_commands.append((server.management_ip, run_kill))
    remote.run_commands(
        kill_commands, timeout=test.args.get('server_timeout', 30))

    # Prepare servers...
    server_commands = []
    run_server = ['/usr/local/bin/iperf3', '-s', '-D', '-p', '8200']
    for group in test.group_servers_by_role().values():
        for server in group:
            server_commands.append((server.management_ip, run_server))
    remote.run_commands(server_commands,
                        timeout=test.args.get('server_timeout', 30))

    # Run clients...
    client_commands = []
    additional_args = test.args.get('iperf_args', [])
    for tenant in tenants:
        grouped_servers = tenant.group_servers_by_role()
        for server, client in random_pairs(grouped_servers['server'],
                                           grouped_servers['client']):
            run_client = ['/usr/local/bin/iperf3', '-c', server.private_ip,
                          '-p', '8200', '--json']
            run_client.extend(additional_args)
            run_server = ['/usr/local/bin/iperf3', '-c', client.private_ip,
                          '-p', '8200', '--json']
            run_server.extend(additional_args)

            client_commands.append((client.management_ip, run_client))
            client_commands.append((server.management_ip, run_server))

    print 'Running iperf...'
    client_results = remote.run_commands(
        client_commands, iperf3.Iperf3Stats(test),
        test.args.get('client_timeout', 600))

    client_results.output()


def fio_volumes(test):
    tenants = test.tenants

    kill_commands = []
    run_kill = ['killall', 'fio']
    for group in test.group_servers_by_role().values():
        for server in group:
            kill_commands.append((server.management_ip, run_kill))
    remote.run_commands(
        kill_commands, timeout=test.args.get('server_timeout', 30))


    # Run clients...

    prepare_commands = []
    client_commands = []
    device_name = test.args.get('device_name', '/dev/vdb')
    prepare_fs = ['/sbin/mkfs.ext4', device_name]
    mount_point = test.args.get('mount_point', '/mnt/fiodisk')
    mount_vol = ['mount', device_name, mount_point]

    for group in test.group_servers_by_role().values():
        for server in group:
            prepare_commands.append((server.management_ip, prepare_fs))
            prepare_commands.append((server.management_ip, mount_vol))

    print 'formatting and mounting volumes...'
    client_results = remote.run_commands(
        prepare_commands,
        test.args.get('server_timeout', 30))

    additional_args = test.args.get('fio_args', [])

    run_fio = ['fio', '--directory=', mount_point, '--name=', test.name, '--output-format=', 'json', '--group_reporting'].extend(additional_args)
    print 'Running fio...'
    for group in test.group_servers_by_role().values():
        for server in group:
            client_commands.append((server.management_ip, run_fio))

    client_results = remote.run_commands(
        client_commands, fio.FioStats(test),
        test.args.get('client_timeout', 600))

    client_results.output()


def fio_ephemeral(test):
    tenants = test.tenants

    kill_commands = []
    run_kill = ['killall', 'fio']
    for group in test.group_servers_by_role().values():
        for server in group:
            kill_commands.append((server.management_ip, run_kill))
    remote.run_commands(
        kill_commands, timeout=test.args.get('server_timeout', 30))


    # Run clients...

    client_commands = []
    additional_args = test.args.get('fio_args', [])

    run_fio = ['fio', '--directory=', '/tmp', '--name=', test.name, '--output-format=', 'json', '--group_reporting'].extend(additional_args)
    print 'Running fio...'
    for group in test.group_servers_by_role().values():
        for server in group:
            client_commands.append((server.management_ip, run_fio))

    client_results = remote.run_commands(
        client_commands, fio.FioStats(test),
        test.args.get('client_timeout', 600))

    client_results.output()

