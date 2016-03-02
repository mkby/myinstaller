## EsgynDB Ansible Installer

### Install esgynDB on top of CDH5.4/HDP2.3/Vanilla Hadoop(work in progress)

**Prerequisite:**

 - Cloudera5.4.x/Hortonworks2.3 is installed on esgynDB nodes
 - /etc/hosts is configured correctly on installer's node
 - Ansible is installed on installer's node
 - Trafodion and esgynDB-manager RPM is stored on installer's node

**Features:**

 - Support installing on multiple clusters managed by one cloudera manager
 - Support running installer from any node, as long as it can ssh to esgynDB nodes
 - Support installing esgynDB on multiple regionserver groups in cloudera manager
 - Support installing esgynDB on non-passwordless ssh nodes
 - Auto discover for HBase regionserver nodes and hbase/hdfs system user

**Examples:**

- Install esgynDB in guide mode without esgynDB manager:

``esgyndb-install.py --no-dbmgr``

- Install esgynDB in config mode with 10 parallel processes (default is 5):

``esgyndb-install.py --config-file xxx_config --fork 10``

- Run installer from local system with user a, install esgynDB on remote nodes with user b, and user b has configured passwordless ssh:

`` esgyndb-install.py --remote-user b --disable-pass``

- Generate the config file only but not doing the real install:

`` esgyndb-install.py --dryrun``
