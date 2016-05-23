#!/usr/bin/env python

import sys
from cm_api.api_client import ApiResource, ApiException
from cm_api.endpoints.services import ApiServiceSetupInfo
from time import sleep
from ConfigParser import ConfigParser
from collections import defaultdict
from random import choice

class Deploy:
    def __init__(self, cm_host=None, cm_port='7180', cm_user='admin', cm_passwd='admin', cluster_name='cluster1'):

        self.cluster_name = cluster_name
        self.cdh_version = "CDH5"

        self._get_host_allocate()
        self.cm_host = cm_host

        self.api = ApiResource(cm_host, cm_port, cm_user, cm_passwd, version=7)
        self.cm = self.api.get_cloudera_manager()

        try:
            self.cluster = self.api.get_cluster(self.cluster_name)
        except:
            try:
                self.cluster = self.api.create_cluster(self.cluster_name, self.cdh_version)
            except:
                self._err('Cannot connect to cloudera manager on %s' % cm_host)

        # add all our hosts to the cluster
        try:
            self.cluster.add_hosts(self.host_list)
            self._info('Add hosts successfully')
        except Exception as e:
            if e.code == 400:
                self._info('Already Added hosts')
            elif e.code == 404:
                self._err(e.message)

    def _err(self, msg):
        print '\n\33[31m***[ERROR]: %s \33[0m' % msg
        exit(0)

    def _info(self, msg):
        print '\n\33[33m***[INFO]: %s \33[0m' % msg

    def _ok(self, msg):
        print '\n\33[32m***[OK]: %s \33[0m' % msg

    def _auto_allocate(self, hosts):
        # enable mgmt node if node count is larger than mgmt_th
        mgmt_th = 6

        if type(hosts) != list: self._err('hosts parameter should be a list')
        host_num = len(hosts)
        # node<=3, ZK=1 ,node>3, ZK=3
        zk_num = 1 if host_num <= 3 else 3

        # with mgmt node
        if host_num >= mgmt_th: 
            self.ap_host = self.es_host = self.ho_host = self.sm_host = self.nn_host = self.hm_host = self.jt_host = hosts[0]
            self.dn_hosts = self.rs_hosts = self.tt_hosts = hosts[1:]
            self.snn_host = hosts[1]
            self.hms_host = hosts[2]
            self.hs2_host = hosts[3]
        # without mgmt node
        else:
            if host_num == 1:
                self.ap_host = self.es_host = self.ho_host = self.sm_host = self.jt_host = \
                self.nn_host = self.hm_host = self.snn_host = self.hms_host = self.hs2_host = hosts[0]
            elif host_num > 1:
                # nn, snn not on same node
                tmp_hosts = hosts[:]
                self.nn_host = choice(tmp_hosts)
                tmp_hosts.remove(self.nn_host)
                self.snn_host = choice(tmp_hosts)
                self.hm_host = choice(tmp_hosts)
                self.jt_host = choice(hosts)
                self.hms_host = choice(hosts)
                self.hs2_host = choice(hosts)
                # cm
                self.ap_host = choice(hosts)
                self.es_host = choice(hosts)
                self.ho_host = choice(hosts)
                self.sm_host = choice(hosts)

            self.dn_hosts = self.rs_hosts = self.tt_hosts = hosts

        self.zk_hosts = hosts[-zk_num:]

    def _get_host_allocate(self):
        config_file = 'config.ini'
        conf = ConfigParser()
        conf.read(config_file)
        try:
            hosts_data = conf.items('hosts')
        except:
            self._err('Incorrect config format')

        try:
            roles_data = conf.items('roles')
        except:
            roles_data = []

        try:
            self.host_list = [ i.strip() for i in hosts_data[0][1].split(',') ]
        except IndexError:
            self._err('Failed to parse hosts from %s' % config_file)

        cfg_data = [ [i[0],i[1].split(',')] for i in roles_data ]
        # auto set if no role config found
        if not cfg_data:
            self._auto_allocate(self.host_list)
            return

        valid_roles = ['DN', 'RS', 'ZK', 'HM', 'NN', 'SNN', 'AP', 'ES', 'SM', 'HO', 'TT', 'JT', 'HMS', 'HS2']
        role_host = defaultdict(list)

        for item in cfg_data:      
            for role in item[1]:
                role = role.strip()
                if role not in valid_roles: self._err('Incorrect role config')
                role_host[role].append(item[0])

        # cdh
        self.nn_host = role_host['NN'][0]
        self.snn_host = role_host['SNN'][0]
        self.hm_host = role_host['HM'][0]
        self.jt_host = role_host['JT'][0]
        self.hms_host = role_host['HMS'][0]
        self.hs2_host = role_host['HS2'][0]
        self.tt_hosts = role_host['TT']
        self.zk_hosts = role_host['ZK']
        self.dn_hosts = role_host['DN']
        self.rs_hosts = role_host['RS']
        # cm
        self.ap_host = role_host['AP'][0]
        self.es_host = role_host['ES'][0]
        self.ho_host = role_host['HO'][0]
        self.sm_host = role_host['SM'][0]

    def setup_cms(self):
        try:
            self.cm.delete_mgmt_service()
        except:
            pass

        # create the management service
        try:
            mgmt = self.cm.create_mgmt_service(ApiServiceSetupInfo())
            mgmt.create_role('AlertPublisher', "ALERTPUBLISHER", self.ap_host)
            mgmt.create_role('EventServer', "EVENTSERVER", self.es_host)
            mgmt.create_role('HostMonitor', "HOSTMONITOR", self.hm_host)
            mgmt.create_role('ServiceMonitor', "SERVICEMONITOR", self.sm_host)
            self._ok('Cloudera management service created successfully.')
        except ApiException:
            self._info('Cloudera management service had already been created.')

    def setup_parcel(self):
        parcels_list = []
        for i,p in enumerate(self.cluster.get_all_parcels()):
            if p.stage == 'AVAILABLE_REMOTELY': continue
            elif p.stage == 'ACTIVATED':
                self._info('Parcel [%s] has already been activated' % p.version)
                return
            else:
                print "Available parcels:"
                print '\t' + str(i) + ': ' + p.product + ' ' + p.version
                parcels_list.append(p)

        if len(parcels_list) == 0:
            self._err('No downloaded ' + self.cdh_version + ' parcel found!')
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

        self._ok(cdh_parcel.product + ' ' + cdh_parcel.version + ' distributed')

        # activate the parcel
        cmd = cdh_parcel.activate()
        if cmd.success != True:
            self._err('Parcel activation failed!')

        # make sure the activation finishes
        while cdh_parcel.stage != "ACTIVATED":
            sleep(5)
            cdh_parcel = self.cluster.get_parcel(cdh_parcel.product, cdh_parcel.version)

        self._ok(cdh_parcel.product + ' ' + cdh_parcel.version + ' activated')

    def _create_service(self, sdata):
        try:
            self.cluster.get_service(sdata['sname'])
            self._info('Service %s had already been configured' % sdata['sname'])
        except ApiException:
            service = self.cluster.create_service(sdata['sname'], sdata['stype'])
            self._ok('Service %s had been created successfully' % sdata['sname'])
            for role in sdata['roles']:
                if role.has_key('rhost'):
                    service.create_role(role['rname'], role['rtype'], role['rhost'])
                elif role.has_key('rhosts'):
                    rid = 0
                    for host in role['rhosts']:
                        rid += 1
                        service.create_role(role['rname'] + '-' + str(rid), role['rtype'], host)

    def setup_cdh(self):
        service_data = [ { 'sname': 'hdfs', 'stype': 'HDFS',
                           'roles': [ {'rname': 'hdfs-namenode', 'rtype': 'NAMENODE', 'rhost': self.nn_host},
                                      {'rname': 'hdfs-secondarynamenode', 'rtype': 'SECONDARYNAMENODE', 'rhost': self.snn_host},
                                      {'rname': 'hdfs-datanode', 'rtype': 'DATANODE', 'rhosts': self.dn_hosts} ]
                         },
                         { 'sname': 'zookeeper', 'stype': 'ZOOKEEPER',
                           'roles': [ {'rname': 'zookeeper', 'rtype': 'SERVER', 'rhosts': self.zk_hosts} ]
                         },
                         { 'sname': 'hbase', 'stype': 'HBASE', 
                           'roles': [ {'rname': 'hbase-master', 'rtype': 'MASTER', 'rhost': self.hm_host},
                                      {'rname': 'hdfs-regionserver', 'rtype': 'REGIONSERVER', 'rhosts': self.rs_hosts} ]
                         },
                         { 'sname': 'hive', 'stype': 'HIVE', 
                           'roles': [ {'rname': 'hive-metastore', 'rtype': 'HIVEMETASTORE', 'rhost': self.hms_host}, 
                                      {'rname': 'hive-server2', 'rtype': 'HIVESERVER2', 'rhost': self.hs2_host},
                                      {'rname': 'hive-gateway', 'rtype': 'GATEWAY', 'rhosts': self.dn_hosts} ]
                         },
                         { 'sname': 'mapreduce', 'stype': 'MAPREDUCE', 
                           'roles': [ {'rname': 'mapreduce-jobtracker', 'rtype': 'JOBTRACKER', 'rhost': self.jt_host},
                                      {'rname': 'mapreduce-tasktracker', 'rtype': 'TASKTRACKER', 'rhosts': self.tt_hosts} ]
                         }
                      ]

        for sdata in service_data:
            self._create_service(sdata)

        # additional config for hive
        try:
            hive_service = self.cluster.get_service('hive')
            hive_metastore_host = self.cm_host # should be same as cm's host, FQDN
            hive_metastore_name = 'hive'
            hive_metastore_password = 'hive'
            hive_metastore_database_port = '7432'
            hive_metastore_database_type = 'postgresql'
            hive_config = { 'hive_metastore_database_host' : hive_metastore_host, \
                            'hive_metastore_database_name' : hive_metastore_name, \
                            'hive_metastore_database_password' : hive_metastore_password, \
                            'hive_metastore_database_port' : hive_metastore_database_port, \
                            'hive_metastore_database_type' : hive_metastore_database_type }
            hive_service.update_config(hive_config)
            self._ok('Additional hive configs had been updated')
        except ApiException as e:
            self._err(e.message)

        # use auto configure for *-site.xml configs
        try:
            self.cluster.auto_configure()
        except ApiException as e:
            self._err(e.message)

    def start_cms(self):
        # start the management service
        self._info('Starting cloudera management service...')
        cms = self.cm.get_service()
        cms.start().wait()
        self._ok('Cloudera management service started successfully')

    def start_cdh(self):
        self._info('Excuting first run command. This might take a while.')
        cmd = self.cluster.first_run()

        while cmd.success == None:
            cmd = cmd.fetch()
            sleep(1)

        if cmd.success != True:
            self._err('The first run command failed: ' + cmd.resultMessage)

        self._ok('First run successfully executed. Your cluster has been set up!')

if __name__ == "__main__":
    if len(sys.argv)==1: 
        print '***ERROR: Please input cloudera master hostname with FQDN'
        exit(1)
    deploy = Deploy(cm_host=sys.argv[1])
    deploy.setup_cms()
    deploy.setup_parcel()
    deploy.start_cms()
    deploy.setup_cdh()
    deploy.start_cdh()
