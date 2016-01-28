#!/usr/bin/env python

import sys
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

# init global cfgs for user input
cfgs = defaultdict(str)

tmp_file = '/tmp/esgyndb_config_temp'
installer_loc = sys.path[0]

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

    def get_content(self, url, test=False):
        self.url = url
        try:
            resp, content = self.h.request(self.url, "GET")  
        except:
            log_err('Failed to access manager URL ' + url)

        if not test:
            try:
                return defaultdict(str, json.loads(content))
            except ValueError:
                #log_err('No json format found in http content')
                log_err('Failed to get data from manager URL, check if password is correct')
            

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
            'hbase_group':
            {
                'prompt':'Enter hbase group name',
                'default':'hbase'
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
                'prompt':'Enter interface for Floating IP address (example: eth0)',
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
                'prompt':'Enter trafodion password',
                'ispasswd':True
            },
            'traf_rpm':
            {
                'prompt':'Enter full path to Trafodion RPM file',
                'isexist': True
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
            answer = base64.b64encode(getpass.getpass(prompt))
        else:
            answer = raw_input(prompt)
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
    
    def getinput(self, name, userdef):
        if self.in_data.has_key(name):
            # save configs to global dict
            cfgs[name] = self._handle_input(self.in_data[name], userdef)
            return cfgs[name]
        else: 
            # should not go to here, just in case
            log_err('Invalid prompt')


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
    # validate url, will not validate user/passwd here
    hg = HttpGet(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']))
    hg.get_content(cfgs['mgr_url'], test=True)

def user_input(no_dbmgr=False):
    """ get user's input and check input value """
    global cfgs, tmp_file, installer_loc
    # load from temp storaged config file
    if os.path.exists(tmp_file):
        tp = ParseJson(tmp_file)
        cfgs = tp.jload()

    u = UserInput()
    g = lambda n: u.getinput(n, cfgs[n])

    g('java_home')
    # find trafodion rpm in installer folder, if more than one
    # rpm found, use the first one
    def_rpm = glob('%s/trafodion*.rpm' % installer_loc)
    if def_rpm:
        u.getinput('traf_rpm', def_rpm[0])
    else:
        g('traf_rpm')

    # get rpm basename from rpm filename
    try:
        cfgs['rpm_basename'] = re.search(r'\/(\w+)-\d\.\d\.\d-.*', cfgs['traf_rpm']).group(1)
    except:
        log_err('Invalid RPM name, be careful don\'t rename RPM name')

    if not no_dbmgr:
        # find esgyndb manager rpm in installer folder, if more than one
        # rpm found, use the first one
        dbmgr_rpm = glob('%s/esgynDB-manager*.rpm' % installer_loc)
        if dbmgr_rpm:
            u.getinput('dbmgr_rpm', dbmgr_rpm[0])
        else:
            g('dbmgr_rpm')

    url = g('mgr_url')
    if not ('http:' in url or 'https:' in url): 
        cfgs['mgr_url'] = 'http://' + cfgs['mgr_url']

    g('mgr_user')
    g('mgr_pwd')

    check_mgr_url()

    if  g('use_hbase_node') == 'N':
        cnt = 0
        # give user another try if input is wrong
        while cnt <= 2:
            cnt += 1
            if cnt == 2: print ' === Please try to input node list again ==='
            node_list = ' '.join(expNumRe(g('node_list')))
            print ' === NODE LIST ===\n' + node_list
            confirm = u.getinput('confirm', '')
            if confirm == 'N': 
                if cnt <= 1:
                    continue
                else:
                    log_err('Incorrect node list, aborted...')
            else:
                cfgs['node_list'] = ' ' + node_list
                break

    check_node_conn()
    
    g('traf_pwd')
    g('traf_start')
    g('hdfs_user')
    g('hbase_user')
    g('hbase_group')
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

# set time format from seconds to h:m:s
def time_elapse(start, end):
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
                help="Specify become method for ansible.")
    parser.add_option("-f", "--fork", dest="fork", metavar="FORK",
                help="Specify number of parallel processes to use for ansible(default=5)" )
    parser.add_option("-d", "--disable-pass", action="store_true", dest="dispass", default=False,
                help="Do not prompt SSH login password for remote hosts. \
                      If set, be sure passwordless ssh is configured.")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                help="Verbose mode for ansible.")
    parser.add_option("--dryrun", action="store_true", dest="dryrun", default=False,
                help="Dry run mode, it will only generate the config file.") 
    parser.add_option("--dbmgr-only", action="store_true", dest="dbmgr", default=False,
                help="Install esgynDB manager only, be sure esgynDB is previously installed.")
    parser.add_option("--dbmgr-rpm", dest="dbmgrrpm", metavar="RPMFILE",
                help="Specify esgynDB manager RPM location.")

    (options, args) = parser.parse_args()

    # handle parser option
    if options.dbmgr and not options.dbmgrrpm: log_err('Wrong parameter, must specify both --dbmgr-only and --dbmgr-rpm')
    if not options.dbmgr and options.dbmgrrpm: log_err('Wrong parameter, must specify both --dbmgr-only and --dbmgr-rpm')

    #######################################
    # get user input and gen variable file
    #######################################
    format_output('EsgynDB Installation Start')
    global cfgs, installer_loc
    def_cfgfile = installer_loc + '/esgyndb_config'
    if options.cfgfile:
        if not os.path.exists(options.cfgfile): 
            log_err('Cannot find config file \'%s\'' % options.cfgfile)
        config_file = options.cfgfile
    else:
        config_file = def_cfgfile

    p = ParseJson(config_file)

    # TODO: get a way to determine trafodion/esgyndb, set the flag to true or false
    no_dbmgr = False

    # must install Trafodion first if using dbmgr only mode
    if options.dbmgr and not os.path.exists(config_file):
        log_err('Must specify the config file, which means you have previously installed Trafodion')

    # not specified config file and default config file doesn't exist either
    if options.dryrun or (not os.path.exists(config_file)): 
        if options.dryrun: format_output('DryRun Start')
        user_input(no_dbmgr)
        
        hg = HttpGet(cfgs['mgr_user'], base64.b64decode(cfgs['mgr_pwd']))

        cm = hg.get_content('%s/api/v6/cm/deployment' % cfgs['mgr_url'])
        # get cluster info, assume only one cluster being managed
        cluster_name = cm['clusters'][0]['displayName']
        cluster_version = cm['clusters'][0]['version']
        fullversion = cm['clusters'][0]['fullVersion']

        # TODO: support HDP later
        if not 'CDH' in cluster_version:
            log_err('Cannot detect Cloudera, currently EsgynDB only supports CDH')
        elif not '5.4' in fullversion:
            log_err('Incorrect CDH version, currently EsgynDB only supports CDH5.4')

        # get list of HBase RegionServer nodes
        hostids = []
        rsnodes = []
        for c in cm['clusters']:
            if c['displayName'] == cluster_name:
                for s in c['services']:
                    if s['type'] == 'HBASE':
                        for r in s['roles']:
                            if r['type'] == 'REGIONSERVER': hostids.append(r['hostRef']['hostId'])

        for i in hostids:
            for h in cm['hosts']:
                if i == h['hostId']: rsnodes.append(h['hostname'])

        rsnodes.sort()
        # set trafodion node list the same as HBase RS nodes
        if not cfgs['node_list']:
            cfgs['node_list'] = ' ' + ' '.join(rsnodes)

        # set other config to cfgs
        cfgs['my_nodes'] = cfgs['node_list'].replace(' ', ' -w ')
        cfgs['first_node'] = cfgs['node_list'].split()[0]
        cfgs['first_rsnode'] = rsnodes[0] # first regionserver node
        cfgs['cluster_name'] = cluster_name.replace(' ','%20')

        cfgs['hbase_xml_file'] = '/etc/hbase/conf/hbase-site.xml'


        cfgs['config_created_date'] = time.strftime('%Y/%m/%d %H:%M %Z')

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
            if config_file == def_cfgfile:
                os.rename(config_file, config_file + '.bak' + ts)
        except OSError:
            log_err('Cannot rename config file')

        # remove temp config file
        if os.path.exists(tmp_file): os.remove(tmp_file)
    
    else:
        format_output('DryRun Complete')

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        tp = ParseJson(tmp_file)
        tp.jsave(cfgs)
        print '\nAborted...'
