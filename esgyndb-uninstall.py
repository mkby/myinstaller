#!/usr/bin/env python

import sys
import os
from optparse import OptionParser

installer_loc = sys.path[0]

def format_output(text):
    num = len(text) + 4
    print '*' * num
    print '  ' + text
    print '*' * num

def log_err(errtext):
    print '***ERROR: ' + errtext
    sys.exit(1)

def main():
    """ uninstaller main loop """

    usage = 'usage: %prog [options]\n'
    usage += '  Trafodion uninstall script. It will uninstall trafodion rpm \
  and remove trafodion user\'s home folder.'
    parser = OptionParser(usage=usage)
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

    # calling ansible to uninstall
    rc = raw_input('Uninstall trafodion, press [y] to continue: ')
    if rc.lower() != 'y': sys.exit(1)

    format_output('Uninstall Start')

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
