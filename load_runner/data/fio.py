import json
import stat
import collections
import csv
import sys

StreamStats = collections.namedtuple('StreamStats', [
    'min_bw_read', 'max_bw_read', 'total_bw_read',
    'min_bw_write', 'max_bw_write', 'total_bw_write',
    'read_iops', 'write_iops', 'read_latency', 'write_latency',
    'read_bytes', 'write_bytes', 'numjobs',
    'disk_util', 'cpu_user', 'cpu_system', 'num_streams'])


class FioStats(object):

    def __init__(self, test):
        self.test = test

        self.block_size = '1'
        self.name = 'test'

        self.usr_cpu = []
        self.sys_cpu = []
        self.read_bytes = 0
        self.write_bytes = 0
        self.read_iops = []
        self.write_iops = []
        self.read_bw = []
        self.write_bw = []
        self.read_bw_min = []
        self.write_bw_min = []
        self.read_bw_max = []
        self.write_bw_max = []
        self.read_latency = []
        self.write_latency = []

        self.disk_util = []
        self.num_vms = 0
        self.num_threads = 0

    def update(self, stream_stats_rcv):
        self.usr_cpu.append(stream_stats_rcv.cpu_user)
        self.sys_cpu.append(stream_stats_rcv.cpu_system)
        self.read_bw.append(stream_stats_rcv.total_bw_read)
        self.write_bw.append(stream_stats_rcv.total_bw_write)
        self.read_bw_min.append(stream_stats_rcv.min_bw_read)
        self.read_bw_max.append(stream_stats_rcv.max_bw_read)
        self.write_bw_min.append(stream_stats_rcv.min_bw_write)
        self.write_bw_max.append(stream_stats_rcv.max_bw_write)
        self.read_latency.append(stream_stats_rcv.read_latency)
        self.write_latency.append(stream_stats_rcv.write_latency)
        self.read_iops.append(stream_stats_rcv.read_iops)
        self.write_iops.append(stream_stats_rcv.write_iops)
        self.disk_util.append(stream_stats_rcv.disk_util)

        self.num_vms += 1
        self.num_threads += stream_stats_rcv.num_streams

    def append(self, data):
        test = self.test
        for result in data:
            try:
                json_result = json.loads(result)
            except ValueError:
                print ('Failed to parse JSON output of test'
                       ' %s on %s:' % test.name)
                print '"""', data, '"""'
                continue

            error = json_result.get('error')
            if error is not None:
                print 'Error in test', test.name, 'of', ':', error
                continue

            stream_stats_rcv = aggregate_stream_stats(json_result)
            self.update(stream_stats_rcv)

    def output(self):
        def avg(arr):
            return sum(arr) / len(arr) if arr else 0

        test = self.test
        args = test.args

        result = collections.OrderedDict()
        result['Test Name'] = test.name
        # Anti-aliasing is applied to min/max values
        result['Min Read B/W'] = avg(self.read_bw_min)
        result['Max Read B/W'] = avg(self.read_bw_max)
        result['Avg Read B/W'] = avg(self.read_bw)
        result['Min Write B/W'] = avg(self.write_bw_min)
        result['Max Write B/W'] = avg(self.write_bw_max)
        result['Avg Write B/W'] = avg(self.write_bw)
        result['Avg Read IOPS'] = avg(self.read_iops)
        result['Avg Write IOPS'] = avg(self.write_iops)
        result['Avg Read Latency'] = avg(self.read_latency)
        result['Avg Write Latency'] = avg(self.write_latency)
        result['Avg Disk Util'] = avg(self.disk_util)
        result['Avg SYS CPU Util'] = avg(self.sys_cpu)
        result['Avg USR CPU Util'] = avg(self.usr_cpu)

        writer = csv.writer(sys.stdout)
        writer.writerow(result.keys())
        writer.writerow(result.values())


# TODO: add 90-99 percentile latencies support
def aggregate_stream_stats(data):
    streams = data['jobs']

    return StreamStats(streams['read']['bw_min'], streams['read']['bw_max'], streams['read']['bw_agg'],
                       streams['write']['bw_min'], streams['write']['bw_max'], streams['write']['bw_agg'],
                       streams['read']['iops'], streams['write']['iops'],
                       streams['read']['lat']['mean'], streams['write']['lat']['mean'],
                       streams['read']['io_bytes'], streams['write']['io_bytes'],
                       streams['usr_cpu'], streams['sys_cpu'], streams['disk_util']['util'])
