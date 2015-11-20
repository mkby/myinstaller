#!/bin/bash
echo
echo "******************************"
echo " EsgynDB INSTALLATION START"
echo "******************************"
fullpath=`readlink -f $0`
installer_loc=${fullpath%/*}
echo $installer_loc
ansible-playbook gen_vars.yml -e installer_loc=$installer_loc -i $installer_loc/default_hosts
if [[ $? -ne 0 ]]; then
  exit -1
fi
echo "******* start install ********"
ansible-playbook install.yml
