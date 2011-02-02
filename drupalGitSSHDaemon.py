#!/usr/bin/env python
import os
import shlex
import sys
from twisted.conch.avatar import ConchUser
from twisted.conch.error import ConchError, UnauthorizedLogin, ValidPublicKey
from twisted.conch.ssh.channel import SSHChannel
from twisted.conch.ssh.session import ISession, SSHSession, SSHSessionProcessProtocol
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.keys import Key
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword, ISSHPrivateKey
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor, defer
from twisted.python import components, log
from twisted.python.failure import Failure
from zope import interface

# Workaround for early EOF in git-receive-pack
# Seems related to Twisted bug #4350
# See: http://twistedmatrix.com/trac/ticket/4350
SSHSessionProcessProtocol.outConnectionLost = lambda self: None

import urllib
import base64
import hashlib

from config import config
from service import Service
from service.protocols import AuthProtocol

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
        service = Service(AuthProtocol('vcs-auth-data'))
        service.request_json({"project_uri":self.projectname(uri)})
        def NoDataHandler(fail):
            fail.trap(ConchError)
            message = fail.value.value
            log.err(message)
            # Return a stub auth_service object
            return {"users":{}, "repo_id":None}
        service.addErrback(NoDataHandler)
        return service.deferred

    def repopath(self, scheme, subpath):
        '''Note, this is where we do further mapping into a subdirectory
        for a user or issue's specific sandbox'''

        # Build the path to the repository
        try:
            scheme_path = config.get(scheme, 'repositoryPath')
        except:
            # Fall back to the default configured path scheme
            scheme_path = config.get('drupalSSHGitServer', 'repositoryPath')
        path = os.path.join(scheme_path, *subpath)
        # Check to see that the folder exists
        if not os.path.exists(path):
            return None
        return path

    def projectname(self, uri):
        '''Extract the project name alone from a path like /project/views.git'''

        parts = uri.split('/')
        for part in parts:
            if len(part) > 4 and part[-4:] == '.git':
                return part[:-4]
        log.err("ERROR: Couldn't determine project name for '{0}'.".format(uri))

def find_error_script():
    for directory in sys.path:
        full_path = os.path.join(directory, "git-error")
        if (os.path.exists(full_path) and 
            os.access(full_path, (os.F_OK | os.X_OK))):
            return full_path
    raise Exception('Could not find git-error executable!')

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

    def map_user(self, username, fingerprint, users):
        """Map the username from name or fingerprint, to users item."""
        if username == "git":
            # Use the fingerprint
            for user in users.values():
                if fingerprint in user["ssh_keys"].values():
                    return user
            # No fingerprints match
            return None
        elif username in users:
            # Use the username
            return users[username]
        else:
            return None

    def auth(self, auth_service, argv):
        """Verify we have permission to run the request command."""
        # Key fingerprint
        if hasattr(self.user.meta, "fingerprint"):
            fingerprint = self.user.meta.fingerprint
        else:
            fingerprint = None

        if hasattr(self.user.meta, "password"):
            password = self.user.meta.password
        else:
            password = None

        # Check permissions by mapping requested path to file system path
        repostring = argv[-1]
        repolist = repostring.split('/')
        scheme = repolist[1]
        projectpath = repolist[2:]
        repopath = self.user.meta.repopath(scheme, projectpath)
        if not repopath:
            return Failure(ConchError("The remote repository at '{0}' does not exist. Verify that your remote is correct.".format(repostring)))

        # Map the user
        users = auth_service["users"]
        user = self.map_user(self.user.username, fingerprint, users)

        # Check to see if anonymous read access is enabled and if 
        # this is a read
        if (not self.user.meta.anonymousReadAccess or \
                'git-upload-pack' not in argv[:-1]):
            # If anonymous access for this type of command is not allowed, 
            # check if the user is a maintainer on this project
            # global values - d.o issue #1036686
            # "git":key
            if self.user.username == "git" and user and not user["global"]:
                return repopath, user, auth_service["repo_id"]
            # Username in maintainers list
            elif self.user.username in users and not user["global"]:
                # username:key
                if fingerprint in user["ssh_keys"].values():
                    return repopath, user, auth_service["repo_id"]
                # username:password
                elif user["pass"] == password:
                    return repopath, user, auth_service["repo_id"]
                else:
                    # Both kinds of username auth failed
                    error = "Permission denied when accessing '{1}' as user '{2}'".format(argv[-1], self.user.username)
                    return Failure(ConchError(error))
            else:
                # Account is globally disabled or disallowed
                # 0 = ok, 1 = suspended, 2 = ToS unchecked, 3 = other reason
                if user and user["global"] == 1:
                    error = "Your account is suspended."
                elif user and user["global"] == 2:
                    error = "You are required to accept the Git Access Agreement in your user profile before using git."
                elif user and user["global"] == 3:
                    error = "This operation cannot be completed at this time.  It may be that we are experiencing technical difficulties or are currently undergoing maintenance."
                else:
                    error = "You do not have permission to access '{0}' with the provided credentials.".format(argv[-1])
                return Failure(ConchError(error))
        else:
            # Read only command and anonymous access is enabled
            return repopath, user, auth_service["repo_id"]

    def errorHandler(self, fail, proto):
        """Catch any unhandled errors and send the exception string to the remote client."""
        fail.trap(ConchError)
        message = fail.value.value
        log.err(message)
        if proto.connectionMade():
            proto.loseConnection()
        error_script = self.user.error_script
        reactor.spawnProcess(proto, error_script, (error_script, message))

    def execCommand(self, proto, cmd):
        """Execute a git-shell command."""
        argv = shlex.split(cmd)
        # This starts an auth request and returns.
        auth_service_deferred = self.user.meta.request(argv[-1])
        # Once it completes, auth is run
        auth_service_deferred.addCallback(self.auth, argv)
        # Then the result of auth is passed to execGitCommand to run git-shell
        auth_service_deferred.addCallback(self.execGitCommand, argv, proto)
        auth_service_deferred.addErrback(self.errorHandler, proto)

    def execGitCommand(self, auth_values, argv, proto):
        """After all authentication is done, setup an environment and execute the git-shell commands."""
        repopath, user, repo_id = auth_values
        sh = self.user.shell
        
        env = {}
        if user:
            # The UID is known, populate the environment
            env['VERSION_CONTROL_GIT_UID'] = user["uid"]
            env['VERSION_CONTROL_GIT_REPO_ID'] = repo_id
            
        command = ' '.join(argv[:-1] + ["'{0}'".format(repopath)])
        reactor.spawnProcess(proto, sh, (sh, '-c', command), env=env)

    def eofReceived(self): pass

    def closed(self): pass


class GitConchUser(ConchUser):
    shell = find_git_shell()
    error_script = find_error_script()

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

class GitPubKeyChecker(object):
    """Skip most of the auth process until the SSH session starts.

    Save the public key fingerprint for later use and verify the signature."""
    credentialInterfaces = ISSHPrivateKey,
    interface.implements(ICredentialsChecker)

    def __init__(self, meta):
        self.meta = meta

    def verify(self, username, credentials, key):
        # Verify the public key signature
        # From twisted.conch.checkers.SSHPublicKeyDatabase._cbRequestAvatarId
        if not credentials.signature:
            # No signature ready
            return Failure(ValidPublicKey())
        else:
            # Ready, verify it
            try:
                if key.verify(credentials.signature, credentials.sigData):
                    return credentials.username
            except:
                log.err()
                return Failure(UnauthorizedLogin("key could not verified"))

    def requestAvatarId(self, credentials):
        key = Key.fromString(credentials.blob)
        fingerprint = key.fingerprint().replace(':', '')
        self.meta.fingerprint = fingerprint
        if (credentials.username == 'git'):
            # Todo, maybe verify the key with a process protocol call
            # (drush or http)
            def success():
                return credentials.username
            d = defer.maybeDeferred(success)
            d.addCallback(self.verify, credentials, key)
            return d
        else:
            """ If a user specified a non-git username, check that the user's key matches their username

            so that we can request a password if it does not."""
            service = Service(AuthProtocol('drupalorg-ssh-user-key'))
            service.request_bool({"username":credentials.username},
                                 {"fingerprint":fingerprint})
            def auth_callback(result):
                if result:
                    return credentials.username
                else:
                    return Failure(UnauthorizedLogin(credentials.username))
            service.addCallback(auth_callback)
            service.addCallback(self.verify, credentials, key)
            return service.deferred

class GitPasswordChecker(object):
    """Skip most of the auth process until the SSH session starts.

    Save the password hash for later use."""
    credentialInterfaces = IUsernamePassword,
    interface.implements(ICredentialsChecker)

    def __init__(self, meta):
        self.meta = meta

    def requestAvatarId(self, credentials):
        self.meta.password = hashlib.md5(credentials.password).hexdigest()
        service = Service(AuthProtocol('drupalorg-vcs-auth-check-user-pass'))
        service.request_bool({"username":credentials.username},
                             {"password":self.meta.password})
        def auth_callback(result):
            if result:
                return credentials.username
            else:
                return Failure(UnauthorizedLogin(credentials.username))
        service.addCallback(auth_callback)
        return service.deferred

class GitServer(SSHFactory):
    authmeta = DrupalMeta()
    portal = Portal(GitRealm(authmeta))
    portal.registerChecker(GitPubKeyChecker(authmeta))
    portal.registerChecker(GitPasswordChecker(authmeta))

    def __init__(self, privkey):
        pubkey = '.'.join((privkey, 'pub'))
        self.privateKeys = {'ssh-rsa': Key.fromFile(privkey)}
        self.publicKeys = {'ssh-rsa': Key.fromFile(pubkey)}

class Server(object):
    def __init__(self):
        self.port = config.getint('drupalSSHGitServer', 'port')
        self.interface = config.get('drupalSSHGitServer', 'host')
        self.key = config.get('drupalSSHGitServer', 'privateKeyLocation')
        components.registerAdapter(GitSession, GitConchUser, ISession)

    def application(self):
        return GitServer(self.key)

if __name__ == '__main__':
    log.startLogging(sys.stderr)
    ssh_server = Server()
    reactor.listenTCP(ssh_server.port, 
                      ssh_server.application(), 
                      interface=ssh_server.interface)
    reactor.run()
