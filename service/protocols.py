from twisted.conch.error import ConchError
from twisted.internet import reactor, defer
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log
from zope.interface import implements
from service import IServiceProtocol
from config import config

# Load drush settings from drupaldaemons.cnf
drush_webroot = config.get('drush-settings', 'webroot')
drush_path = config.get('drush-settings', 'drushPath')

class DrushError(ConchError):
    pass

class DrushProcessProtocol(ProcessProtocol):
    implements(IServiceProtocol)
    """Read string values from Drush"""
    def __init__(self, command):
        self.raw = ""
        self.raw_error = ""
        self.deferred = defer.Deferred()
        self.command = command

    def outReceived(self, data):
        self.raw += data

    def errReceived(self, data):
        self.raw_error += data

    def outConnectionLost(self):
        self.result = self.raw.strip()

    def processEnded(self, status):
        if self.raw_error:
            log.err("Errors reported from drush:")
            for each in self.raw_error.split("\n"):
                log.err("  " + each)
        rc = status.value.exitCode
        if self.result and rc == 0:
            self.deferred.callback(self)
        else:
            if rc == 0:
                err = DrushError("Failed to read from drush.")
            else:
                err = DrushError("Drush failed ({0})".format(rc))
            self.deferred.errback(err)

    def request(self, *args):
        exec_args = (drush_path, "--root={0}".format(drush_webroot), self.command) + args
        reactor.spawnProcess(self, drush_path, exec_args, env = {"TERM":"dumb"})
        return self.deferred
