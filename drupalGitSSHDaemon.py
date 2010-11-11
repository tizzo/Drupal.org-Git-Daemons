#!/usr/bin/env python
import os
import shlex
import sys
from twisted.conch.avatar import ConchUser
from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.error import ConchError
from twisted.conch.ssh import common
from twisted.conch.ssh.session import (ISession,
                                       SSHSession,
                                       SSHSessionProcessProtocol)
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.keys import Key
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor
from twisted.python import components, log
from zope import interface

import ConfigParser
import urllib
import base64
import json

log.startLogging(sys.stderr)

class IGitMetadata(interface.Interface):
    'API for authentication and access control.'

    def repopath(self, username, reponame):
        '''
        Given a username and repo name, return the full path of the repo on
        the file system.
        '''

class DrupalMockMeta(object):

    def repopath(self, username, reponame):
        '''Note, this is where we could do further mapping into a subdirectory
        for a user or issue's specific sandbox'''

        'Build the path to the repository'
        path = config.get('daemon', 'reposiotryPath')
        path = path + reponame
        project = '';
        'Check to see that the folder exists'
        if not os.path.exists(path):
          return None
        return path

def find_git_shell():
    # Find git-shell path.
    # Adapted from http://bugs.python.org/file15381/shutil_which.patch
    path = os.environ.get("PATH", os.defpath)
    for dir in path.split(os.pathsep):
        full_path = os.path.join(dir, 'git-shell')
        if (os.path.exists(full_path) and 
                os.access(full_path, (os.F_OK | os.X_OK))):
            return full_path
    raise Exception('Could not find git executable!')


class GitSession(object):
    interface.implements(ISession)

    def __init__(self, user):
        self.user = user

    def execCommand(self, proto, cmd):
        argv = shlex.split(cmd)
        reponame = argv[-1]
        sh = self.user.shell

        # Check permissions by mapping requested path to file system path
        repopath = self.user.meta.repopath(self.user.username, reponame)
        if repopath is None:
            raise ConchError('Invalid repository.')

        'Build the request to run against drupal'
        url = config.get('remote-auth-server', 'url')
        path = config.get('remote-auth-server', 'path')
        fingerprint = Key.fromString(self.user.meta.credentials.blob, 'BLOB').fingerprint()
        params = urllib.urlencode({'fingerprint' : fingerprint})
        response = urllib.urlopen(url + '/' + path + '?%s' % params)
        result = response.readline()
        repos = json.loads(result)
        projectName = reponame[1:-4] 
        if projectName not in repos:
          raise ConchError('Permission denied %s was not in %s' % (projectName, repos))
        command = ' '.join(argv[:-1] + ["'%s'" % (repopath,)])
        reactor.spawnProcess(proto, sh,(sh, '-c', command))

    def eofReceived(self): pass

    def closed(self): pass


class GitConchUser(ConchUser):
    shell = find_git_shell()

    def __init__(self, username, meta):
        ConchUser.__init__(self)
        self.username = username
        self.channelLookup.update({"session": SSHSession})
        self.meta = meta

    def logout(self): pass


class GitRealm(object):
    interface.implements(IRealm)

    def __init__(self, meta):
        self.meta = meta

    def requestAvatar(self, username, mind, *interfaces):
        user = GitConchUser(username, self.meta)
        return interfaces[0], user, user.logout


class GitPubKeyChecker(SSHPublicKeyDatabase):
    def __init__(self, meta):
        self.meta = meta

    def checkKey(self, credentials):
        self.meta.credentials = credentials
        if (credentials.username != 'git'):
            return False
        return True
        
class GitServer(SSHFactory):
    authmeta = DrupalMockMeta()
    portal = Portal(GitRealm(authmeta))
    portal.registerChecker(GitPubKeyChecker(authmeta))

    def __init__(self, privkey):
        pubkey = '.'.join((privkey, 'pub'))
        self.privateKeys = {'ssh-rsa': Key.fromFile(privkey)}
        self.publicKeys = {'ssh-rsa': Key.fromFile(pubkey)}


if __name__ == '__main__':
    # Load our configurations
    config = ConfigParser.SafeConfigParser()
    config.readfp(open(sys.path[0] + '/drupaldaemons.cnf'))
    port = config.getint('daemon', 'port')
    key = config.get('daemon', 'privateKeyLocation')
    components.registerAdapter(GitSession, GitConchUser, ISession)
    reactor.listenTCP(port, GitServer(key))
    reactor.run()
