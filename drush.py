from twisted.internet import reactor, defer
from twisted.internet.protocol import ProcessProtocol
import json
from config import config

# Load drush settings from drupaldaemons.cnf
webroot = config.get('drush-settings', 'webroot')
drush_path = config.get('drush-settings', 'drushPath')

class DrushProcessProtocol(ProcessProtocol):
    """Read string values from Drush"""
    def __init__(self, command):
        self.raw = ""
        self.deferred = defer.Deferred()
        self.command = command

    def outReceived(self, data):
        self.raw += data

    def outConnectionLost(self):
        self.data = self.raw.strip()

    def processEnded(self, status):
        rc = status.value.exitCode
        if rc == 0:
            self.deferred.callback(self)
        else:
            self.deferred.errback(rc)

    def call(self, *args):
        exec_args = (drush_path, "--root={0}".format(webroot), self.command) + args
        reactor.spawnProcess(self, drush_path, exec_args)
        return self.deferred

class DrushProcessProtocolJSON(DrushProcessProtocol):
    """Read JSON values from Drush."""
    def outConnectionLost(self):
        self.data = json.loads(self.raw)
