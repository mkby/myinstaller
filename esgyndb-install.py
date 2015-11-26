#!/usr/bin/env python

import sys
import os
import re
import json
import httplib2
import getpass
import time
from subprocess import Popen, PIPE

class ParseJson:
    """ 
    jload: load json file to a dict
    jsave: save dict to json file with pretty format
    """
    def __init__(self, js_file):
        self.js_file = js_file

    def jload(self):
        with open(self.js_file, 'r') as f:
            tmparray = f.readlines()
        content = ''
        for t in tmparray:
            content += t

        try:
            return json.loads(content)
        except ValueError:
            log_err('No json format found in config file')

    def jsave(self, dic):
        with open(self.js_file, 'w') as f:
            f.write(json.dumps(dic, indent=4))

class HttpGet:
    def __init__(self, user, passwd):
        self.user = user
        self.passwd = passwd
        self.h = httplib2.Http(".cache")  
        self.h.add_credentials(self.user, self.passwd)

    def get_content(self, url):
        self.url = url
        try:
            resp, content = self.h.request(self.url, "GET")  
        except:
            log_err('Failed to access manager URL ' + url)

        try:
            return json.loads(content)
        except ValueError:
            log_err('No json format found in http content')
            


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
                    log_err('Password mismatch')
        else:
            answer = raw_input(prompt)
            if not answer and default: answer = default
    
        # check answer value basicly
        if isYN:
            answer = answer.upper()
            if answer != 'Y' and answer != 'N':
                log_err('Invalid parameter, should be \'Y|y|N|n\'')
        else:
            if not answer:
                log_err('Empty value')
        
        return answer
    
    def getinput(self, name):
        if self.in_data.has_key(name):
            return self._handle_input(self.in_data[name])
        else: 
            log_err('Invalid prompt')


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


def log_err(errtext):
    print '***ERROR: ' + errtext
    sys.exit(1)

def format_output(text):
    num = len(text) + 4
    print '*' * num
    print '  ' + text
    print '*' * num

def user_input():
    """ get user's input """

    u = UserInput()
    
    # TODO check rpm file existence
    traf_rpm = u.getinput('traf_rpm')

    mgr_url = u.getinput('mgr_url')
    if ('http:' or 'https:') in mgr_url: log_err('Do not include http or https')
    mgr_user = u.getinput('mgr_user')
    mgr_pwd = u.getinput('mgr_pwd')

    java_home = u.getinput('java_home')

    use_hbase_node = u.getinput('use_hbase_node')
    node_list = ''
    if  use_hbase_node == 'N':
        node_list = ' '.join(expNumRe(u.getinput('node_list')))
        print ' === NODE LIST ===\n' + node_list
        confirm = u.getinput('confirm')
        if confirm == 'N': log_err('\nAborted...')
    
    traf_start = u.getinput('traf_start')
    traf_pwd = u.getinput('traf_pwd')

    hdfs_user = u.getinput('hdfs_user')
    hbase_user = u.getinput('hbase_user')
    hbase_group = u.getinput('hbase_group')
    dcs_cnt_per_node = u.getinput('dcs_cnt_per_node')
    dcs_ha = u.getinput('dcs_ha')
    ldap_security = u.getinput('ldap_security')

    user_cfgs = {
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
    return user_cfgs

def pre_check():
    """ check required packages should be installed """
    # TODO  ansible should be installed
    pass

def main():
    """ esgyndb_installer main loop """

    format_output('EsgynDB INSTALLATION START')

    pre_check()

    cfgs = {}
    # TODO
    # add func to save user input to a tmp file and reload it when re-run
    # suport ldap security / dcs ha
    # overwrite config_file with --config-file option
    # config_file = xxx

    installer_loc = sys.path[0]
    config_file = installer_loc + '/esgyndb_config.json'
    p = ParseJson(config_file)
    if not os.path.exists(config_file): 
        cfgs = user_input()
        
        hg = HttpGet(cfgs['mgr_user'], cfgs['mgr_pwd'])

        clusters = hg.get_content('http://%s/api/v1/clusters' % cfgs['mgr_url'])
        # get cluster name, assume only one cluster managed
        cluster_name = clusters['items'][0]['name']

        # get list of HBase RegionServer node if node_list is not specified
        if not cfgs['node_list']:
            cm = hg.get_content('http://%s/api/v6/cm/deployment' % cfgs['mgr_url'])
            hostids = []
            hostnames = []
            for c in cm['clusters']:
                if c['displayName'] == cluster_name:
                    for s in c['services']:
                        if s['type'] == 'HBASE':
                            for r in s['roles']:
                                if r['type'] == 'REGIONSERVER': hostids.append(r['hostRef']['hostId'])

            for i in hostids:
                for h in cm['hosts']:
                    if i == h['hostId']: hostnames.append(h['hostname'])

            hostnames.sort()
            node_list = ' '.join(hostnames)
            node_list = ' ' + node_list
            cfgs['node_list'] = node_list

        # set other config to cfgs
        cfgs['my_nodes'] = node_list.replace(' ', ' -w ')
        cfgs['first_node'] = node_list.split()[0]
        cfgs['cluster_name'] = cluster_name.replace(' ','%20')

        cfgs['hbase_xml_file'] = '/etc/hbase/conf/hbase-site.xml'
        cfgs['rpm_basename'] = 'trafodion'

        # save config file as json format
        print '\n Generating json file to save variables ... \n'
        p.jsave(cfgs)

    # config file exists
    else:
        print '\n Loading variable json file ... \n'
        cfgs = p.jload()


    ##############################
    # generate ansible config&hosts file
    ##############################
    print '\n Generating ansible config and hosts file ... \n'
    node_array = cfgs['node_list'].split()
    first_node = node_array[0]
    node_array = [ node + '\n' for node in node_array ]

    ansible_cfg = os.getenv('HOME') + '/.ansible.cfg'
    hosts_file = installer_loc + '/hosts'
    ts = time.strftime('%y%m%d_%H%M')

    try:
        with open(ansible_cfg, 'w') as f:
            f.write('[defaults]\n')
            f.write('log_path = $HOME/esgyndb_install_' + ts + '.log\n')
            f.write('inventory =' + hosts_file + '\n')
            f.write('host_key_checking = False\n')
            f.write('display_skipped_hosts = False\n')
    except IOError:
        log_err('Failed to open ansible.cfg file')

    try:
        with open(hosts_file, 'w') as f:
            f.write('[trafnodes]\n')
            f.writelines(node_array)
            f.write('\n[firstnode]\n')
            f.write(first_node)
    except IOError:
        log_err('Failed to open hosts file')

    #############################
    # calling ansible to install
    #############################
    format_output('Ansible Installation start, input remote hosts SSH passwd if prompt')
    cmd = 'ansible-playbook %s/install.yml -i %s/hosts -e \'%s\' -k' % \
        (installer_loc, installer_loc, json.dumps(cfgs))

    # get user from parameters
    # remote_user = xxx
    remote_user = ''
    if remote_user: cmd += ' -u %s' % remote_user

    rc = os.system(cmd)
    if rc: sys.exit(rc)

    format_output('EsgynDB INSTALLATION COMPLETE')

#    # rename config file when successfully installed
#    ts = time.strftime('%y%m%d_%H%M')
#    try:
#        os.rename(config_file, config_file + '.bak' + ts)
#    except OSError:
#        pass
    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print '\nAborted...'
