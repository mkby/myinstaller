#!/usr/bin/env python

import getpass
import sys
import os
import re

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
                'default':8
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
            confirm = getpass.getpass('Confirm ' + prompt)
            if orig == confirm: answer = confirm
            if not answer and default: 
                answer = default
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

def main():
    format_output('EsgynDB INSTALLATION START')

    u = UserInput()
    
    use_hbase_node = u.getinput('use_hbase_node')
    if  use_hbase_node == 'N':
        node_list = ' '.join(expNumRe(u.getinput('node_list')))
        print ' === NODE LIST ===\n' + node_list
        confirm = u.getinput('confirm')
        if confirm == 'N': u.log_err('\nAborted...')
    
    traf_start = u.getinput('traf_start')
    traf_pwd = u.getinput('traf_pwd')
    traf_rpm = u.getinput('traf_rpm')

    # check format, should not include http
    mgr_url = u.getinput('mgr_url')

    mgr_user = u.getinput('mgr_user')
    mgr_pwd = u.getinput('mgr_pwd')
    hdfs_user = u.getinput('hdfs_user')
    hbase_user = u.getinput('hbase_user')
    hbase_group = u.getinput('hbase_group')
    ldap_security = u.getinput('ldap_security')
    dcs_ha = u.getinput('dcs_ha')
    java_home = u.getinput('java_home')
    dcs_cnt_per_node = u.getinput('dcs_cnt_per_node')

    installer_loc = sys.path[0]

    # detect config file existence

    #ansible-playbook gen_vars.yml -e "installer_loc=$installer_loc" -i $installer_loc/default_hosts
    #ansible-playbook install.yml
    
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print '\nAborted...'
