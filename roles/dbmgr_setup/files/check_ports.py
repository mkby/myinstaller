#!/usr/bin/env python
# @@@ START COPYRIGHT @@@
#
# (C) Copyright 2015 Esgyn Corportation
#
# @@@ END COPYRIGHT @@@
import os

def check_port(port):
    rc = 0
    while not rc: 
        cmd = 'sudo netstat -anp | grep -q %d' % port
        rc = os.system(cmd)
        if not rc: port += 10
    print port

dm_http_port = 4205
dm_https_port = 4206
tsd_port = 5242
http_port = 8070

check_port(dm_http_port)
check_port(dm_https_port)
check_port(tsd_port)
check_port(http_port)

