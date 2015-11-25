#!/usr/bin/env python

import sys
import os
from datetime import date

try:
    installer_loc = sys.argv[1]
    node_list = sys.argv[2]
except IndexError:
    print 'ERROR: missing parameters'
    sys.exit(1)


node_array = node_list.split()
first_node = node_array[0]
node_array = [ node + '\n' for node in node_array ]

cfg_file = os.getenv('HOME') + '/.ansible.cfg'
hosts_file = installer_loc + '/hosts'
today = date.today().strftime('%Y%m%d') 

if not os.path.exists(cfg_file):
    try:
        with open(cfg_file, 'w') as f:
            f.write('[defaults]\n')
            f.write('log_path = /var/log/esgyndb_install_' + today + '.log\n')
            f.write('host_key_checking = False')
            f.write('inventory =' + hosts_file + '\n')
        f.close()
    except IOError:
        print 'ERROR: Failed to open ansible.cfg file'
        sys.exit(1)

try:
    with open(hosts_file, 'w') as f:
        f.write('[trafnodes]\n')
        f.writelines(node_array)
        f.write('\n[firstnode]\n')
        f.write(first_node)
    f.close()
except IOError:
    print 'ERROR: Failed to open hosts file'
    sys.exit(1)
