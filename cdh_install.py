#!/usr/bin/env python

import os, sys
import socket
import time
import json
from deploy_cdh import Deploy
from optparse import OptionParser
from common import *

def config_cdh():
    # config cdh
    deploy = Deploy()
    deploy.setup_cms()
    deploy.setup_parcel()
    deploy.start_cms()
    deploy.setup_cdh()
    deploy.start_cdh()

def main():
    usage = 'usage: %prog [options]\n'
    usage += '  Cloudera install script. It will install and configure Cloudera rpms \n\
  and deploy Hadoop services via cm api.'
    parser = OptionParser(usage=usage)
    parser.add_option("-u", "--remote-user", dest="user", metavar="USER",
                help="Specify ssh login user for remote server, \
                      if not provided, use current login user as default.")
    parser.add_option("-p", "--package-only", action="store_true", dest="pkgonly", default=False,
                help="Install Cloudera package only but not deploy it. Please use CM web page to deploy it manually.")
    parser.add_option("--version", action="store_true", dest="version", default=False,
                help="Show installer version.")

    (options, args) = parser.parse_args()

    if options.version: version()

    repo_port = '8900'
    # get configs
    cfg = ParseConfig()
    cdhnodes = cfg.get_hosts()
    repo_dir = cfg.get_repodir()
    parcel_dir = cfg.get_parceldir()

    if not repo_dir: err('Failed to get repository dir')
    if not parcel_dir: err('Failed to get parcel dir')

    cdhmaster = cdhnodes[0]

    with open('/etc/hosts', 'r') as f:
        lines = f.readlines()

    try:
        hosts =[ [l for l in lines if h in l][0] for h in cdhnodes ] 
    except IndexError:
        err('hosts mismatch, please check the hosts in config.ini are set in /etc/hosts.')
    hosts_json = json.dumps({'hosts':hosts})

    hostname = socket.gethostname()
    repo_ip = socket.gethostbyname(hostname)

    # set ansible configs
    content = '\n[cdhmaster]\n' + cdhmaster + '\n[cdhnodes]\n'
    for n in cdhnodes: content += n + '\n'
    log_path = set_ansible_cfgs(content)

    http_start(repo_dir, repo_port)

    cmd = 'ansible-playbook cm_install.yml -k --extra-vars='
    cmd += '"repo_ip=%s repo_port=%s parcel_dir=%s"' % (repo_ip, repo_port, parcel_dir)
    cmd += ' --extra-vars \'%s\'' % hosts_json
    if options.user: cmd += ' -u %s' % options.user

    info('Starting ansible playbook to deploy cloudera rpms')
    rc = os.system(cmd)

    http_stop()

    if rc:
        err('Failed to deploy cloudera, please check log file %s for details' % log_path)
    else:
        info('Cloudera RPMs installed successfully!')

    if not options.pkgonly: config_cdh()

if __name__ == "__main__":
    main()
