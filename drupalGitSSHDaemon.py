#!/usr/bin/env python
import os
import shlex
import sys
from twisted.conch.avatar import ConchUser
from twisted.conch.error import ConchError
from twisted.conch.ssh.session import ISession, SSHSession, SSHSessionProcessProtocol
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.keys import Key
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword, ISSHPrivateKey
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor, defer
from twisted.python import components, log
from zope import interface

# Workaround for early EOF in git-receive-pack
# Seems related to Twisted bug #4350
# See: http://twistedmatrix.com/trac/ticket/4350
SSHSessionProcessProtocol.outConnectionLost = lambda self: None

import urllib
import base64
import hashlib
import exceptions

from config import config
import drush

class DrupalMeta(object):
    def __init__(self):
        self.anonymousReadAccess = config.getboolean('drupalSSHGitServer', 'anonymousReadAccess')

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
            drush_process = drush.DrushProcessProtocolJSON('vcs-auth-data')
            drush_process.call(self.projectname(uri))
            def asynchJSON(self):
                return self.data
            drush_process.deferred.addCallback(asynchJSON)
            return drush_process.deferred
        except exceptions.IOError:
            log.msg("ERROR: Could not retrieve auth information from %s." % (command,))
            log.msg("Verify versioncontrol-project is enabled and drush-settings settings are correct.")
        except exceptions.TypeError:
            log.msg("ERROR: Drush provided bad json.")
            log.msg(self.repoAuthData.__str__())

    def repopath(self, reponame):
        '''Note, this is where we could do further mapping into a subdirectory
        for a user or issue's specific sandbox'''

        # Build the path to the repository
        path = config.get('drupalSSHGitServer', 'repositoryPath')
        path = path + reponame

        # Check to see that the folder exists
        log.msg(path)
        if not os.path.exists(path):
            raise ConchError('Invalid repository: {0}'.format(reponame))

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

    def auth(self, auth_service, argv):
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
            # "git":key
            if self.user.username == "git":
                for user in auth_service.values():
                    if fingerprint in user["ssh_keys"].values():
                        return True, auth_service
            # Username in maintainers list
            elif self.user.username in auth_service.keys():
                # username:key
                if fingerprint in auth_service[self.user.username]["ssh_keys"].values():
                    return True, auth_service
                # username:password
                elif auth_service[self.user.username]["pass"] == password:
                    return True, auth_service
                else:
                    return False
            else:
                return False
        else:
            # Read only command and anonymous access is enabled
            return True, auth_service

    def execCommand(self, proto, cmd):
        argv = shlex.split(cmd)
        # This starts an auth request and returns.
        auth_service_deferred = self.user.meta.request(argv[-1])
        # Once it completes, auth is run
        auth_service_deferred.addCallback(self.auth, argv)
        # Then the result of auth is passed to execGitCommand to run git-shell
        auth_service_deferred.addCallback(self.execGitCommand, argv, proto)

    def execGitCommand(self, auth_values, argv, proto):
        reponame = argv[-1]
        authed, auth_service = auth_values
        if authed:
            # Check permissions by mapping requested path to file system path
            try:
                repopath = self.user.meta.repopath(reponame)
                env = {'VERSION_CONTROL_GIT_REPOSITORY':self.user.meta.projectname(reponame),
                       'VERSION_CONTROL_GIT_USERNAME':self.user.username}
                if self.user.username in auth_service:
                    # The UID is known
                    env['VERSION_CONTROL_GIT_UID'] = auth_service[self.user.username]['uid']

                command = ' '.join(argv[:-1] + ["'{0}'".format(repopath)])
                sh = self.user.shell
                log.msg(env)
                reactor.spawnProcess(proto, sh, (sh, '-c', command), env=env)
            except ConchError, e:
                log.err(str(e))
        else:
            log.err('Permission denied when accessing {0}'.format(reponame))

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

class GitPubKeyPassthroughChecker(object):
    """Skip most of the auth process until the SSH session starts.

    Save the public key fingerprint for later use."""
    credentialInterfaces = ISSHPrivateKey,
    interface.implements(ICredentialsChecker)

    def __init__(self, meta):
        self.meta = meta

    def requestAvatarId(self, credentials):
        fingerprint = Key.fromString(credentials.blob).fingerprint()
        self.meta.fingerprint = fingerprint.replace(':','')
        if (credentials.username == 'git'):
            return defer.succeed(credentials.username)
        else:
            """ If a user specified a non-git username, check that the user's key matches their username

            so that we can request a password if it does not."""
            drush_process = drush.DrushProcessProtocol('ssh-user-key')
            drush_process.call(credentials.username, fingerprint)
            def username(self):
                if self.data:
                    return credentials.username
                else:
                    return defer.fail(credentials.username)
            drush_process.deferred.addCallback(username)
            return drush_process.deferred

class GitPasswordPassthroughChecker(object):
    """Skip most of the auth process until the SSH session starts.

    Save the password hash for later use."""
    credentialInterfaces = IUsernamePassword,
    interface.implements(ICredentialsChecker)

    def __init__(self, meta):
        self.meta = meta

    def requestAvatarId(self, credentials):
        self.meta.password = hashlib.md5(credentials.password).hexdigest()
        drush_process = drush.DrushProcessProtocol('vcs-auth-check-user-pass')
        drush_process.call(credentials.username, credentials.password)
        def username(self):
            if self.data:
                return credentials.username
            else:
                return defer.fail(credentials.username)
        drush_process.deferred.addCallback(username)
        return drush_process

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
