import json
import collections
import csv
import sys

StreamStats = collections.namedtuple('StreamStats', [
    'min_bw', 'max_bw', 'total_bw', 'bytes', 'num_streams', 'cpu_total',
    'cpu_user', 'cpu_system'])


class Iperf3Stats(object):
    def __init__(self, test):
        self.test = test

        self.total_bw_rcv = 0.0
        self.total_bw_snd = 0.0
        self.total_data_rcv = 0.0
        self.total_data_snd = 0.0

        self.vm_min_bw_rcv = float('Inf')
        self.vm_min_bw_snd = float('Inf')
        self.vm_max_bw_rcv = 0.0
        self.vm_max_bw_snd = 0.0

        self.thread_min_bw_rcv = float('Inf')
        self.thread_min_bw_snd = float('Inf')
        self.thread_max_bw_rcv = 0.0
        self.thread_max_bw_snd = 0.0

        self.cpu_total_min_rcv = float('Inf')
        self.cpu_total_max_rcv = 0.0
        self.cpu_total_avg_sum_rcv = 0.0
        self.cpu_user_min_rcv = float('Inf')
        self.cpu_user_max_rcv = 0.0
        self.cpu_user_avg_sum_rcv = 0.0
        self.cpu_system_min_rcv = float('Inf')
        self.cpu_system_max_rcv = 0.0
        self.cpu_system_avg_sum_rcv = 0.0

        self.cpu_total_min_snd = float('Inf')
        self.cpu_total_max_snd = 0.0
        self.cpu_total_avg_sum_snd = 0.0
        self.cpu_user_min_snd = float('Inf')
        self.cpu_user_max_snd = 0.0
        self.cpu_user_avg_sum_snd = 0.0
        self.cpu_system_min_snd = float('Inf')
        self.cpu_system_max_snd = 0.0
        self.cpu_system_avg_sum_snd = 0.0

        self.num_vms = 0
        self.num_threads = 0

    def update_min(self, name, value):
        assert 'min' in name
        setattr(self, name, min(getattr(self, name), value))

    def update_max(self, name, value):
        assert 'max' in name
        setattr(self, name, max(getattr(self, name), value))

    def update(self, stream_stats_rcv, stream_stats_snd):
        self.total_bw_rcv += stream_stats_rcv.total_bw
        self.total_data_rcv += stream_stats_rcv.bytes
        self.total_bw_snd += stream_stats_snd.total_bw
        self.total_data_snd += stream_stats_snd.bytes

        self.update_min('vm_min_bw_rcv', stream_stats_rcv.total_bw)
        self.update_min('vm_min_bw_snd', stream_stats_snd.total_bw)
        self.update_max('vm_max_bw_rcv', stream_stats_rcv.total_bw)
        self.update_max('vm_max_bw_snd', stream_stats_snd.total_bw)

        self.update_min('thread_min_bw_rcv', stream_stats_rcv.min_bw)
        self.update_min('thread_min_bw_snd', stream_stats_snd.min_bw)
        self.update_max('thread_max_bw_rcv', stream_stats_rcv.max_bw)
        self.update_max('thread_max_bw_snd', stream_stats_snd.max_bw)

        self.update_min('cpu_total_min_rcv', stream_stats_rcv.cpu_total)
        self.update_max('cpu_total_max_rcv', stream_stats_rcv.cpu_total)
        self.cpu_total_avg_sum_rcv += stream_stats_rcv.cpu_total
        self.update_min('cpu_user_min_rcv', stream_stats_rcv.cpu_user)
        self.update_max('cpu_user_max_rcv', stream_stats_rcv.cpu_user)
        self.cpu_user_avg_sum_rcv += stream_stats_rcv.cpu_user
        self.update_min('cpu_system_min_rcv', stream_stats_rcv.cpu_system)
        self.update_max('cpu_system_max_rcv', stream_stats_rcv.cpu_system)
        self.cpu_system_avg_sum_rcv += stream_stats_rcv.cpu_system

        self.update_min('cpu_total_min_snd', stream_stats_snd.cpu_total)
        self.update_max('cpu_total_max_snd', stream_stats_snd.cpu_total)
        self.cpu_total_avg_sum_snd += stream_stats_snd.cpu_total
        self.update_min('cpu_user_min_snd', stream_stats_snd.cpu_user)
        self.update_max('cpu_user_max_snd', stream_stats_snd.cpu_user)
        self.cpu_user_avg_sum_snd += stream_stats_snd.cpu_user
        self.update_min('cpu_system_min_snd', stream_stats_snd.cpu_system)
        self.update_max('cpu_system_max_snd', stream_stats_snd.cpu_system)
        self.cpu_system_avg_sum_snd += stream_stats_snd.cpu_system

        self.num_vms += 1
        self.num_threads += stream_stats_rcv.num_streams

    def append(self, data):
        test = self.test
        address = data['address']
        for result in data['results']:
            output = result['output']
            try:
                json_result = json.loads(output)
            except ValueError:
                print ('Failed to parse JSON output of test'
                       ' %s on %s:' % (test.name, address))
                print '"""', data, '"""'
                continue

            error = json_result.get('error')
            if error is not None:
                print 'Error in test', test.name, 'of', address, ':', error
                continue

            stream_stats_rcv = aggregate_stream_stats(json_result, 'receiver')
            stream_stats_snd = aggregate_stream_stats(json_result, 'sender')
            self.update(stream_stats_rcv, stream_stats_snd)

    def output(self):
        test = self.test
        args = test.args
        iperf_args = args.get('iperf_args', [])

        def get_arg(arg, default):
            if arg in iperf_args:
                i = iperf_args.index(arg)
                return iperf_args[i + 1]
            else:
                return default

        mss = get_arg('-M', 'N/A')
        time = get_arg('-t', 'N/A')
        proto = 'UDP' if '-u' in iperf_args else 'TCP'
        tenants = sum(1 for t in test.tenants)
        networks = sum(sum(1 for n in t.networks) for t in test.tenants)

        def gbps(x):
            return '{0} Gbps'.format(x / 1000000000.0)

        def gbs(x):
            return '{0} Gbs'.format(x / 1073741824.0)

        result = collections.OrderedDict([
            ('Test Name', test.name),
            ('Protocol', proto),
            ('Number of Tenants', tenants),
            ('Number of Networks', networks),
            ('Number of VMs', self.num_vms),
            ('Num of threads', self.num_threads),
            ('Time', time),
            ('MSS', mss),
            ('Total bw rcv', gbps(self.total_bw_rcv)),
            ('Total bw snd', gbps(self.total_bw_snd)),
            ('Total data rcv', gbs(self.total_data_rcv)),
            ('Total data snd', gbps(self.total_data_snd)),
            ('VM min bw rcv', gbps(self.vm_min_bw_rcv)),
            ('VM min bw snd', gbps(self.vm_min_bw_snd)),
            ('VM max bw rcv', gbps(self.vm_max_bw_rcv)),
            ('VM max bw snd', gbps(self.vm_max_bw_snd)),
            ('VM avg bw rcv', gbps(self.total_bw_rcv / self.num_vms)),
            ('VM avg bw snd', gbps(self.total_bw_snd / self.num_vms)),
            ('Thread min bw rcv', gbps(self.thread_min_bw_rcv)),
            ('Thread min bw snd', gbps(self.thread_min_bw_snd)),
            ('Thread max bw rcv', gbps(self.thread_max_bw_rcv)),
            ('Thread max bw snd', gbps(self.thread_max_bw_snd)),
            ('Thread avg bw rcv', gbps(self.total_bw_rcv / self.num_threads)),
            ('Thread avg bw snd', gbps(self.total_bw_snd / self.num_threads)),
            ('CPU total min rcv', self.cpu_total_min_rcv),
            ('CPU total max rcv', self.cpu_total_max_rcv),
            ('CPU total avg rcv', self.cpu_total_avg_sum_rcv / self.num_vms),
            ('CPU user min rcv', self.cpu_user_min_rcv),
            ('CPU user max rcv', self.cpu_user_max_rcv),
            ('CPU user avg rcv', self.cpu_user_avg_sum_rcv / self.num_vms),
            ('CPU system min rcv', self.cpu_system_min_rcv),
            ('CPU system max rcv', self.cpu_system_max_rcv),
            ('CPU system avg rcv', self.cpu_system_avg_sum_rcv / self.num_vms),
            ('CPU total min snd', self.cpu_total_min_snd),
            ('CPU total max snd', self.cpu_total_max_snd),
            ('CPU total avg snd', self.cpu_total_avg_sum_snd / self.num_vms),
            ('CPU user min snd', self.cpu_user_min_snd),
            ('CPU user max snd', self.cpu_user_max_snd),
            ('CPU user avg snd', self.cpu_user_avg_sum_snd / self.num_vms),
            ('CPU system min snd', self.cpu_system_min_snd),
            ('CPU system max snd', self.cpu_system_max_snd),
            ('CPU system avg snd', self.cpu_system_avg_sum_snd / self.num_vms),
        ])
        writer = csv.writer(sys.stdout)
        writer.writerow(result.keys())
        writer.writerow(result.values())


def aggregate_stream_stats(data, key):
    if key == 'sender':
        cpu_key = 'host'
    else:
        cpu_key = 'remote'
    streams = data['end']['streams']
    cpu_data = data['end']['cpu_utilization_percent']
    return StreamStats(min(s[key]['bits_per_second'] for s in streams),
                       max(s[key]['bits_per_second'] for s in streams),
                       sum(s[key]['bits_per_second'] for s in streams),
                       sum(s[key]['bytes'] for s in streams),
                       len(streams),
                       cpu_data[cpu_key + '_total'],
                       cpu_data[cpu_key + '_user'],
                       cpu_data[cpu_key + '_system'])
