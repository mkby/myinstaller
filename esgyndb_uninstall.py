#!/usr/bin/env python

import sys
import os
from esgyndb_install import ParseJson, expNumRe, format_output, log_err
from optparse import OptionParser

installer_loc = sys.path[0]
hosts_file = installer_loc + '/hosts'

def main():
    """ uninstaller main loop """

    usage = 'usage: %prog [options]\n'
    usage += '  Trafodion uninstall script. It will uninstall trafodion rpm\n\
  and remove trafodion user and home folder.\n\
  Uninstall configs priority: 1. config file 2. last install 3. user input'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config-file", dest="cfgfile", metavar="FILE",
                help="Provided json format config file for uninstalling.")
    parser.add_option("-u", "--remote-user", dest="user", metavar="USER",
                help="Specify ssh login user for remote server, \
                      if not provided, use current login user as default.")
    parser.add_option("-b", "--become-method", dest="method", metavar="METHOD",
                help="Specify become method for ansible.")
    parser.add_option("-f", "--fork", dest="fork", metavar="FORK",
                help="Specify number of parallel processes to use for ansible(default=5)" )
    parser.add_option("-d", "--disable-pass", action="store_false", dest="dispass", default=False,
                help="Do not prompt SSH login password for remote hosts. \
                      If set, be sure passwordless ssh is configured.")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False,
                help="Verbose mode for ansible.")

    (options, args) = parser.parse_args()

    notify = lambda n: raw_input('Uninstall trafodion on [%s], press [y] to continue: ' % n)

    node_list = '' 
    if options.cfgfile:
        p = ParseJson(options.cfgfile)
        cfgs = p.jload()
        node_list = cfgs['node_list']
        rc = notify(node_list)
        if rc.lower() != 'y': sys.exit(1)
    else:
        try:
            with open(hosts_file, 'r') as f:
                lines = f.readlines()
                try:
                    index = lines.index('[firstnode]\n')
                except ValueError:
                    log_err('Incorrect hosts file')
            for i in range(1, index-1): 
                node_list = node_list + ' ' + lines[i].strip()
        except IOError:
            log_err('Failed to open hosts file')

        rc = notify(node_list)
        if rc.lower() != 'y':
            node_lists = raw_input('Please manually input trafodion node list to uninstall: ')
            node_list = ' '.join(expNumRe(node_lists))
            rc = notify(node_list)
            if rc.lower() != 'y': sys.exit(1)
    
    node_array = node_list.split()
    node_array = [ node + '\n' for node in node_array ]

    try:
        with open(hosts_file, 'w') as f:
            f.write('[trafnodes]\n')
            f.writelines(node_array)
            f.write('\n[firstnode]\n')
            f.writelines(node_array[0])
    except IOError:
        log_err('Failed to open hosts file')

    format_output('Uninstall Start')

    # calling ansible to uninstall
    cmd = 'ansible-playbook %s/uninstall.yml ' % installer_loc

    if not options.dispass: cmd += ' -k'
    if options.verbose: cmd += ' -v'
    if options.user: cmd += ' -u %s' % options.user
    if options.fork: cmd += ' -f %s' % options.fork
    if options.method: cmd += ' --become-method=%s' % options.method

    rc = os.system(cmd)
    if rc: log_err('Failed to uninstall Trafodion by ansible')

    format_output('Uninstall Complete')

if __name__ == "__main__":
    main()
