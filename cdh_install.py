#!/usr/bin/env python

import os, sys
import socket
import time
import json
from deploy_cdh import Deploy
from common import *

repo_port = '8900'
# get configs
cfg = ParseConfig()
cdhnodes = cfg.get_item('hosts')
repo_dir = cfg.get_item('repo_dir')
parcel_dir = cfg.get_item('parcel_dir')

if not repo_dir: err('Failed to get repository dir')
if not parcel_dir: err('Failed to get parcel dir')

cdhmaster = cdhnodes[0]

with open('/etc/hosts', 'r') as f:
    lines = f.readlines()

hosts = [ [l for l in lines if h in l][0] for h in cdhnodes ]
hosts_json = json.dumps({'hosts':hosts})

hostname = socket.gethostname()
repo_ip = socket.gethostbyname(hostname)

installer_loc = sys.path[0]
ansible_cfg = os.getenv('HOME') + '/.ansible.cfg'
hosts_file = installer_loc + '/hosts'
ts = time.strftime('%y%m%d_%H%M')
logs_dir = installer_loc + '/logs'
if not os.path.exists(logs_dir): os.mkdir(logs_dir)
log_path = '%s/cdh_install_%s.log' %(logs_dir, ts)

# set ansible cfg
try:
    with open(ansible_cfg, 'w') as f:
        f.write('[defaults]\n')
        f.write('log_path = %s\n' % log_path)
        f.write('inventory =' + hosts_file + '\n')
        f.write('host_key_checking = False\n')
except IOError:
    log_err('Failed to open ansible.cfg file')

cdhnodes = [ i + '\n' for i in cdhnodes ]
try:
    with open(hosts_file, 'w') as f:
        f.write('\n[cdhmaster]\n')
        f.write(cdhmaster)
        f.write('\n[cdhnodes]\n')
        f.writelines(cdhnodes)
except IOError:
    log_err('Failed to open hosts file')


# main
user = sys.argv[1] if len(sys.argv)>1 else ''
http_start(repo_dir, repo_port)

cmd = 'ansible-playbook cm_install.yml -k --extra-vars='
cmd += '"repo_ip=%s repo_port=%s parcel_dir=%s"' % (repo_ip, repo_port, parcel_dir)
cmd += ' --extra-vars \'%s\'' % hosts_json
if user:
    cmd += ' -u %s' % user
info('Starting ansible playbook to deploy cloudera rpms')
print cmd
rc = os.system(cmd)

http_stop()

if rc:
    err('Failed to deploy cloudera')
else:
    info('Cloudera rpm deployed successfully!')

# config cdh
deploy = Deploy(cm_host=cdhmaster)
deploy.setup_cms()
deploy.setup_parcel()
deploy.start_cms()
deploy.setup_cdh()
deploy.start_cdh()
