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
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor, defer
from twisted.python import components, log
from zope import interface

import ConfigParser
import subprocess
import urllib
import base64
import json
import hashlib
import exceptions

def configure():
    config = ConfigParser.SafeConfigParser()
    try:
        config.readfp(open(sys.path[0] + '/drupaldaemons.cnf'))
    except IOError:
        config.readfp(open("/etc/drupaldaemons.cnf"))
    return config

class ConchAuthError(ConchError):
    pass

class IGitMetadata(interface.Interface):
    'API for authentication and access control.'

    def repopath(self, reponame):
        '''
        Given a username and repo name, return the full path of the repo on
        the file system.
        '''

class DrupalMeta(object):
    interface.implements(IGitMetadata)
    def __init__(self):
        # Load our configurations
        self.config = configure()
        self.anonymousReadAccess = self.config.getboolean('drupalSSHGitServer', 'anonymousReadAccess')

    def request(self, uri):
        """Build the request to run against drupal

        request(project uri)

        Values and structure returned:
        {username: {uid:int, 
                    repo_id:int, 
                    access:boolean, 
                    branch_create:boolean, 
                    branch_update:boolean, 
                    branch_delete:boolean, 
                    tag_create:boolean,
                    tag_update:boolean,
                    tag_delete:boolean,
                    per_label:list,
                    name:str,
                    pass:md5,
                    ssh_keys: { key_name:fingerprint }
                   }
        }"""
        try:
            webroot = self.config.get('drush-settings', 'webroot')
            drushPath = self.config.get('drush-settings', 'drushPath')
            command = '%s --root=%s vcs-auth-data %s' % (drushPath, webroot, self.projectname(uri))
            result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readline()
            self.repoAuthData = json.loads(result)
            return self.repoAuthData["users"]
        except exceptions.IOError:
            log.msg("ERROR: Could not retrieve auth information from .")
            log.msg("Verify versioncontrol-project is enabled and drush-settings settings are correct.")
            return None
        except exceptions.TypeError:
            log.msg("ERROR: Drush provided bad json.")
            log.msg(self.repoAuthData.__str__())

    def repopath(self, reponame):
        '''Note, this is where we could do further mapping into a subdirectory
        for a user or issue's specific sandbox'''

        # Build the path to the repository
        path = self.config.get('drupalSSHGitServer', 'repositoryPath')
        path = path + reponame

        # Check to see that the folder exists
        log.msg(path)
        if not os.path.exists(path):
            return None
        return path

    def projectname(self, uri):
        '''Extract the project name alone from a path like /project/views.git'''

        parts = uri.split('/')
        for part in parts:
            if len(part) > 4 and part[-4:] == '.git':
                return part[:-4]
        log.msg("ERROR: Couldn't determine project name for '%s'." % (uri,))


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

    def auth(self, reponame, argv):
        # Key fingerprint
        if hasattr(self.user.meta, "fingerprint"):
            fingerprint = self.user.meta.fingerprint
        else:
            fingerprint = None

        if hasattr(self.user.meta, "password"):
            password = self.user.meta.password
        else:
            password = None

        # Check to see if anonymous read access is enabled and if 
        # this is a read
        if (not self.user.meta.anonymousReadAccess or \
                'git-upload-pack' not in argv[:-1]):
            # If anonymous access for this type of command is not allowed, 
            # check if the user is a maintainer on this project
            # git:key, user:key, user:password
            auth_service = self.user.meta.request(reponame)
            if self.user.username == "git":
                for user in auth_service.values():
                    if fingerprint in user["ssh_keys"].values():
                        return True
            elif self.user.username in auth_service.keys():
                if fingerprint in auth_service[self.user.username]["ssh_keys"].values():
                    return True
                if auth_service[self.user.username]["pass"] == password:
                    return True
            else:
                return False
        else:
            # Read only command and anonymous access is enabled
            return True

    def execCommand(self, proto, cmd):
        argv = shlex.split(cmd)
        reponame = argv[-1]
        sh = self.user.shell

        if self.auth(reponame, argv):
            # Check permissions by mapping requested path to file system path
            repopath = self.user.meta.repopath(reponame)
            if repopath is None:
                raise ConchError('Invalid repository.')

            command = ' '.join(argv[:-1] + ["'%s'" % (repopath,)])
            reactor.spawnProcess(proto, sh, (sh, '-c', command))
        else:
            raise ConchAuthError('Permission denied when accessing {0}'.format(reponame))

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

class GitPubKeyPassthroughChecker(SSHPublicKeyDatabase):
    """Skip most of the auth process until the SSH session starts.

    Save the public key fingerprint for later use."""
    def __init__(self, meta):
        self.meta = meta

    def checkKey(self, credentials):
        fingerprint = Key.fromString(credentials.blob).fingerprint()
        self.meta.fingerprint = fingerprint.replace(':','')
	if (credentials.username == 'git'):
	    return True
	else:
	    config = configure()
            webroot = config.get('drush-settings', 'webroot')
            drushPath = config.get('drush-settings', 'drushPath')
            """ If a user specified a non-git username, check that the user's key matches their username

            so that we can request a password if it does not."""
            command = '%s --root=%s ssh-user-key %s %s' % (drushPath, webroot, credentials.username, self.meta.fingerprint)
            result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readline()
	    if result.strip() == 'true':
                return True
	    else:
	        return False

class GitPasswordPassthroughChecker(object):
    """Skip most of the auth process until the SSH session starts.

    Save the password hash for later use."""
    credentialInterfaces = IUsernamePassword,
    interface.implements(ICredentialsChecker)

    def __init__(self, meta):
        self.meta = meta

    def requestAvatarId(self, credentials):
        self.meta.password = hashlib.md5(credentials.password).hexdigest()
	config = configure()
        webroot = config.get('drush-settings', 'webroot')
        drushPath = config.get('drush-settings', 'drushPath')
        command = '%s --root=%s vcs-auth-check-user-pass %s %s' % (drushPath, webroot, credentials.username, credentials.password)
        result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readline()
	if result.strip() == 'true':
          return defer.succeed(credentials.username)
	else:
          return defer.fail(credentials.username)


class GitServer(SSHFactory):
    authmeta = DrupalMeta()
    portal = Portal(GitRealm(authmeta))
    portal.registerChecker(GitPubKeyPassthroughChecker(authmeta))
    portal.registerChecker(GitPasswordPassthroughChecker(authmeta))

    def __init__(self, privkey):
        pubkey = '.'.join((privkey, 'pub'))
        self.privateKeys = {'ssh-rsa': Key.fromFile(privkey)}
        self.publicKeys = {'ssh-rsa': Key.fromFile(pubkey)}

class Server(object):
    def __init__(self):
        # Load our configurations
        config = configure()
        self.port = config.getint('drupalSSHGitServer', 'port')
        self.key = config.get('drupalSSHGitServer', 'privateKeyLocation')
        components.registerAdapter(GitSession, GitConchUser, ISession)

    def application(self):
        return GitServer(self.key)

if __name__ == '__main__':
    log.startLogging(sys.stderr)
    ssh_server = Server()
    reactor.listenTCP(ssh_server.port, ssh_server.application())
    reactor.run()
