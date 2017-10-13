load-runner
===========

# Description

The load-runner tool prepares an environment to benchmark the network and storage performance in the OpenStack cloud. The tests use iperf running between client and server virtual machines and then demonstrate the results in csv format.

# Prerequisites

The load-runner tool requires access to public OpenStack API endpoints from its Master VM. For authentication it uses keystone v3 endpoint.
Internal/admin API endpoints do not need to be reachable from the VM.
The tool spawns VMs that need to have the following:
```
0. User with admin privileges
1. iperf3 installed
2. fio (at least 2.18) installed
3. command_agent.py installed and configured to run on boot
4. The 2 virtual NICs attached to the VMs should both be configured using DHCP and/or using config drive (when Neutron or DHCP server is not stable enough for spawning hundreds of VMs).
5. The VM image should be uploaded to glance and made public.
```

A management network should be created. This network should have connectivity to OpenStack API endpoints. This network should also have “shared” flag set to true so it can be connected to VMs in different projects.

Load-runner should be executed from a machine that has IPv4 route to the management network. It can be a bare metal machine when management network is provider network or have route to provider network, or a VM connected to management network otherwise.

# Installation

```
1. git clone https://github.com/Symantec/load-runner.git
2. cd load-runner 
3. sudo python setup.py install 
```

# Configuration

#### vim load_runner/settings.py

```
CONTROLLER_IP = '172.16.0.2' # This is the reachable IP address of the controller
OS_AUTH_URL = 'http://%s:5000/v2.0/' % CONTROLLER_IP # URL pointing to reachable keystone API endpoint
OS_USERNAME = 'admin' # Name of user with admin role
OS_TENANT = 'admin' # Name of project in which user have admin role
OS_PASSWORD = 'secrete' # Password for admin user
OS_DOMAIN_NAME = 'default' #Domain name to which the user belongs
OS_INSECURE = True #Enables/disables certificate verification in case of HTTPS endpoints
OS_REQUIRED_ROLES = ['admin'] #List additional roles required to get full admin privileges here in case of fancy cloud access policy.
OS_REGION_NAME = 'RegionOne' #Region name in case of multiple cloud partitions

SPAWN_DELAY = 0 # Delay in seconds between booting VMs to lower load on cluster
ACTIVATION_TIMEOUT = 120 # Wait time in seconds for VM state to change to ACTIVE
BOOT_TIMEOUT = 300 # Wait time in seconds for VM boot
TEST_TIMEOUT = 120 # Wait time in seconds to finish tests
MANAGEMENT_NETWORK_ID = '9398a44e-c170-4e50-affc-e4f321a67069' # UUID of the management network
MANAGEMENT_NET_NAME = 'mgmtnet' # Name of the management network
MANAGEMENT_CIDR = '192.168.111.0/24' # Management network CIDR
PRIVATE_CIDR = '192.168.0.0/24' # Base CIDR for private networks (plan it large enough to host all VMs user in tests)
FLAVOR_ID = '6' # Flavor ID of the iperf VM image.
IMAGE_ID = '0e6cfb31-5bd3-420f-b9a9-9494d5f3907a' # UUID of the iperf (slave) VM image.
UPDATE_NEUTRON_QUOTAS = False # True if network quotas need to be updated.
UPDATE_NOVA_QUOTAS = False # True if compute quotas need to be updated.
USE_DHCP = True # 'True' if network should be configured by DHCP. 'False' if configured by config drive.
```

#### vim test.yml
The tests can be described in this YAML file. Look at tests/ directory for more examples with availability zones, etc.
```
tests:
  - name: iperf_smoke_test                         # Name of the testcase
    procedure: load_runner.tests.iperf_pairs_zmq   # Name of the procedure
    args:
      iperf_args: ['-t', '3']                      # Iperf arguments
    tenants:
      - name: iperf_smoke_test                     # Name of the tenant
        networks:
          - name: private                          # Name of the network
            floating_ip: public                    
            servers:
              - role: server                       # Role of the VM
                count: 1                           # Number of VMs to be created
              - role: client
                count: 1
```


# Execution

```
python -m load_runner.run -t <test-name> -o <output-file>
```

# Useful links/Resources

TBD: https://github.com/Symantec/load-runner/wiki

# Notes 

1. Once the test resources are spun up, it can be re-used for running load-runner subsequently.
2. In case of spawning failure, process will be resumed using existing resources on a next run attempt.
3. Teardown is currently being implemented.
4. SOCKS proxy support for Openstack API access is being considered.

# License

Copyright 2014 Symantec Corporation.
Portions Copyright 2016-2017 Nikolay Pliashechnykov

Licensed under the Apache License, Version 2.0 (the “License”); you may not use this file except in compliance with the License. You may obtain a copy of the license at

http://www.apache.org/license/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an “AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

