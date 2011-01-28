from twisted.conch import interfaces
from twisted.conch.ssh.common import NS, getNS
from twisted.conch.ssh.keys import Key
from twisted.conch.ssh.userauth import SSHUserAuthServer
from twisted.cred import credentials
from twisted.cred.credentials import IUsernamePassword, ISSHPrivateKey
from twisted.cred.portal import Portal
from zope import interface

class IGitSSHPrivateKey(ISSHPrivateKey):
    """Anonymous git user requests..."""
    pass

class GitSSHPrivateKey:
    interface.implements(IGitSSHPrivateKey)
    def __init__(self, username, algName, blob, sigData, signature):
        self.username = username
        self.algName = algName
        self.blob = blob
        self.sigData = sigData
        self.signature = signature

class GitPortal(Portal):
    def login(self, c, mind, interface):
        if c.username == "git":
            # Make git@ users key requests match a different auth interface
            git_cred = GitSSHPrivateKey(c.username, 
                                        c.algName,
                                        c.blob,
                                        c.sigData,
                                        c.signature)
            return Portal.login(self, git_cred, mind, interface)
        else:
            # Do nothing for normal users
            return Portal.login(self, c, mind, interface)
