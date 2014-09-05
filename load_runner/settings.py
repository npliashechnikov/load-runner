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

CONTROLLER_IP = '172.16.0.2'
OS_AUTH_URL = 'http://%s:5000/v2.0/' % CONTROLLER_IP
OS_SERVICE_ENDPOINT = 'http://%s:35357/v2.0/' % CONTROLLER_IP
OS_USERNAME = 'admin'
OS_TENANT = 'admin'
OS_PASSWORD = 'admin'
OS_TOKEN = 'PKUiCQHi'
SPAWN_DELAY = 0
ACTIVATION_TIMEOUT = 120
BOOT_TIMEOUT = 300
TEST_TIMEOUT = 120

MANAGEMENT_NETWORK_ID = '9398a44e-c170-4e50-affc-e4f321a67069'
MANAGEMENT_NET_NAME = 'mgmtnet'
MANAGEMENT_CIDR = '192.168.111.0/24'
PRIVATE_CIDR = '192.168.0.0/24'
FLAVOR_ID = '6'
IMAGE_ID = '0e6cfb31-5bd3-420f-b9a9-9494d5f3907a'
ROOT_DIR = '/tmp'

UPDATE_NEUTRON_QUOTAS = False  # Set to False for Contrail testing
USE_DHCP = True  # Set to True for Contrail testing
