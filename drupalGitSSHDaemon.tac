#!/usr/bin/twistd -ny
# You can run this .tac file directly with:
#    twistd -ny drupalGitSSHDaemon.tac

import os
import drupalGitSSHDaemon
from twisted.application import service, internet
from twisted.python.log import ILogObserver, FileLogObserver
from twisted.python.logfile import DailyLogFile

def getSSHService():
    ssh_server = drupalGitSSHDaemon.Server()
    return internet.TCPServer(ssh_server.port, ssh_server.application())

# this is the core part of any tac file, the creation of the root-level
# application object
application = service.Application("Drupal SSH Git Server")
logfile = DailyLogFile("gitssh.log", "/var/log")
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

# attach the service to its parent application
service = getSSHService()
service.setServiceParent(application)
