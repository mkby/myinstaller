#!/usr/bin/env python
import os
import json
from ConfigParser import ConfigParser
from collections import defaultdict


def ok(msg):
    print '\n\33[32m***[OK]: %s \33[0m' % msg

def info(msg):
    print '\n\33[33m***[INFO]: %s \33[0m' % msg

def err(msg):
    print '\n\33[31m***[ERROR]: %s \33[0m' % msg
    exit(0)

class ParseJson:
    """ 
    jload: load json file to a dict
    jsave: save dict to json file with pretty format
    """
    def __init__(self, js_file):
        self.js_file = js_file

    def jload(self):
        with open(self.js_file, 'r') as f:
            tmparray = f.readlines()
        content = ''
        for t in tmparray:
            content += t

        try:
            return defaultdict(str, json.loads(content))
        except ValueError:
            log_err('No json format found in config file')

    def jsave(self, dic):
        with open(self.js_file, 'w') as f:
            f.write(json.dumps(dic, indent=4))

class ParseConfig:
    def __init__(self):
        self.cfg_file = 'config.ini'
        self.conf = ConfigParser()
        self.conf.read(self.cfg_file)

    def _get_hosts(self):
        try:
            return [ i.strip() for i in self.conf.items('hosts')[0][1].split(',') ]
        except IndexError:
            err('Failed to parse hosts from %s' % self.cfg_file)

    def _get_roles(self):
        try:
            return [ [i[0],i[1].split(',')] for i in self.conf.items('roles') ]
        except:
            return []

    def _get_dir(self, dir_name):
        try:
            return [c[1] for c in self.conf.items('cdh_config') if c[0] == dir_name][0]
        except:
            return ''

    def _get_repodir(self):
        return self._get_dir('repo_dir')

    def _get_parceldir(self):
        return self._get_dir('parcel_dir')

    def get_item(self, item):
        if item == 'hosts': return self._get_hosts()
        elif item == 'roles': return self._get_roles()
        elif item == 'repo_dir': return self._get_repodir()
        elif item == 'parcel_dir': return self._get_parceldir()
        else: err('Incorrect item')
    
def http_start(repo_dir, repo_port):
    info('Starting temporary python http server')
    os.system("cd %s; python -m SimpleHTTPServer %s > /dev/null 2>&1 &" % (repo_dir, repo_port))

def http_stop():
    info('Stopping python http server')
    os.system("ps -ef|grep SimpleHTTPServer |grep -v grep | awk '{print $2}' |xargs kill -9")

def format_output(text):
    num = len(text) + 4
    print '*' * num
    print '  ' + text
    print '*' * num

def expNumRe(text):
    """
    expand numeric regular expression to list
    e.g. 'n[01-03] n1[0-1]': ['n01','n02','n03','n10','n11']
    e.g. 'n[09-11].com': ['n09.com','n10.com','n11.com']
    """
    explist = []
    for regex in text.split():
        r = re.match(r'(.*)\[(\d+)-(\d+)\](.*)',regex)
        if r:
            h = r.group(1)
            d1 = r.group(2)
            d2 = r.group(3)
            t = r.group(4)

            convert = lambda d: str(('%0' + str(min(len(d1), len(d2))) + 'd') % d)
            if d1 > d2: d1,d2 = d2,d1
            explist.extend([h + convert(c) + t for c in range(int(d1), int(d2)+1)])

        else:
            # keep original value if not matched
            explist.append(regex)

    return explist

def time_elapse(start, end):
    """ set time format from seconds to h:m:s """
    seconds = end - start
    hours = seconds / 3600
    seconds = seconds % 3600
    minutes = seconds / 60
    seconds = seconds % 60
    print "Installation time: %d hour(s) %d minute(s) %d second(s)" % (hours, minutes, seconds)

if __name__ == "__main__":
    exit(0)
