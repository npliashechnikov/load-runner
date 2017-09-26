CONTROLLER_IP = '172.16.0.2'
OS_AUTH_URL = 'https://%s:5000/v2.0/' % CONTROLLER_IP
OS_SERVICE_ENDPOINT = 'https://%s:35357/v2.0/' % CONTROLLER_IP
OS_DOMAIN_NAME='default'
OS_USERNAME = 'admin'
OS_TENANT = 'admin'
OS_PASSWORD = 'changeme'
OS_INSECURE = True

OS_REQUIRED_ROLES = ['admin']
SPAWN_DELAY = 0
OS_REGION_NAME='RegionOne'
ACTIVATION_TIMEOUT = 120
BOOT_TIMEOUT = 120
TEST_TIMEOUT = 120
API_QUERY_TIMEOUT = 0.5

MANAGEMENT_NETWORK_ID = 'changeme'
MANAGEMENT_NAME = 'lr-net'
MANAGEMENT_CIDR = '192.168.0.0/16'
PRIVATE_CIDR = '172.16.32.0/24'
FLAVOR_ID = '2'
IMAGE_ID = 'changeme' #Insert lr-slave image ID here
ROOT_DIR = '/tmp'

UPDATE_NEUTRON_QUOTAS = True #Set to False for Contrail testing
USE_DHCP = True  # Set to True for Contrail testing
