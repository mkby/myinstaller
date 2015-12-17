#!/bin/bash
# @@@ START COPYRIGHT @@@
#
# (C) Copyright 2015 Esgyn Corportation
#
# @@@ END COPYRIGHT @@@
if [ -f /etc/timezone ]; then
  TIMEZONE=`cat /etc/timezone`
elif [ -h /etc/localtime ]; then
  TIMEZONE=`readlink /etc/localtime | sed "/posix/d;s/\/usr\/share\/zoneinfo\///"`
else
  checksum=`md5sum /etc/localtime | cut -d' ' -f1`
  TIMEZONE=`find /usr/share/zoneinfo/ -type f -exec md5sum {} \; | grep "^$checksum" | sed "/posix/d;s/.*\/usr\/share\/zoneinfo\///"`
fi
echo $TIMEZONE\
| tr " " "\n"
