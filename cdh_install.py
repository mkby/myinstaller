#!/usr/bin/env python

import os, sys
import socket
import time
import json
from ConfigParser import ConfigParser
from deploy_cdh import Deploy


def info(msg):
    print '\n\33[33m***[INFO]: %s \33[0m' % msg

def err(msg):
    print '\n\33[31m***[ERROR]: %s \33[0m' % msg
    exit(0)

# get configs
config_file = 'config.ini'
repo_port = '8900'
conf = ConfigParser()
conf.read(config_file)
try:
    hosts_data = conf.items('hosts')
    cdh_config = conf.items('cdh_config')
except:
    err('Failed to read config file %s' % config_file)


try:
    cdhnodes = [ i.strip() for i in hosts_data[0][1].split(',') ]
    cdhmaster = cdhnodes[0]

    for cfg in cdh_config:
        if cfg[0] == 'repo_dir': repo_dir = cfg[1]
        #if cfg[0] == 'repo_port': repo_port = cfg[1]
        if cfg[0] == 'parcel_dir': parcel_dir = cfg[1]
except IndexError:
    err('Failed to parse hosts from %s' % config_file)

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
log_path = '%s/cdh_install_%s.log' %(installer_loc, ts)

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
info('Starting temporary python http server')
os.system("cd %s; python -m SimpleHTTPServer %s > /dev/null 2>&1 &" % (repo_dir, repo_port))

cmd = 'ansible-playbook cm_install.yml -k --extra-vars='
cmd += '"repo_ip=%s repo_port=%s parcel_dir=%s"' % (repo_ip, repo_port, parcel_dir)
cmd += ' --extra-vars \'%s\'' % hosts_json
info('Starting ansible playbook to deploy cloudera rpms')
rc = os.system(cmd)

info('Stopping python http server')
os.system("ps -ef|grep SimpleHTTPServer |grep -v grep | awk '{print $2}' |xargs kill -9")

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
