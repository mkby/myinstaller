#!/usr/bin/env python
# -*- coding: utf8 -*- 

import sys
reload(sys)
sys.setdefaultencoding("utf-8")
import os
import re
import socket
import json
# httplib2 is not installed by default
try:
    import httplib2
except ImportError:
    print 'Python module httplib2 is not found. Install python-httplib2 or ansible first.'
    sys.exit(1)
import base64
import getpass
import time
from optparse import OptionParser
from glob import glob
from collections import defaultdict
from prettytable import PrettyTable

# init global cfgs for user input
cfgs = defaultdict(str)

installer_loc = sys.path[0]
tmp_file = installer_loc + '/.esgyndb_config_temp'
def_cfgfile = installer_loc + '/esgyndb_config'

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
            return defaultdict(str, json.loads(content))
        except ValueError:
            log_err('No json format found in config file')

    def jsave(self, dic):
        with open(self.js_file, 'w') as f:
            f.write(json.dumps(dic, indent=4))

class HttpGet:
    def __init__(self, user, passwd):
        self.user = user
        self.passwd = passwd
        self.h = httplib2.Http(disable_ssl_certificate_validation=True)  
        self.h.add_credentials(self.user, self.passwd)
        self.headers = {}
        self.headers['X-Requested-By'] = 'trafodion'
        self.headers['Content-Type'] = 'application/json'
        self.headers['Authorization'] = 'Basic %s' % (base64.b64encode('%s:%s' % (self.user, self.passwd)))

    def get_content(self, url):
        self.url = url
        try:
            resp, content = self.h.request(self.url, 'GET', headers=self.headers)  
            if resp.status != 200:
                log_err('Error return code %s when getting configs from manager URL' % resp.status)
        except Exception:
            log_err('Failed to access manager URL ' + url)

        try:
            return defaultdict(str, json.loads(content))
        except ValueError:
            log_err('Failed to get data from manager URL, check if password is correct')
            

class HadoopDiscover:
    ''' discover for hadoop related info '''
    def __init__(self, distro, cluster_name, index):
        self.hg = HttpGet(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']))
        self.distro = distro
        self.index = index
        self.cluster_name = cluster_name
        self.cluster_url = '%s/api/v1/clusters/%s' % (cfgs['mgr_url'], cluster_name.replace(' ', '%20'))
        self.rsnodes = []
        self.users = {}

    def get_hadoop_users(self):
        if 'CDH' in self.distro:
            self._get_cdh_users()
        elif 'HDP' in self.distro:
            self._get_hdp_users()
        return self.users

    def _get_hdp_users(self):
        desired_cfg = self.hg.get_content('%s/?fields=Clusters/desired_configs' % (self.cluster_url))
        config_type = {'hbase-env':'hbase_user', 'hadoop-env':'hdfs_user'}
        for k,v in config_type.items():
            desired_tag = desired_cfg['Clusters']['desired_configs'][k]['tag']
            current_cfg = self.hg.get_content('%s/configurations?type=%s&tag=%s' % (self.cluster_url, k, desired_tag))
            self.users[v] = current_cfg['items'][0]['properties'][v]

    def _get_cdh_users(self):
        def _get_username(hadoop_type, index):
            if index == 1:
                service_name = hadoop_type
            else:
                service_name = hadoop_type + str(index)

            cfg = self.hg.get_content('%s/services/%s/config' % (self.cluster_url, service_name))
            if cfg.has_key('items'):
                for item in cfg['items']:
                    if item['name'] == 'process_username': 
                        return item['value']
            return hadoop_type

        hdfs_user = _get_username('hdfs', self.index)
        hbase_user = _get_username('hbase', self.index)

        self.users = {'hbase_user':hbase_user, 'hdfs_user':hdfs_user}

    def get_rsnodes(self):
        if 'CDH' in self.distro:
            if not '5.4.' in self.distro:
                log_err('Incorrect CDH version, currently EsgynDB only supports CDH5.4')
            self._get_rsnodes_cdh()
        elif 'HDP' in self.distro:
            if not '2.3' in self.distro:
                log_err('Incorrect HDP version, currently EsgynDB only supports HDP2.3')
            self._get_rsnodes_hdp()

        self.rsnodes.sort()
        # use short hostname
        try:
            self.rsnodes = [re.match(r'([\w\-]+).*',n).group(1) for n in self.rsnodes]
        except AttributeError:
            pass
        return self.rsnodes

    def _get_rsnodes_cdh(self):
        ''' get list of HBase RegionServer nodes in CDH '''
        cm = self.hg.get_content('%s/api/v6/cm/deployment' % cfgs['mgr_url'])

        hostids = []
        for c in cm['clusters']:
            if c['displayName'] == self.cluster_name:
                for s in c['services']:
                    if s['type'] == 'HBASE':
                        for r in s['roles']:
                            if r['type'] == 'REGIONSERVER': hostids.append(r['hostRef']['hostId'])
        for i in hostids:
            for h in cm['hosts']:
                if i == h['hostId']: self.rsnodes.append(h['hostname'])

    def _get_rsnodes_hdp(self):
        ''' get list of HBase RegionServer nodes in HDP '''
        hdp = self.hg.get_content('%s/services/HBASE/components/HBASE_REGIONSERVER' % self.cluster_url )
        self.rsnodes = [ c['HostRoles']['host_name'] for c in hdp['host_components'] ]
        

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
                'default':'hdfs',
                'isuser': True
            },
            'hbase_user':
            {
                'prompt':'Enter hbase user name',
                'default':'hbase',
                'isuser': True
            },
            'dcs_ha':
            {
                'prompt':'Enable DCS High Avalability',
                'default':'N',
                'isYN':True
            },
            'dcs_ip':
            {
                'prompt':'Enter Floating IP address for DCS HA',
                'isIP':True
            },
            'dcs_interface':
            {
                'prompt':'Enter interface for Floating IP address',
                'default':'eth0',
            },
            'dcs_bknodes':
            {
                'prompt':'Enter DCS Backup Master Nodes for DCS HA (blank separated)',
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
                'default':'389',
                'isdigit':True
            },
            'ldap_identifiers':
            {
                'prompt':'Enter all LDAP unique identifiers (blank separated)',
            },
            'ldap_encrypt':
            {
                'prompt':'Enter LDAP Encryption Level (0: Encryption not used, 1: SSL, 2: TLS)',
                'default':'0',
                'isdigit':True
            },
            'ldap_certpath':
            {
                'prompt':'Enter full path to TLS certificate',
            },
            'ldap_userinfo':
            {
                'prompt':'If Requred search user name/password',
                'default':'N',
                'isYN':True
            },
            'ldap_user':
            {
                'prompt':'Enter Search user name (if required)',
                'default':' ',
            },
            'ldap_pwd':
            {
                'prompt':'Enter Search password (if required)',
                'default':' ',
            },
            'java_home':
            {
                'prompt':'Specify location of Java 1.7.0_65 or higher (JDK) on trafodion nodes',
                'default':'/usr/java/jdk1.7.0_67-cloudera'
            },
            'dcs_cnt_per_node':
            {
                'prompt':'Enter number of DCS client connections per node',
                'default':'8',
                'isdigit':True
            },
            'mgr_url':
            {
                'prompt':'Enter HDP/CDH web manager URL:port, (full URL, if no http/https prefix, default prefix is http://)'
            },
            'mgr_user':
            {
                'prompt':'Enter HDP/CDH web manager user name',
                'default':'admin',
                'isuser': True
            },
            'mgr_pwd':
            {
                'prompt':'Enter HDP/CDH web manager user password',
                'ispasswd':True
            },
            'traf_pwd':
            {
                'prompt':'Enter trafodion user password',
                'ispasswd':True
            },
            'traf_rpm':
            {
                'prompt':'Enter full path to Trafodion RPM file',
                'isexist': True
            },
            'db_admin_user':
            {
                'prompt':'Enter DB Admin user name for esgynDB manager',
                'default':'DB__ADMINUSER',
                'isuser': True
            },
            'db_admin_pwd':
            {
                'prompt':'Enter DB Admin user password for esgynDB manager',
                'default':'traf123',
            },
            'dbmgr_rpm':
            {
                'prompt':'Enter full path to esgynDB manager RPM file',
                'isexist': True
            },
            'node_list':
            {
                'prompt':'Enter list of Nodes separated by space, support simple numeric RE,\n e.g. \'n[01-12] n[21-25]\',\'n0[1-5].com\''
            },
            'cluster_no':
            {
                'prompt':'Select the above cluster number for installing esgynDB',
                'default':'1',
                'isdigit':True
            },
            'use_hbase_node':
            {
                'prompt':'Use same Trafodion nodes as HBase RegionServer nodes',
                'default':'Y',
                'isYN':True
            },
            'confirm_nodelist':
            {
                'prompt':'Confirm expanded node list is correct',
                'default':'Y',
                'isYN':True
            },
            'confirm_all':
            {
                'prompt':'Confirm all configs are correct',
                'default':'N',
                'isYN':True
            },
        }
    
    def _handle_input(self, args, userdef):
        prompt = args['prompt']
        default = userdef
        ispasswd = isYN = isdigit = isexist = isIP = isuser = ''
        if (not default) and args.has_key('default'): default = args['default']
        if args.has_key('ispasswd'): 
            ispasswd = args['ispasswd']
            # no default value for password
            default = ''
        if args.has_key('isYN'): isYN = args['isYN']
        if args.has_key('isdigit'): isdigit = args['isdigit']
        if args.has_key('isexist'): isexist = args['isexist']
        if args.has_key('isIP'): isIP = args['isIP']
        if args.has_key('isuser'): isuser = args['isuser']
    
        if isYN:
            prompt = prompt + ' (Y/N) '
    
        if default:
            prompt = prompt + ' [' + default + ']: '
        else:
            prompt = prompt + ': '
    
        # no default value for password
        if ispasswd:
            orig = getpass.getpass(prompt)
            confirm = getpass.getpass('Confirm ' + prompt)
            if orig == confirm: 
                answer = base64.b64encode(confirm)
            else:
                log_err('Password mismatch')
        else:
            try:
                answer = raw_input(prompt)
            except UnicodeEncodeError:
                log_err('Character Encode error, check user input')
            if not answer and default: answer = default
    
        # check answer value basicly
        answer = answer.rstrip()
        if answer:
            if isYN:
                answer = answer.upper()
                if answer != 'Y' and answer != 'N':
                    log_err('Invalid parameter, should be \'Y|y|N|n\'')
            elif isdigit:
                if not answer.isdigit():
                    log_err('Invalid parameter, should be a number')
            elif isexist:
                if not os.path.exists(answer):
                    log_err('\'%s\' doesn\'t exist' % answer)
            elif isIP:
                try:
                    socket.inet_pton(socket.AF_INET, answer)
                except:
                    log_err('Invalid IP address \'%s\'' % answer)
            elif isuser:
                if re.match(r'\w+', answer).group() != answer:
                    log_err('Invalid user name \'%s\'' % answer)

        else:
            log_err('Empty value')
        
        return answer
    
    def get_input(self, name, userdef=''):
        if self.in_data.has_key(name):
            # save configs to global dict
            cfgs[name] = self._handle_input(self.in_data[name], userdef)
            return cfgs[name]
        else: 
            # should not go to here, just in case
            log_err('Invalid prompt')

    def notify_user(self):
        ''' show the final configs to user '''
        print '\n  **** Final Configs ****'
        pt = PrettyTable(['config type', 'value'])
        pt.align['config type'] = pt.align['value'] = 'l'
        for k,v in sorted(cfgs.items()):
            if self.in_data.has_key(k):
                if self.in_data[k].has_key('ispasswd') or 'confirm' in k: continue
                pt.add_row([k, v])
        print pt
        confirm = self.get_input('confirm_all')
        if confirm == 'N': 
            if os.path.exists(def_cfgfile): os.remove(def_cfgfile)
            log_err('User quit')


def expNumRe(text):
    """
    expand numeric regular expression to list
    e.g. 'n[01-03] n1[0-1]': ['n01','n02','n03','n10','n11']
    e.g. 'n[09-11].com': ['n09.com','n10.com','n11.com']
    """
    explist = []
    for regex in text.split():
        r = re.match(r'(.*)\[(\d+)-(\d+)\](.*)',regex)
        if r:
            h = r.group(1)
            d1 = r.group(2)
            d2 = r.group(3)
            t = r.group(4)

            convert = lambda d: str(('%0' + str(min(len(d1), len(d2))) + 'd') % d)
            if d1 > d2: d1,d2 = d2,d1
            explist.extend([h + convert(c) + t for c in range(int(d1), int(d2)+1)])

        else:
            # keep original value if not matched
            explist.append(regex)

    return explist


def log_err(errtext):

    print '***ERROR: ' + errtext
    global tmp_file
    # save tmp config files
    tp = ParseJson(tmp_file)
    tp.jsave(cfgs)

    sys.exit(1)

def format_output(text):
    num = len(text) + 4
    print '*' * num
    print '  ' + text
    print '*' * num

def check_node_conn():
    for node in cfgs['node_list'].split():
        rc = os.system('ping -c 1 %s >/dev/null 2>&1' % node)
        if rc: log_err('Cannot ping %s, please check network connection or /etc/hosts configured correctly ' % node)

def check_mgr_url():
    hg = HttpGet(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']))
    validate_url_v1 = '%s/api/v1/clusters' % cfgs['mgr_url']
    validate_url_v6 = '%s/api/v6/clusters' % cfgs['mgr_url']
    content = hg.get_content(validate_url_v1)

    if content['items'][0].has_key('name'):
        # use v6 rest api for CDH to get fullversion
        content = hg.get_content(validate_url_v6)

    cluster_cfgs = []
    # loop all managed clusters
    for clusters in content['items']:
        try:
            # HDP
            distro = clusters['Clusters']['version']
            cluster_name = clusters['Clusters']['cluster_name']
        except KeyError:
            # CDH
            try:
                distro = 'CDH' + clusters['fullVersion']
                cluster_name = clusters['displayName']
            except KeyError:
                distro = cluster_name = ''

        cluster_cfgs.append([distro, cluster_name])

    return cluster_cfgs

    
def user_input(no_dbmgr=False):
    """ get user's input and check input value """
    global cfgs, tmp_file, installer_loc
    # load from temp storaged config file
    if os.path.exists(tmp_file):
        tp = ParseJson(tmp_file)
        cfgs = tp.jload()

    u = UserInput()
    g = lambda n: u.get_input(n, cfgs[n])

    g('java_home')

    def _check_rpm(input_name, rpm_name):
        # find rpm in installer folder, if more than one rpm found, use the first one
        rpm_loc = glob('%s/%s*.rpm' % (installer_loc, rpm_name))
        if rpm_loc:
            u.get_input(input_name, rpm_loc[0])
        else:
            g(input_name)

        # get rpm basename from rpm filename
        try:
            rpm_basename, rpm_version = re.search(r'(%s.*)-(\d\.\d\.\d)-.*' % rpm_name, cfgs[input_name]).groups()
            return rpm_basename, rpm_version
        except:
            log_err('Invalid %s RPM name, be careful don\'t rename original RPM name' % rpm_name)

    cfgs['traf_basename'], cfgs['traf_version'] = _check_rpm('traf_rpm', 'trafodion')

    if not no_dbmgr:
        cfgs['dbmgr_basename'], cfgs['dbmgr_version'] = _check_rpm('dbmgr_rpm', 'esgynDB-manager')
        g('db_admin_user')
        g('db_admin_pwd')

    url = g('mgr_url')
    if not ('http:' in url or 'https:' in url): 
        cfgs['mgr_url'] = 'http://' + cfgs['mgr_url']

    g('mgr_user')
    g('mgr_pwd')

    cluster_cfgs = check_mgr_url()
    c_index = 0
    # support multiple clusters, test on CDH only
    if len(cluster_cfgs) > 1:
        for index, config in enumerate(cluster_cfgs):
            print str(index + 1) + '. ' + config[1]
        c_index = int(g('cluster_no')) - 1
        if c_index < 0 or c_index >= len(cluster_cfgs):
            log_err('Incorrect number')

    distro, cluster_name = cluster_cfgs[c_index]
    discover = HadoopDiscover(distro, cluster_name, c_index+1)
    rsnodes = discover.get_rsnodes()
    hadoop_users = discover.get_hadoop_users()

    # cdh uses different service names in multiple clusters
    if c_index == 0:
        cfgs['hbase_service_name'] = 'hbase'
        cfgs['hdfs_service_name'] = 'hdfs'
        cfgs['zookeeper_service_name'] = 'zookeeper'
    else:
        cfgs['hbase_service_name'] = 'hbase' + str(c_index+1)
        cfgs['hdfs_service_name'] = 'hdfs' + str(c_index+1)
        cfgs['zookeeper_service_name'] = 'zookeeper' + str(c_index+1)
    
    cfgs['distro'] = distro
    cfgs['cluster_name'] = cluster_name.replace(' ', '%20')
    cfgs['hdfs_user'] = hadoop_users['hdfs_user']
    cfgs['hbase_user'] = hadoop_users['hbase_user']

    # manually set node list
    if  g('use_hbase_node') == 'N':
        cnt = 0
        # give user another try if input is wrong
        while cnt <= 2:
            cnt += 1
            if cnt == 2: print ' === Please try to input node list again ==='
            node_lists = expNumRe(g('node_list'))
            if set(node_lists).difference(set(rsnodes)):
                log_err('Incorrect node list, should be part of RegionServer nodes')
            node_list = ' '.join(node_lists)
            print ' === NODE LIST ===\n' + node_list
            confirm = u.get_input('confirm_nodelist')
            if confirm == 'N': 
                if cnt <= 1:
                    continue
                else:
                    log_err('Incorrect node list, aborted...')
            else:
                cfgs['node_list'] = ' ' + node_list
                break
    else:
        cfgs['node_list'] = ' ' + ' '.join(rsnodes)

    check_node_conn()

    # set other config to cfgs
    cfgs['my_nodes'] = cfgs['node_list'].replace(' ', ' -w ')
    cfgs['first_node'] = cfgs['node_list'].split()[0]
    cfgs['first_rsnode'] = rsnodes[0] # first regionserver node
    cfgs['hbase_xml_file'] = '/etc/hbase/conf/hbase-site.xml'
    cfgs['config_created_date'] = time.strftime('%Y/%m/%d %H:%M %Z')
    
    g('traf_pwd')
    g('traf_start')
    g('dcs_cnt_per_node')

    # ldap security
    if g('ldap_security') == 'Y':
        g('ldap_hosts')
        g('ldap_port')
        g('ldap_identifiers')
        ldap_encrypt = g('ldap_encrypt')
        if  ldap_encrypt == '1' or ldap_encrypt == '2':
            g('ldap_certpath')
        elif ldap_encrypt == '0':
            cfgs['ldap_certpath'] = ''
        else:
            log_err('Invalid ldap encryption level')

        if g('ldap_userinfo') == 'Y':
            g('ldap_user')
            g('ldap_pwd')
        else:
            cfgs['ldap_user'] = ''
            cfgs['ldap_pwd'] = ''

    # DCS HA
    if g('dcs_ha') == 'Y':
        g('dcs_ip')
        g('dcs_interface')
        g('dcs_bknodes')
        # check dcs backup nodes should exist in node list
        if sorted(list(set((cfgs['dcs_bknodes'] + ' ' + cfgs['node_list']).split()))) != sorted(cfgs['node_list'].split()):
            log_err('Invalid DCS backup nodes, please pick up from node list')

    u.notify_user()

def time_elapse(start, end):
    """ set time format from seconds to h:m:s """
    seconds = end - start
    hours = seconds / 3600
    seconds = seconds % 3600
    minutes = seconds / 60
    seconds = seconds % 60
    print "Installation time: %d hour(s) %d minute(s) %d second(s)" % (hours, minutes, seconds)

def pre_check():
    """ check required packages should be installed """

    # check ansible is installed
    rc = os.system('which ansible-playbook >/dev/null 2>&1')
    if rc: log_err('\'ansible\' is not found, please install it first')


def main():
    """ esgyndb_installer main loop """

    pre_check()

    ################################
    # script options and usage info
    ################################
    usage = 'usage: %prog [options]\n'
    usage += '  EsgynDB install wrapper script. It will create ansible\n\
  config, variables, hosts file and call ansible to install EsgynDB.'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config-file", dest="cfgfile", metavar="FILE",
                help="Json format file. If provided, all install prompts \
                      will be taken from this file and not prompted for.")
    parser.add_option("-u", "--remote-user", dest="user", metavar="USER",
                help="Specify ssh login user for remote server, \
                      if not provided, use current login user as default.")
    parser.add_option("-b", "--become-method", dest="method", metavar="METHOD",
                help="Specify become root method for ansible [ sudo | su | pbrun | pfexec | runas | doas ].")
    parser.add_option("-f", "--fork", dest="fork", metavar="FORK",
                help="Specify number of parallel processes to use for ansible(default=5)" )
    parser.add_option("-d", "--disable-pass", action="store_true", dest="dispass", default=False,
                help="Do not prompt SSH login password for remote hosts. \
                      If set, be sure passwordless ssh is configured.")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                help="Verbose mode for ansible.")
    parser.add_option("--dryrun", action="store_true", dest="dryrun", default=False,
                help="Dry run mode, it will only generate the config file.") 
    parser.add_option("--no-dbmgr", action="store_true", dest="nodbmgr", default=False,
                help="Do not install esgynDB manager.")
    parser.add_option("--dbmgr-only", action="store_true", dest="dbmgr", default=False,
                help="Install esgynDB manager only, be sure esgynDB is previously installed.")
    parser.add_option("--dbmgr-rpm", dest="dbmgrrpm", metavar="RPMFILE",
                help="Specify esgynDB manager RPM location.")

    (options, args) = parser.parse_args()

    # handle parser option
    if options.dryrun and options.cfgfile:
        log_err('Wrong parameter, cannot specify both --dryrun and --config-file')

    if options.dbmgr and options.nodbmgr:
        log_err('Wrong parameter, cannot specify both --dbmgr-only and --no-dbmgr')

    if bool(options.dbmgr) != bool(options.dbmgrrpm):
        log_err('Wrong parameter, must specify both --dbmgr-only and --dbmgr-rpm')

    if options.method:
        if options.method not in ['sudo','su','pbrun','pfexec','runas','doas']:
            log_err('Wrong method, valid methods: [ sudo | su | pbrun | pfexec | runas | doas ].')
        
    # set no_dbmgr flag
    if options.nodbmgr:
        no_dbmgr = True
    else:
        no_dbmgr = False

    #######################################
    # get user input and gen variable file
    #######################################
    format_output('EsgynDB Installation Start')
    global cfgs, installer_loc
    if options.cfgfile:
        if not os.path.exists(options.cfgfile): 
            log_err('Cannot find config file \'%s\'' % options.cfgfile)
        config_file = options.cfgfile
    else:
        config_file = def_cfgfile

    p = ParseJson(config_file)

    # must install Trafodion first if using dbmgr only mode
    if options.dbmgr and not os.path.exists(config_file):
        log_err('Must specify the config file, which means you have previously installed Trafodion')

    # not specified config file and default config file doesn't exist either
    if options.dryrun or (not os.path.exists(config_file)): 
        if options.dryrun: format_output('DryRun Start')
        user_input(no_dbmgr)

        # save config file as json format
        print '\n** Generating json file to save configs ... \n'
        p.jsave(cfgs)

    # config file exists
    else:
        print '\n** Loading configs from json file ... \n'
        cfgs = p.jload()

        # check some basic info
        check_mgr_url()
        check_node_conn()

        u = UserInput()
        u.notify_user()

    if not options.dryrun:
        #####################################
        # generate ansible config&hosts file
        #####################################
        print '\n** Generating ansible config and hosts file ... \n'
        node_array = cfgs['node_list'].split()
        first_node = node_array[0]
        first_rsnode = cfgs['first_rsnode']
        node_array = [ node + '\n' for node in node_array ]

        ansible_cfg = os.getenv('HOME') + '/.ansible.cfg'
        hosts_file = installer_loc + '/hosts'
        ts = time.strftime('%y%m%d_%H%M')
        log_path = '%s/esgyndb_install_%s.log' %(installer_loc, ts)

        try:
            with open(ansible_cfg, 'w') as f:
                f.write('[defaults]\n')
                f.write('log_path = %s\n' % log_path)
                f.write('inventory =' + hosts_file + '\n')
                f.write('host_key_checking = False\n')
                #f.write('display_skipped_hosts = False\n')
        except IOError:
            log_err('Failed to open ansible.cfg file')

        try:
            with open(hosts_file, 'w') as f:
                f.write('[trafnodes]\n')
                f.writelines(node_array)
                f.write('\n[firstnode]\n')
                f.write(first_node)
                f.write('\n\n[firstrsnode]\n')
                f.write(first_rsnode)
        except IOError:
            log_err('Failed to open hosts file')

        #############################
        # calling ansible to install
        #############################
        format_output('Ansible Installation start')

        start_time = time.time()

        cmd = 'ansible-playbook %s/install.yml -i %s/hosts -e \'%s\'' % \
            (installer_loc, installer_loc, json.dumps(cfgs))

        # only install esgynDB manager
        if options.dbmgr: 
            cmd += ' --tags=dbmgr'
 
            # will overwrite previous dbmgr_rpm value
            if os.path.exists(options.dbmgrrpm):
                cmd += ' --extra-vars "dbmgr_rpm=%s"' % options.dbmgrrpm
            else:
                log_err('Failed to find esgynDB manager rpm file')

            # force set to false
            no_dbmgr = False

        if no_dbmgr: cmd += ' --skip-tags=dbmgr'
        if not options.dispass: cmd += ' -k'
        if options.verbose: cmd += ' -v'
        if options.user: cmd += ' -u %s' % options.user
        if options.fork: cmd += ' -f %s' % options.fork
        if options.method: cmd += ' --become-method=%s' % options.method

        rc = os.system(cmd)
        if rc: log_err('Failed to install EsgynDB by ansible, please check log file %s for details.\n\
    Double check config file \'%s\' to make sure nothing is wrong.' % (log_path, config_file))

        format_output('EsgynDB Installation Complete')

        end_time = time.time()
        time_elapse(start_time, end_time)

        ################
        # clean up work
        ################
        # rename default config file when successfully installed
        # so next time user can input new variables for a new install
        # or specify the backup config file to install again
        try:
            # only rename default config file
            if config_file == def_cfgfile and os.path.exists(config_file):
                os.rename(config_file, config_file + '.bak' + ts)
        except OSError:
            log_err('Cannot rename config file')
    else:
        format_output('DryRun Complete')

    # remove temp config file
    if os.path.exists(tmp_file): os.remove(tmp_file)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        tp = ParseJson(tmp_file)
        tp.jsave(cfgs)
        print '\nAborted...'
