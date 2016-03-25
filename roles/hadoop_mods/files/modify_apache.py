#!/usr/bin/env python
import sys
try: 
  import xml.etree.cElementTree as ET 
except ImportError: 
  import xml.etree.ElementTree as ET

hbase_xml = sys.argv[1]
hdfs_xml = sys.argv[2]

mod_cfgs = {
    'hbase': {
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
    'hdfs': { 'dfs.namenode.acls.enabled': 'true' },
    'zoo.cfg': { 'maxClientCnxns': '0' }
}

class HandleXML:
    def __init__(self, xml_file):
        self._xml_file = xml_file
        try:
            self._tree = ET.parse(self._xml_file)
        except:
            print ('***ERROR: failed to parsing xml') 
            sys.exit(1)
            
        self._root = self._tree.getroot()
        self._nvlist = []
        for prop in self._root.findall('property'):
            t_array = []
            for elem in prop:
                t_array.append(elem.text) 
            self._nvlist.append(t_array)

    def __indent(self, elem):
        """Return a pretty-printed XML string for the Element."""
        if len(elem):
            if not elem.text: elem.text = '\n' + '  '
            if not elem.tail: elem.tail = '\n'
            for subelem in elem:
                self.__indent(subelem)
        else:
            if not elem.tail: elem.tail = '\n' + '  '

    def get_property(self, name):
        try:
            return [x[1] for x in self._nvlist if x[0]==name][0]
        except:
            return ''

    def add_property(self, name, value):
        # don't add property if already exists
        if self.get_property(name): return
        elem_p = ET.Element('property')
        elem_name = ET.Element('name')
        elem_value = ET.Element('value')

        elem_name.text = name
        elem_value.text = value
        elem_p.append(elem_name)
        elem_p.append(elem_value)

        self._root.append(elem_p)

    def write_xml(self):
        self.__indent(self._root)
        self._tree.write(self._xml_file)

    def output_xmlinfo(self):
        for n,v in self._nvlist:
            print n,v


hbasexml = HandleXML(hbase_xml)
for n,v in mod_cfgs['hbase'].items():
    hbasexml.add_property(n, v)
hbasexml.write_xml()

hdfsxml = HandleXML(hdfs_xml)
for n,v in mod_cfgs['hdfs'].items():
    hdfsxml.add_property(n, v)
hdfsxml.write_xml()
