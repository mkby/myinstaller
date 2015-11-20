#!/usr/bin/python

import sys

try:
    cfg_file=sys.argv[1]
    dcs_cnt=int(sys.argv[2])
    node_array=sys.argv[3:]
except IndexError:
    print 'ERROR: missing parameters'
    sys.exit(1)

node_cnt=len(node_array)

per_node=dcs_cnt/node_cnt
extra_cnt=dcs_cnt%node_cnt
cnt=0
with open(cfg_file, 'w') as f:
    for node in node_array:
        cnt=cnt+1
        if cnt <= extra_cnt: 
            f.write(node+' '+str(per_node+1)+'\n')
        else:
            f.write(node+' '+str(per_node)+'\n')
f.close()
