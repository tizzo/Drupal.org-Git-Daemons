import sys
import ConfigParser

def configure():
    config = ConfigParser.SafeConfigParser()
    try:
        config.readfp(open(sys.path[0] + '/drupaldaemons.cnf'))
    except IOError:
        config.readfp(open("/etc/drupaldaemons.cnf"))
    return config

config = configure()
