#!/usr/bin/env python
import sys
import httplib2
import json
import base64
import time

mgr_user = sys.argv[1] 
mgr_pwd = sys.argv[2]
cluster_url = sys.argv[3]
desired_config_url = cluster_url + '?fields=Clusters/desired_configs'
config_url = cluster_url + '/configurations?type={0}&tag={1}'

mod_cfgs = {
    'hbase-site': {
        'hbase.master.distributed.log.splitting': 'false',
        'hbase.coprocessor.region.classes': 'org.apache.hadoop.hbase.coprocessor.transactional.TrxRegionObserver,org.apache.hadoop.hbase.coprocessor.transactional.TrxRegionEndpoint,org.apache.hadoop.hbase.coprocessor.AggregateImplementation',
        'hbase.hregion.impl': 'org.apache.hadoop.hbase.regionserver.transactional.TransactionalRegion',
        'hbase.regionserver.region.split.policy': 'org.apache.hadoop.hbase.regionserver.ConstantSizeRegionSplitPolicy',
        'hbase.snapshot.enabled': 'true',
        'hbase.bulkload.staging.dir': '/hbase-staging',
        'hbase.regionserver.region.transactional.tlog': 'true',
        'hbase.snapshot.master.timeoutMillis': '600000',
        'hbase.snapshot.region.timeout': '600000',
        'hbase.client.scanner.timeout.period': '600000'
    },
    'hdfs-site': { 'dfs.namenode.acls.enabled': 'true' },
    'zoo.cfg': { 'maxClientCnxns': '0' }
}

class Ambari_Rest:
    def __init__(self, user, passwd):
        self.h = httplib2.Http(disable_ssl_certificate_validation=True)
        self.h.add_credentials(user, passwd)
        self.headers = {}
        self.headers["Authorization"] = "Basic %s" % (base64.b64encode("%s:%s" % (user, passwd)))
        self.headers["X-Requested-By"] = "trafodion"

    def _request(self, url, method, body=None):
        try:
            resp, content = self.h.request(url, method, headers=self.headers, body=body)
            if resp.status != 200:
                print 'Error return code {0} when {1}ting configs'.format(resp.status, method.lower())
                sys.exit(1)
            if method == 'GET': return content 
        except Exception as exc:
            raise Exception('Error with {0}ting configs using Ambari REST api. Reason: {1}'.format(method.lower(), exc))

    def get_config(self, url):
        return json.loads(self._request(url, 'GET'))

    def set_config(self, url, config_type, properties):
        tag = 'version' + str(int(time.time() * 1000000))
        config = {
          'Clusters': {
            'desired_config': {
              'type': config_type,
              'tag': tag,
              'properties': properties
            }
          }
        }
        self._request(url, 'PUT', body=json.dumps(config))
  
### main ###
ambari_rest = Ambari_Rest(mgr_user, mgr_pwd)
desired_cfg = ambari_rest.get_config(desired_config_url)

for config_type in mod_cfgs.keys():
    desired_tag = desired_cfg['Clusters']['desired_configs'][config_type]['tag']
    current_cfg = ambari_rest.get_config(config_url.format(config_type, desired_tag))
    new_properties = current_cfg['items'][0]['properties']
    new_properties.update(mod_cfgs[config_type])
    ambari_rest.set_config(cluster_url, config_type, new_properties)
