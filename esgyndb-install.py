#!/usr/bin/env python

import sys
import os
import re
import json
import getpass
from datetime import date
from subprocess import Popen, PIPE

class UserInput:
    def __init__(self):
        self.in_data = {
            'traf_start':
            {
                'prompt':'Start Trafodion instance after installation',
                'default':'Y',
                'isYN':True
            },
            'hdfs_user':
            {
                'prompt':'Enter hdfs user name',
                'default':'hdfs'
            },
            'hbase_user':
            {
                'prompt':'Enter hbase user name',
                'default':'hbase'
            },
            'hbase_group':
            {
                'prompt':'Enter hbase group name',
                'default':'hbase'
            },
            'dcs_ha':
            {
                'prompt':'Enable DCS HA',
                'default':'N',
                'isYN':True
            },
            'ldap_security':
            {
                'prompt':'Enable LDAP security',
                'default':'N',
                'isYN':True
            },
            'ldap_hosts':
            {
                'prompt':'Enter list of LDAP Hostnames (blank separated)',
            },
            'ldap_port':
            {
                'prompt':'Enter LDAP Port number (Example: 389 for no encryption or TLS, 636 for SSL)',
                'default':389,
            },
            'java_home':
            {
                'prompt':'Specify location of Java 1.7.0_65 or higher (JDK)',
                'default':'/usr/java/jdk1.7.0_67-cloudera'
            },
            'dcs_cnt_per_node':
            {
                'prompt':'Enter number of DCS client connections per node',
                'default':'8'
            },
            'mgr_url':
            {
                'prompt':'Enter HDP/CDH web manager URL:port, (no http:// needed)'
            },
            'mgr_user':
            {
                'prompt':'Enter HDP/CDH web manager user name',
                'default':'admin'
            },
            'mgr_pwd':
            {
                'prompt':'Enter HDP/CDH web manager user password',
                'default':'admin',
                'ispasswd':True
            },
            'traf_pwd':
            {
                'prompt':'Enter trafodion password',
                'default':'traf123',
                'ispasswd':True
            },
            'traf_rpm':
            {
                'prompt':'Enter full path to Trafodion RPM file'
            },
            'node_list':
            {
                'prompt':'Enter list of Nodes separated by space, support simple numeric RE, e.g. n0[1-5].com'
            },
            'use_hbase_node':
            {
                'prompt':'Use same Trafodion nodes as HBase RegionServer nodes',
                'default':'Y',
                'isYN':True
            },
            'confirm':
            {
                'prompt':'Confirm expanded node list is correct',
                'default':'Y',
                'isYN':True
            },
        }
    
    def log_err(self, errtext):
        print '***ERROR: ' + errtext
        sys.exit(1)
    
    def _handle_input(self, args):
        prompt = args['prompt']
        default = ''
        ispasswd = ''
        isYN = ''
        if args.has_key('default'): default = args['default']
        if args.has_key('ispasswd'): ispasswd = args['ispasswd']
        if args.has_key('isYN'): isYN = args['isYN']
    
        if isYN:
            prompt = prompt + ' (Y/N) '
    
        if default:
            prompt = prompt + ' [' + default + ']: '
        else:
            prompt = prompt + ': '
    
        if ispasswd:
            orig = getpass.getpass(prompt)
            if (not orig) and default: 
                answer = default
            else:
                confirm = getpass.getpass('Confirm ' + prompt)
                if orig == confirm: 
                    answer = confirm
                else:
                    self.log_err('Password mismatch')
        else:
            answer = raw_input(prompt)
            if not answer and default: answer = default
    
        # check answer value basicly
        if isYN:
            answer = answer.upper()
            if answer != 'Y' and answer != 'N':
                self.log_err('Invalid parameter, should be \'Y|y|N|n\'')
        else:
            if not answer:
                self.log_err('Empty value')
        
        return answer
    
    def getinput(self, name):
        if self.in_data.has_key(name):
            return self._handle_input(self.in_data[name])
        else: 
            self.log_err('Invalid prompt')


def expNumRe(text):
    """
    expand numeric regular expression to list
    e.g. 'n0[1-3] n1[0-1]': [n01,n02,n03,n10,n11]
    """
    explist = []
    for regex in text.split():
        r = re.match(r'(.*)\[(\d)-(\d)\](.*)',regex)
        if r:
            h = r.group(1)
            d1 = int(r.group(2))
            d2 = int(r.group(3))
            t = r.group(4)
            if d1 > d2: d1,d2 = d2,d1
            explist.extend([h + str(c) + t for c in range(d1, d2+1)])
        else:
            # keep original value if not matched
            explist.append(regex)

    return explist

def format_output(text):
    num = len(text) + 4
    print '*' * num
    print '  ' + text
    print '*' * num

def user_input():
    """ get user's input """

    u = UserInput()
    
    traf_rpm = u.getinput('traf_rpm')

    mgr_url = u.getinput('mgr_url')
    if ('http:' or 'https:') in mgr_url: u.log_err('Do not include http or https')
    mgr_user = u.getinput('mgr_user')
    mgr_pwd = u.getinput('mgr_pwd')

    java_home = u.getinput('java_home')

    use_hbase_node = u.getinput('use_hbase_node')
    node_list = ''
    if  use_hbase_node == 'N':
        node_list = ' '.join(expNumRe(u.getinput('node_list')))
        print ' === NODE LIST ===\n' + node_list
        confirm = u.getinput('confirm')
        if confirm == 'N': u.log_err('\nAborted...')
    
    traf_start = u.getinput('traf_start')
    traf_pwd = u.getinput('traf_pwd')

    hdfs_user = u.getinput('hdfs_user')
    hbase_user = u.getinput('hbase_user')
    hbase_group = u.getinput('hbase_group')
    dcs_cnt_per_node = u.getinput('dcs_cnt_per_node')
    dcs_ha = u.getinput('dcs_ha')
    ldap_security = u.getinput('ldap_security')

    cfgs = {
    'traf_rpm':          traf_rpm,
    'mgr_url':           mgr_url,
    'mgr_user':          mgr_user,
    'mgr_pwd':           mgr_pwd,
    'java_home':         java_home,
    'use_hbase_node':    use_hbase_node,
    'node_list':         node_list,
    'traf_start':        traf_start,
    'traf_pwd':          traf_pwd,
    'hdfs_user':         hdfs_user,
    'hbase_user':        hbase_user,
    'hbase_group':       hbase_group,
    'dcs_cnt_per_node':  dcs_cnt_per_node,
    'dcs_ha':            dcs_ha,
    'ldap_security':     ldap_security,
    }
    return json.dumps(cfgs)


def main():
    """ esgyndb_installer main loop """

    format_output('EsgynDB INSTALLATION START')

    installer_loc = sys.path[0]
    config_file = installer_loc + '/group_vars/all.yml'

    # TODO
    # overwrite config_file with --config-file option
    # config_file = xxx

    if not os.path.exists(config_file): 
        cfgs = user_input()
        # generate config file first
        cmd = 'ansible-playbook %s/install.yml -e \'%s\' -e installer_loc=%s -i %s/default_hosts --tags=var_tag' % \
            (installer_loc, cfgs, installer_loc, installer_loc)
        rc = os.system(cmd)
        if rc: sys.exit(rc)

        # start installing using generated config file 'group_vars/all.yml'
        cmd = 'ansible-playbook %s/install.yml -e installer_loc=%s -i %s/default_hosts --tags=install_tag' % \
            (installer_loc, installer_loc, installer_loc)
        rc = os.system(cmd)
        if rc: sys.exit(rc)
    else:
        # start installing using specified config file
        cmd = 'ansible-playbook %s/install.yml -e @%s -e installer_loc=%s -i %s/default_hosts --tags=install_tag' % \
            (installer_loc, config_file, installer_loc, installer_loc)
        rc = os.system(cmd)
        if rc: sys.exit(rc)

    format_output('EsgynDB INSTALLATION COMPLETE')

    # rename config file when successfully installed
    ts = date.today().strftime('%Y%m%d_%H%M')
    try:
        os.rename(config_file, config_file + '.bak' + ts)
    except OSError:
        pass
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print '\nAborted...'
