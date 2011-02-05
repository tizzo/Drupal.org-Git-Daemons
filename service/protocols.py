from base64 import b64encode
from config import config
from service import IServiceProtocol
from twisted.conch.error import ConchError
from twisted.internet import reactor, defer
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log
from twisted.web.client import getPage
from twisted.web.error import Error
import urllib, urlparse
from zope.interface import implements

auth_protocol = config.get('drupalSSHGitServer', 'authServiceProtocol')
if auth_protocol == "drush":
    # Load drush settings from drupaldaemons.cnf
    drush_webroot = config.get('drush-settings', 'webroot')
    drush_path = config.get('drush-settings', 'drushPath')
elif auth_protocol == "http":
    # Load http settings
    http_service_url = config.get('http-settings', 'serviceUrl')
    http_host_header = config.get('http-settings', 'hostHeader')
    http_auth = b64encode(config.get('http-settings', 'httpAuth'))
    http_headers = {"Host":http_host_header, "Authorization":"Basic " + http_auth}
else:
    raise Exception("No valid authServiceProtocol specified.")

class DrushError(ConchError):
    pass

class HTTPError(ConchError):
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
            self.deferred.callback(self.result)
        else:
            if rc == 0:
                err = DrushError("Failed to read from drush.")
            else:
                err = DrushError("Drush failed ({0})".format(rc))
            self.deferred.errback(err)

    def request(self, *args):
        exec_args = [drush_path, 
                     "--root={0}".format(drush_webroot), 
                     self.command]
        for a in args:
            exec_args += a.values()
        reactor.spawnProcess(self, drush_path, exec_args, env={"TERM":"dumb"})
        return self.deferred

class HTTPServiceProtocol(object):
    implements(IServiceProtocol)
    def __init__(self, url):
        self.deferred = None
        self.command = url

    def http_request_error(self, fail):
        fail.trap(Error)
        raise HTTPError("Could not open URL for {0}.".format(self.command))

    def request(self, *args):
        arguments = dict()
        for a in args:
            arguments.update(a)
        url_arguments = self.command + "?" + urllib.urlencode(arguments)
        constructed_url = urlparse.urljoin(http_service_url, url_arguments)
        self.deferred = getPage(constructed_url, headers=http_headers)
        self.deferred.addErrback(self.http_request_error)


if auth_protocol == "drush":
    AuthProtocol = DrushProcessProtocol
elif auth_protocol == "http":
    AuthProtocol = HTTPServiceProtocol
