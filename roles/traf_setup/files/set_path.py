#!/usr/bin/python

import sys

try:
    sq_root = sys.argv[1]
    traf_ver = sys.argv[2]
except IndexError:
    print 'ERROR: missing parameters'
    sys.exit(1)

dcs_path = sq_root + '/dcs-' + traf_ver
rest_path = sq_root + '/rest-' + traf_ver
sqenv_path = sq_root + '/sqenvcom.sh'

found = 0
with open(sqenv_path, 'a+') as f:
    for line in f.readlines():
        if 'DCS_INSTALL_DIR' in line:
            found = 1
    if not found:
        f.write('export DCS_INSTALL_DIR=' + dcs_path + '\n')
        f.write('export REST_INSTALL_DIR=' + rest_path + '\n')
f.close()
