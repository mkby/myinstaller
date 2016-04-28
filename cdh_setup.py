#!/usr/bin/env python

import sys
from cm_api.api_client import ApiResource, ApiException
from cm_api.endpoints.services import ApiServiceSetupInfo
from time import sleep
from ConfigParser import ConfigParser
from collections import defaultdict
from random import choice

class Deploy:
    def __init__(self, cm_host='eason-1', cm_port='7180', cm_user='admin', cm_passwd='admin', cluster_name='easoncluster'):
        self.services = {
                       "ZOOKEEPER" : "Zookeeper",
                       "HDFS" : "hdfs",
                       "HBASE" : "hbase"}

        self.cluster_name = cluster_name
        self.cdh_version = "CDH5"

        self._get_host_allocate()

        self.api = ApiResource(cm_host, cm_port, cm_user, cm_passwd, version=7)
        self.cm = self.api.get_cloudera_manager()
        try:
            self.cluster = self.api.get_cluster(self.cluster_name)
        except ApiException:
            self.cluster = self.api.create_cluster(self.cluster_name, self.cdh_version)

        # add all our hosts to the cluster
        try:
            self.cluster.add_hosts(self.host_list)
            self._info('Add hosts successfully')
        except Exception as e:
            print e
            self._info('Already Added hosts')

    def _err(self, msg):
        print '\n***ERROR: ' + msg
        exit(0)

    def _info(self, msg):
        print '\n***INFO: ' + msg

    def _auto_allocate(self, hosts):
        # enable mgmt node if node count is larger than mgmt_th
        mgmt_th = 6

        if type(hosts) != list: self._err('hosts parameter should be a list')
        host_num = len(hosts)
        # node<=3, ZK=1 ,node>3, ZK=3
        zk_num = 1 if host_num <= 3 else 3

        # with mgmt node
        if host_num >= mgmt_th: 
            self.ap_host = self.es_host = self.ho_host = self.sm_host = self.nn_host = self.hm_host = hosts[0]
            self.dn_hosts = self.rs_hosts = hosts[1:]
            self.snn_host = hosts[1]
        # without mgmt node
        else:
            if host_num == 1:
                self.ap_host = self.es_host = self.ho_host = self.sm_host = self.nn_host = self.hm_host = self.snn_host = hosts[0]
            elif host_num > 1:
                # nn, snn not on same node
                tmp_hosts = hosts[:]
                self.nn_host = choice(tmp_hosts)
                tmp_hosts.remove(self.nn_host)
                self.snn_host = choice(tmp_hosts)
                self.hm_host = choice(tmp_hosts)
                # cm
                self.ap_host = choice(hosts)
                self.es_host = choice(hosts)
                self.ho_host = choice(hosts)
                self.sm_host = choice(hosts)

            self.dn_hosts = self.rs_hosts = hosts

        self.zk_hosts = hosts[-zk_num:]


    def _get_host_allocate(self):
        conf = ConfigParser()
        conf.read("config.ini")
        try:
            hosts_data = conf.items('hosts')
            roles_data = conf.items('roles')
        except NoSectionError:
            self._err('Incorrect config format')

        self.host_list = [ i.strip() for i in hosts_data[0][1].split(',') ]

        # parse role from config.ini
        cfg_data = [ [i[0],i[1].split(',')] for i in roles_data ]
        if not cfg_data:
            self._auto_allocate(self.host_list)
            return

        valid_roles = ['DN', 'RS', 'ZK', 'HM', 'NN', 'SNN', 'AP', 'ES', 'SM', 'HO']
        role_host = defaultdict(list)

        for item in cfg_data:      
            for role in item[1]:
                role = role.strip()
                if role not in valid_roles: self._err('Incorrect role config')
                role_host[role].append(item[0])

        print role_host
        # cdh
        self.nn_host = role_host['NN'][0]
        self.snn_host = role_host['SNN'][0]
        self.hm_host = role_host['HM'][0]
        self.zk_hosts = role_host['ZK']
        self.dn_hosts = role_host['DN']
        self.rs_hosts = role_host['RS']
        # cm
        self.ap_host = role_host['AP'][0]
        self.es_host = role_host['ES'][0]
        self.ho_host = role_host['HO'][0]
        self.sm_host = role_host['SM'][0]

    def setup_cms(self):
        # create the management service
        try:
            #self.cm.delete_mgmt_service()
            mgmt = self.cm.create_mgmt_service(ApiServiceSetupInfo())
            mgmt.create_role('AlertPublisher', "ALERTPUBLISHER", self.ap_host)
            mgmt.create_role('EventServer', "EVENTSERVER", self.es_host)
            mgmt.create_role('HostMonitor', "HOSTMONITOR", self.hm_host)
            mgmt.create_role('ServiceMonitor', "SERVICEMONITOR", self.sm_host)
            self._info('Cloudera management service created successfully.')
        except ApiException:
            self._info('Cloudera management service had already been created.')

    def setup_parcel(self):
        parcels_list = []
        for i,p in enumerate(self.cluster.get_all_parcels()):
            if p.stage == 'AVAILABLE_REMOTELY': continue
            elif p.stage == 'ACTIVATED':
                self._info('Parcel [%s] has already been activated, skipping parcel setting...' % p.version)
                return
            else:
                print "Available parcels:"
                print '\t' + str(i) + ': ' + p.product + ' ' + p.version
                parcels_list.append(p)

        if len(parcels_list) == 0:
            self._err('No downloaded' + self.cdh_version + ' parcel found!')
        elif len(parcels_list) > 1:
            index = raw_input('input parcel number:')
            if not index.isdigit:
                self._err('Error index, must be a number')
            cdh_parcel = parcels_list[int(index)-1]
        else:
            cdh_parcel = parcels_list[0]

      #  # download the parcel
      #  print "Starting parcel download. This might take a while."
      #  cmd = cdh_parcel.start_download()
      #  if cmd.success != True:
      #      print "Parcel download failed!"
      #      exit(0)

      #  # make sure the download finishes
      #  while cdh_parcel.stage != 'DOWNLOADED':
      #  sleep(5)
      #      cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

      #  print cdh_parcel.product + ' ' + cdh_parcel.version + " downloaded"

        # distribute the parcel
        self._info('Starting parcel distribution. This might take a while.')
        cmd = cdh_parcel.start_distribution()
        i = 0
        while cmd.success == None:
            i += 1
            sleep(5)
            cmd = cmd.fetch()
            s = '.' * i
            print '\r%s' % s,
            sys.stdout.flush()
        if cmd.success != True:
            self._err('Parcel distribution failed!')

        # make sure the distribution finishes
        while cdh_parcel.stage != "DISTRIBUTED":
            sleep(5)
            cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

        self._info(cdh_parcel.product + ' ' + cdh_parcel.version + ' distributed')

        # activate the parcel
        cmd = cdh_parcel.activate()
        if cmd.success != True:
            self._err('Parcel activation failed!')

        # make sure the activation finishes
        while cdh_parcel.stage != "ACTIVATED":
            sleep(5)
            cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

        self._info(cdh_parcel.product + ' ' + cdh_parcel.version + ' activated')


    def setup_cdh(self):
        # HDFS
        try:
            self.cluster.get_service('HDFS')
            self._info('Service HDFS had already been configured')
        except ApiException:
            hdfs_service = self.cluster.create_service('HDFS', 'HDFS')
            hdfs_service.create_role('hdfs-namenode', 'NAMENODE', self.nn_host)
            hdfs_service.create_role('hdfs-secondarynamenode', 'SECONDARYNAMENODE', self.snn_host)
            dn_id = 0
            for dn_host in self.dn_hosts:
                dn_id += 1
                hdfs_service.create_role('hdfs-datanode-' + str(dn_id), 'DATANODE', dn_host)

        # HBASE
        try:
            self.cluster.get_service('HBase')
            self._info('Service HBase had already been configured')
        except ApiException:
            hbase_service = self.cluster.create_service('HBase', 'HBASE')
            hbase_service.create_role('hbase-master', 'MASTER', self.hm_host)
            rs_id = 0
            for rs_host in self.rs_hosts:
                rs_id += 1
                hbase_service.create_role('hbase-regionserver-' + str(rs_id), 'REGIONSERVER', rs_host)

        # ZOOKEEPER
        try:
            self.cluster.get_service('ZooKeeper')
            self._info('Service ZooKeeper had already been configured')
        except ApiException:
            zk_service = self.cluster.create_service('ZooKeeper', 'ZOOKEEPER')
            zk_id = 0
            for zk_host in self.zk_hosts:
               zk_id += 1
               role = zk_service.create_role('zookeeper-' + str(zk_id), 'SERVER', zk_host)
     
        # use auto configure for *-site.xml configs
        self.cluster.auto_configure()

    def start_cms(self):
        # start the management service
        self._info('Starting cloudera management service...')
        cms = self.cm.get_service()
        cms.start().wait()

    def start_cdh(self):
        self._info('Excuting first run command. This might take a while.')
        cmd = self.cluster.first_run()

        while cmd.success == None:
            cmd = cmd.fetch()
            sleep(1)

        if cmd.success != True:
            self._err('The first run command failed: ' + cmd.resultMessage)

        self._info('First run successfully executed. Your cluster has been set up!')


if __name__ == "__main__":
    deploy = Deploy()
    deploy.setup_cms()
    deploy.setup_parcel()
    deploy.setup_cdh()
    deploy.start_cms()
    deploy.start_cdh()
