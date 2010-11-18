#!/usr/bin/env python

import os
import sys
import ConfigParser
import json
import beanstalkc
import subprocess

repositoryPath = ''
url = ''
port = 0
beanstalk = False
job = False

if __name__ == '__main__':
  config = ConfigParser.SafeConfigParser()
  config.readfp(open(sys.path[0] + '/drupaldaemons.cnf'))
  repositoryPath = config.get('beanstalkd-git-repo-manager-daemon', 'repositoryPath')
  url = config.get('beanstalkd-git-repo-manager-daemon', 'url')
  port = config.getint('beanstalkd-git-repo-manager-daemon', 'port')
  beanstalk = beanstalkc.Connection(host=url, port=port)
  print 'The repository manager daemon has started.'

  ''' 
    TODO: This is a dead simple implementation and should be made a proper daemon 
    (probably using http://pypi.python.org/pypi/python-daemon or similar)
  '''
  while True:
    print 'Listening for a new beanstalkd job'
    job = beanstalk.reserve()
    jobData = json.loads(job.body)
    repo = repositoryPath + '/' + jobData['project'] + '.git'
    if (jobData['operation'] == 'create'):
      print 'Creating a new repository at %s' % (repo)
      try:
        os.mkdir(repo)
        os.chdir(repo)
        subprocess.call(['git', 'init', '--bare'], shell=False)
        os.chdir(repositoryPath)
      except:
        print 'Creation FAILED!'
    elif (jobData['operation'] == 'delete'):
      print 'Deleting the repository at %s' % (repo)
      try:
        subprocess.call(['rm', '-rf', (repo)], shell=False)
      except:
        print 'Deletion FAILED!'
    job.delete()
