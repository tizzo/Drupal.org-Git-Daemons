# Drupal.org Git Daemons

This project is a proof of concept and intellectual excercise to demonstrate the use of SSH daemons and beanstalkd to maintain git reposiotries mapped to project module projects.

To use this module properly

## BeanstalkD Reposiotry Manager

### Requirements:
- [Beanstalkd](http://kr.github.com/beanstalkd/)
- [Beanstalkc](https://github.com/earl/beanstalkc)
- [Project Git Auth](https://github.com/tizzo/Project-Git-Auth)

To run this Daemon you must have the python 2.6 or higher and have beanstalkc installed.

### Installing beanstalkdRepositoryManager and its dependencdies

#### Install and start beanstalkd
[Install beanstalkd](http://kr.github.com/beanstalkd/download.html) and then start it with the following command:  `[path to your compiled beantaslk]/beanstalkd -l 127.0.0.1 -p 11300`

#### Install beanstalkc

### Starting the repo manager

Once you have beanstalk `beanstalkdRepositoryManager.py`

###Install the [Project Git Auth](https://github.com/tizzo/Project-Git-Auth) module

## Drupal Git SSH Daemon

### Requirements:
- [twisted 10.1.0](http://twistedmatrix.com/trac/wiki/Downloads)
- [Project Git Auth](https://github.com/tizzo/Project-Git-Auth)


#### Configure the daemon

Configure the daemon in the drupaldaemons.cnf to properly point to a local directory on your system and at your drupal site where [Project Git Auth](https://github.com/tizzo/Project-Git-Auth) is properly installed.

#### Starting the daemon

Start the daemon by typing `./drupalGitSSHDaemon.py`


