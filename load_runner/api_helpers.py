

from keystoneclient.v3.client import Client
from neutronclient.neutron import client as neutron
from novaclient.v2 import client as nova
from cinderclient.v2.client import Client as cinder

from cinderclient import exceptions as cinder_exceptions
from novaclient import exceptions as nova_exceptions
from keystoneclient import exceptions as keystone_exceptions
from neutronclient.client import exceptions as neutron_exceptions

import settings
import sys
import time
import traceback

all_ports = {}
cinder_clients = {}
keystone_client = None
neutron_client = None
nova_clients = {}
servers = {}
keystone_session = None
fips = {}


def get_keystone_session(tenant_name=None, tenant_id=None):
    url = settings.OS_AUTH_URL
    keystone_client = Client(user_domain_name=settings.OS_DOMAIN_NAME,
                             username=settings.OS_USERNAME, password=settings.OS_PASSWORD,
                             project_name=tenant_name,
                             project_id=tenant_id,
                             project_domain_name=settings.OS_DOMAIN_NAME,
                             auth_url=settings.OS_AUTH_URL.replace('/v2.0', '/v3'),
                             insecure=settings.OS_INSECURE,
                             region=settings.OS_REGION_NAME,
                             endpoint=settings.OS_AUTH_URL.replace('/v2.0', '/v3'))

    keystone_client.authenticate()
    keystone_session = keystone_client.session
    return keystone_client, keystone_session


def get_keystone_client():
    global keystone_client
    global keystone_session

    if keystone_client is None:
        url = settings.OS_AUTH_URL
        keystone_client, keystone_session = get_keystone_session(settings.OS_TENANT)

    return keystone_client


def get_neutron_client():
    global neutron_client
    if not keystone_session:
        get_keystone_client()
    if neutron_client is None:
        neutron_client = neutron.Client('2.0',
                                        session=keystone_session,
                                        insecure=settings.OS_INSECURE)
    return neutron_client


def get_nova_client(tenant_id=None):
    global nova_clients
    client = nova_clients.get(tenant_id)
    if client is None:
        if tenant_id is None:
            tenant_name = settings.OS_TENANT
        else:
            tenant_name = None
        _, session = get_keystone_session(tenant_name, tenant_id)

        client = nova.Client(session=session, insecure=settings.OS_INSECURE)
        nova_clients[tenant_id] = client
    return client


def get_cinder_client(tenant_id=None):
    global cinder_clients
    client = cinder_clients.get(tenant_id)

    if client is None:
        if tenant_id is None:
            tenant_name = settings.OS_TENANT
        else:
            tenant_name = None
        _, session = get_keystone_session(tenant_name, tenant_id)

        client = cinder(session=session, insecure=settings.OS_INSECURE)
        cinder_clients[tenant_id] = client
    return client


def get_or_create_tenant(tenant_name):
    client = get_keystone_client()
    try:
        tenant = client.projects.find(name=tenant_name)
    except keystone_exceptions.NotFound:
        try:
            tenant = client.projects.create(tenant_name, settings.OS_DOMAIN_NAME)
        except keystone_exceptions.Forbidden:
            print "Unable to create tenant. Please check if user has admin privileges"
            sys.exit(1)
        time.sleep(4) # allow for Contrail to sync with Keystone

    def user_ensure_role(name):
        try:
            role_id = client.roles.find(name=name).id
        except keystone_exceptions.NotFound:
            print "role %s not found. Please check configuration." % name
            sys.exit(1)
        try:
            client.roles.grant(role_id, user=user_id, project=tenant.id)
        except keystone_exceptions.Forbidden:
            print "Can't grant role %s in tenant %s - access denied. Please check if user has admin privileges." % (role_id, tenant.id)
            sys.exit(1)
        except keystone_exceptions.Conflict:
            print "Role %s already granted for %s in %s - proceeding." % (role_id, user_id, tenant.id)
            return

    user_id = client.users.find(name=settings.OS_USERNAME).id
    for role in settings.OS_REQUIRED_ROLES:
        user_ensure_role(role)

    if settings.UPDATE_NEUTRON_QUOTAS:
        get_neutron_client().update_quota(
            tenant.id, {
                'quota': {
                    'network': 100000,
                    'floatingip': 500000,
                    'security_group_rule': 500000,
                    'security_group': 500000,
                    'router': 10,
                    'port': 500000,
                    'subnet': 100000
                }
            })
    return tenant.id


def delete_tenant(tenant_id):
    client = get_keystone_client()
    try:
        client.projects.delete(tenant_id)
    except keystone_exceptions.Forbidden:
        print "Unable to delete tenant %s - access denied."


def get_or_create_network(tenant_id, network_name):
    client = get_neutron_client()
    existing = client.list_networks(
        name=network_name, tenant_id=tenant_id).get('networks', [])
    if not existing:
        try:
            network = client.create_network({'network': {
                'name': network_name,
                'admin_state_up': True,
                'tenant_id': tenant_id}})['network']
        except neutron_exceptions.Forbidden:
            print 'Unable to create network in tenant %s - access denied.' % tenant_id
            sys.exit(1)
    else:
        network = existing[0]
    return network['id']


def delete_network(network_id):
    client = get_neutron_client()
    try:
        client.delete_network(network_id)
    except neutron_exceptions.Forbidden:
        print 'Unable to delete network %s - access denied.' % network_id
    except neutron_exceptions.Conflict:
        print 'Unable to delete network %s - ports still exist in it.' % network_id


def get_or_create_subnet(tenant_id, network_id, network_name, cidr):
    client = get_neutron_client()
    existing = client.list_subnets(network_id=network_id).get('subnets', [])
    if existing:
        if existing[0]['cidr'] != cidr:
            raise RuntimeError('Subnet in existing network is different from '
                               'requested. Tear down environment and set it up'
                               ' again to change network CIDRs.')
        else:
            return existing[0]['id']
    try:
        subnet = client.create_subnet({
            'subnet': {
                'name': network_name,
                'network_id': network_id,
                'tenant_id': tenant_id,
                'enable_dhcp': True,
                'dns_nameservers': ['8.8.8.8'],
                'cidr': cidr,
                'ip_version': 4
            }
        })
    except neutron_exceptions.Forbidden:
        print 'Unable to create subnet - access denied. Ensure the user has rights to create subnets.'
        sys.exit(1)

    return subnet['subnet']['id']


def create_server(tenant_id, network_id, name, key_name,
                  availability_zone=None, scheduler_hints=None,
                  floating_ip=None):
    if settings.USE_DHCP:
        return create_server_dhcp(
            tenant_id, network_id, name, key_name, availability_zone,
            scheduler_hints, floating_ip=floating_ip)
    else:
        return create_server_config_drive(
            tenant_id, network_id, name, key_name, availability_zone,
            scheduler_hints, floating_ip=floating_ip)


def create_server_config_drive(tenant_id, network_id, name, key_name,
                               availability_zone=None, scheduler_hints=None,
                               floating_ip=None):
    """
    Function that creates server with network configuration using config
    drive.
    """
    if settings.SPAWN_DELAY:
        time.sleep(settings.SPAWN_DELAY)
    neutron_client = get_neutron_client()

    MAX_TRIES = 15
    tries = 0
    private_port = None
    management_port = None

    while tries < MAX_TRIES:
        tries += 1
        try:
            private_port = neutron_client.create_port(
                {'port': {'tenant_id': tenant_id, 'network_id': network_id}})
            private_port = private_port['port']
            break
        except:
            traceback.print_exc()
            if tries >= MAX_TRIES:
                raise
            print 'For', tries, 'time, sleeping 20 sec...'
            time.sleep(20)

    tries = 0
    while tries < MAX_TRIES:
        tries += 1
        try:
            management_port = neutron_client.create_port(
                {'port': {'tenant_id': tenant_id,
                          'network_id': settings.MANAGEMENT_NETWORK_ID}})
            management_port = management_port['port']
            break
        except:
            traceback.print_exc()
            if tries >= MAX_TRIES:
                raise
            print 'For', tries, 'time, sleeping 20 sec...'
            time.sleep(20)

    if not (private_port and management_port):
        print "Port creation failed in Neutron. Please check cloud configuration."
        sys.exit(1)

    private_ip = private_port['fixed_ips'][0]['ip_address']
    management_ip = management_port['fixed_ips'][0]['ip_address']

    client = get_nova_client(tenant_id)
    server = client.servers.create(
        name, settings.IMAGE_ID, settings.FLAVOR_ID,
        nics=[{'port-id': management_port['id']},
              {'port-id': private_port['id']}],
        meta={'management_ip': management_ip,
              'management_mac': management_port['mac_address'],
              'private_ip': private_ip,
              'private_mac': private_port['mac_address']},
        config_drive=True,
        key_name=key_name,
        availability_zone=availability_zone,
        scheduler_hints=scheduler_hints)
    return server.id, private_ip, management_ip


def create_server_dhcp(tenant_id, network_id, name, key_name,
                       availability_zone=None, scheduler_hints=None,
                       floating_ip=None):
    print "started creating server"
    if settings.SPAWN_DELAY:
        time.sleep(settings.SPAWN_DELAY)

    client = get_nova_client(tenant_id)
    server = client.servers.create(
        name, settings.IMAGE_ID, settings.FLAVOR_ID,
        nics=[{'net-id': settings.MANAGEMENT_NETWORK_ID},
              {'net-id': network_id}],
        key_name=key_name,
        availability_zone=availability_zone,
        scheduler_hints=scheduler_hints)
    initial_t = time.time()
    while True:
 
        t = time.time()
        server = client.servers.get(server.id)
        if server.status == 'ERROR':
            raise Exception("Server %s failed to spawn"%server.id)
        if hasattr(server, 'networks'):
            try:
                server_nets = server.networks
                management_ip = server_nets.pop(settings.MANAGEMENT_NAME)[0]
                private_ip = server_nets.values()[0][0]
                if time.time() - initial_t > settings.BOOT_TIMEOUT:
                    print "Timeout while waiting for server %s to boot, terminating test." % server.id
                    sys.exit(1)
                break
            except Exception, e:
                pass  # avoid intermittent Nova/Contrail failures
        time.sleep(settings.API_QUERY_TIMEOUT)
        print (time.time() - t)

    if floating_ip is not None:
        fip = get_free_floatingip(tenant_id, floating_ip)
        if fip is None:
            fip = create_free_floatingip(tenant_id, floating_ip)
        assign_floating_ip(fip, server.id, network_id)

    print "finished creating server"
    return server.id, private_ip, management_ip


def terminate_server(server_id):
    client = get_nova_client()
    client.servers.delete(server_id)


def get_server(server_id):
    client = get_nova_client()
    try:
        server = client.servers.get(server_id)
        return server
    except nova_exceptions.NotFound:
        return None


def get_or_create_router(tenant_id, name, args):
    client = get_neutron_client()
    routers = client.list_routers(
        tenant_id=tenant_id, name=name).get('routers', [])
    if routers:
        return routers[0]['id']
    else:
        # Create router and connect it to all the networks
        data = dict(args.items())
        data['tenant_id'] = tenant_id
        data['name'] = name
        try:
            router = client.create_router(dict(router=data))
        except neutron_exceptions.Forbidden:
            print 'Creating router failed - access denied.'
            sys.exit(1)

        return router['router']['id']


def delete_router(router_id):
    client = get_neutron_client()
    client.delete_router(router_id)


def add_router_interface(router_id, network_id, subnet_id):
    client = get_neutron_client()
    for port in client.list_ports(network_id=network_id).get('ports', []):
        if port['device_owner'] != 'network:router_interface':
            continue
        for fip in port['fixed_ips']:
            if fip['subnet_id'] == subnet_id:
                other_router_id = port['device_id']
                if other_router_id == router_id:
                    return
                client.remove_interface_router(
                    other_router_id, {'subnet_id': subnet_id})
                break
    client.add_interface_router(router_id, {'subnet_id': subnet_id})


def remove_router_interface(router_id, subnet_id):
    client = get_neutron_client()
    client.remove_interface_router(router_id, {'subnet_id': subnet_id})


def get_servers(tenant_id):
    client = get_nova_client(tenant_id)
    return [s for s in client.servers.list(detailed=True)]


def ensure_default_sg_state(tenant_id):
    client = get_neutron_client()
    # Add 'allow all ingress ipv4 traffic' rule to default security group
    security_groups = client.list_security_groups(
        tenant_id=tenant_id, name='default').get('security_groups', [])
    security_group = security_groups[0]
    # Remove rules with remote_group_id or IPv6
    need_allow = {'ingress', 'egress'}
    try:
        for rule in security_group['security_group_rules']:
            if rule['remote_group_id'] is not None or rule['ethertype'] != 'IPv4':
                client.delete_security_group_rule(rule['id'])
            elif (rule['direction'] == 'ingress' and
                  rule['remote_ip_prefix'] == '0.0.0.0/0'):
                need_allow.discard('ingress')
            elif (rule['direction'] == 'egress' and
                  rule['remote_ip_prefix'] == '0.0.0.0/0'):
                need_allow.discard('egress')
        # Add allow all security group
        for direction in need_allow:
            client.create_security_group_rule({
                'security_group_rule': {
                    'security_group_id': security_group['id'],
                    'direction': direction,
                    'ethertype': 'IPv4',
                    'tenant_id': tenant_id,
                    'remote_ip_prefix': '0.0.0.0/0'
                }
            })
    except neutron_exceptions.Forbidden:
        print 'Security group operation failed - access denied.'
        sys.exit(1)


def get_ports(tenant_id):
    client = get_neutron_client()
    result = {}
    ports = client.list_ports(tenant_id=tenant_id)['ports']
    for port in ports:
        if port['device_owner'].startswith('network:'):
            continue
        result.setdefault(port['device_id'], []).append(port['network_id'])
    return result


def get_network_servers(network_id):
    client = get_neutron_client()
    result = set()
    ports = client.list_ports(network_id=network_id)['ports']
    for port in ports:
        if port['device_owner'].startswith('network:'):
            continue
        if port['device_owner'].startswith('neutron:'):
            continue
        result.add(port['device_id'])
    return result


def get_free_floatingip(tenant_id, network_id):
    global fips
    client = get_neutron_client()
    if not fips.has_key(tenant_id+network_id):
        fips[tenant_id+network_id] = client.list_floatingips(tenant_id=tenant_id)['floatingips']
    for fip in fips[tenant_id+network_id]:
        if fip['port_id'] is None:
            fips[tenant_id+network_id].remove(fip)
            return fip
    return None


def create_free_floatingip(tenant_id, network_id):
    client = get_neutron_client()
    try:
        return client.create_floatingip(
            dict(floatingip=dict(tenant_id=tenant_id,
                                 floating_network_id=network_id)))['floatingip']
    except neutron_exceptions.Forbidden:
        print 'Floating IP creation failed - access denied.'
        sys.exit(1)


def assign_floating_ip(fip, server_id, network_id):
    client = get_neutron_client()
    ports = client.list_ports(device_id=server_id)['ports']
    for port in ports:
        if port['network_id'] == network_id:
            break
    else:
        raise RuntimeError('Failed to find port in net {0} for server '
                           '{1}'.format(network_id, server_id))
    client.update_floatingip(
        fip['id'],
        dict(floatingip={
            'port_id': port['id'],
            'fixed_ip_address': port['fixed_ips'][0]['ip_address']}))


def get_data_ip(server_id, network_id, floating_ip):
    x = time.time()
    client = get_neutron_client()

    ports = all_ports.get(server_id)
    if ports is None:
        ports1 = client.list_ports()['ports']
        for p in ports1:
            all_ports.setdefault(p['device_id'], []).append(p)
        ports = all_ports.get(server_id, [])

    for port in ports:
        if port['network_id'] == network_id:
            break
    else:
        raise RuntimeError('Failed to find port in net {0} for server '
                           '{1}'.format(network_id, server_id))

    print 'took', (time.time() - x)

    if floating_ip is None or True:
        return port['fixed_ips'][0]['ip_address']

    fips = client.list_floatingips(port_id=port['id'])['floatingips']
    for fip in fips:
        if fip['port_id'] == port['id']:
            return fip['floating_ip_address']

    print 'took', (time.time() - x)

    return None
