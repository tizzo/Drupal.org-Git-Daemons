# Drupal.org Git Daemons

This project is a proof of concept and intellectual excercise to demonstrate the use of SSH daemons and beanstalkd to maintain git reposiotries mapped to project module projects.

## BeanstalkD Reposiotry Manager

### Requirements:
- [Beanstalkd](http://kr.github.com/beanstalkd/)
- [Beanstalkc](https://github.com/earl/beanstalkc)
- [Project Git Auth](https://github.com/tizzo/Project-Git-Auth)

To run this Daemon you must have the python 2.6 or higher and have beanstalkc installed.

### Installing beanstalkdRepositoryManager and its dependencdies

#### Install and start beanstalkd

Beanstalk can easily be built from source.  Once you have [beanstalkd](http://kr.github.com/beanstalkd/download.html), start it with the following command:  `[path to your compiled beantaslk]/beanstalkd -l 127.0.0.1 -p 11300`

#### Install beanstalkc

- Ensure that you have easy_install installed (on debian/ubuntu `apt-get install python-dev  python-setuptools`).
- Run `git clone https://github.com/earl/beanstalkc.git`
- Move into the beanstalkc directory `cd beanstalkc`
- Run the installer `python setup.py install`


### Starting the repo manager

Once you have beanstalk started run `./beanstalkdRepositoryManager.py` from inside this repository.

###Install the [Project Git Auth](https://github.com/tizzo/Project-Git-Auth) module

## Drupal Git SSH Daemon

### Requirements:
- [Twisted 10.1.0](http://twistedmatrix.com/trac/wiki/Downloads)
- [Project Git Auth](https://github.com/tizzo/Project-Git-Auth)

### Installing Twisted

- Ensure that you have easy_install installed (on debian/ubuntu `apt-get install python-dev  python-setuptools`).
- Download Twisted 10.1.0 `wget http://tmrc.mit.edu/mirror/twisted/Twisted/10.1/Twisted-10.1.0.tar.bz2`
- Untar Twisted `tar -xvf Twisted-10.1.0.tar.bz2`
- Move into the Twisted directory `cd Twisted-10.1.0`
- Run the Twisted installer `pyton setup.py install`

#### Configure the daemon

Configure the daemon in the drupaldaemons.cnf to properly point to a local directory on your system and at your drupal site where [Project Git Auth](https://github.com/tizzo/Project-Git-Auth) is properly installed.

#### Starting the daemon

From inside this repository, Start the daemon by typing `./drupalGitSSHDaemon.py`
