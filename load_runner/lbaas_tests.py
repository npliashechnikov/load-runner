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

from load_runner import remote
from load_runner import api_helpers


def ab_lbaas(test):
    tenants = test.tenants

    neutron = api_helpers.get_neutron_client()

    # Run clients...
    commands = []
    args = test.args.get('ab_args', [])
    url = test.args.get('url', '')
    for tenant in tenants:
        pool = neutron.create_pool(dict(pool={
            "tenant_id": tenant.tenant_id,
            "name": "web_pool",
            "protocol": "HTTP",
            "lb_method": "ROUND_ROBIN",
            "subnet_id": tenant.networks[0].subnet_id,
        }))['pool']
        vip = neutron.create_vip(dict(vip={
            "tenant_id": tenant.tenant_id,
            "name": "web_vip",
            "subnet_id": tenant.networks[0].subnet_id,
            "protocol": "HTTP",
            "protocol_port": 80,
            "pool_id": pool['id'],
            #"session_persistence" : {
            #"type":"APP_COOKIE", "cookie_name":"jsessionid"}
        }))['vip']

        url = test.args.get('url', '') % dict(vip=vip['address'])
        grouped_servers = tenant.group_servers_by_role()
        for server in grouped_servers['server']:
            neutron.create_member(dict(member={
                "address": server.private_ip,
                "protocol_port": 80,
                "pool_id": pool['id']
            }))

        for client in grouped_servers['client']:
            commands.append((client.management_ip, ['ab'] + args + [url]))

    print 'Running iperf...'
    results = remote.run_commands(
        commands, [], test.args.get('timeout', 600))

    for result in results:
        print result['results'][0]['error']
        print result['results'][0]['output']
