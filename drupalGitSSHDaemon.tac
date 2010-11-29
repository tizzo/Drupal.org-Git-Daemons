# You can run this .tac file directly with:
#    twistd -ny drupalGitSSHDaemon.tac

import os
import drupalGitSSHDaemon
from twisted.application import service, internet
from twisted.web import static, server

def getSSHService():
    ssh_server = drupalGitSSHDaemon.Server()
    return internet.TCPServer(ssh_server.port, ssh_server.application())

# this is the core part of any tac file, the creation of the root-level
# application object
application = service.Application("Drupal SSH Git Server")

# attach the service to its parent application
service = getSSHService()
service.setServiceParent(application)
