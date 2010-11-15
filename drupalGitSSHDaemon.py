#!/usr/bin/env python
import os
import shlex
import sys
from twisted.conch.avatar import ConchUser
from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.error import ConchError
from twisted.conch.ssh import common
from twisted.conch.ssh.session import ISession, SSHSession
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.keys import Key
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor, defer
from twisted.python import components, log
from zope import interface

import ConfigParser
import urllib
import base64
import json
import hashlib

log.startLogging(sys.stderr)

class IGitMetadata(interface.Interface):
    'API for authentication and access control.'

    def repopath(self, username, reponame):
        '''
        Given a username and repo name, return the full path of the repo on
        the file system.
        '''

    def pubkeys(self, username):
        '''
        Return the list of valid public keys for a user.
        '''

    def passwords(self, username):
        '''
        Return the list of valid password hashes for a user.
        '''

class DrupalMeta(object):
    def request(self, username):
        'Build the request to run against drupal'
        url = config.get('remote-auth-server', 'url')
        path = config.get('remote-auth-server', 'path')
        params = urllib.urlencode({'user' : username})
        response = urllib.urlopen(url + '/' + path + '?%s' % params)
        result = response.readline()
        return json.loads(result)

    def repopath(self, username, reponame):
        '''Note, this is where we could do further mapping into a subdirectory
        for a user or issue's specific sandbox'''

        'Build the path to the repository'
        path = config.get('daemon', 'repositoryPath')
        path = path + reponame + ".git"
        project = '';
        'Check to see that the folder exists'
        log.msg(path)
        if not os.path.exists(path):
          return None

        projectName = reponame[1:] 
        repos = self.request(username)["repos"]
        if projectName not in repos:
          raise ConchError('Permission denied %s was not in %s' % (projectName, repos))

        return path

    def pubkeys(self, username):
        return self.request(username)["keys"]

    def passwords(self, username):
        return self.request(username)["password"],

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
        fingerprint = Key.fromString(credentials.blob).fingerprint()
        fingerprint = fingerprint.replace(':','')
        for k in self.meta.pubkeys(credentials.username):
            if k == fingerprint:
                return True
        return False
        
class GitPasswordChecker(object):
    credentialInterfaces = IUsernamePassword,
    interface.implements(ICredentialsChecker)
    def __init__(self, meta):
        self.meta = meta

    def requestAvatarId(self, credentials):
        for k in self.meta.passwords(credentials.username):
            md5_password = hashlib.md5(credentials.password).hexdigest()
            if k == md5_password:
                return defer.succeed(credentials.username)
        return defer.fail(UnauthorizedLogin("invalid password"))

class GitServer(SSHFactory):
    authmeta = DrupalMeta()
    portal = Portal(GitRealm(authmeta))
    portal.registerChecker(GitPubKeyChecker(authmeta))
    portal.registerChecker(GitPasswordChecker(authmeta))

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
