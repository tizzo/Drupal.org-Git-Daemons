# Drupal.org Git Daemons

This project is a proof of concept and intellectual excercise to demonstrate the use of SSH daemons and beanstalkd to maintain git repositories mapped to project module projects.

## Drupal Git SSH Daemon

### Requirements:
- [Twisted 10.1.0](http://twistedmatrix.com/trac/wiki/Downloads)
- [Versioncontrol Git](http://drupal.org/project/versioncontrol_git) (and all dependencies)
- [Versioncontrol Project](http://drupal.org/project/versioncontrol_project) (and all dependencies)
- [Drush](http://drupal.org/project/drush)

### Installing Twisted

All install instructions are Ubuntu / Debian focused.

- On Ubuntu, `apt-get install python-twisted`

### Upgrading Twisted

- Ensure that you have easy_install installed (on debian/ubuntu `apt-get install python-dev  python-setuptools`).
- Download Twisted 10.1.0 `wget http://tmrc.mit.edu/mirror/twisted/Twisted/10.1/Twisted-10.1.0.tar.bz2`
- Untar Twisted `tar -xvf Twisted-10.1.0.tar.bz2`
- Move into the Twisted directory `cd Twisted-10.1.0`
- Run the Twisted installer `pyton setup.py install`

#### Configure the daemon

- Copy and configure the configuration file `cp drupaldaemons.cnf.default /etc/drupaldaemons.cnf`
- Configure the daemon in the drupaldaemons.cnf to properly point to a local directory on your system and at your drupal site where [Project Git Auth](https://github.com/tizzo/Project-Git-Auth) is properly installed.

#### Starting the daemon

For testing, the daemon can be started by moving into the root of this repository and typing `./drupalGitSSHDaemon.py`

For a proper deployment, twistd should be used to run the daemon.  If you have installed twisted via packages for your ditribution, you should have one init.d script that manages all of your twisted services.  All you have to do is add the following line to the twistd configuration (usually located in `/etc/conf.d/twistd`).  Replace [uid] and [gid] with the user and group you would like to use to run the daemon and replace the path with the path where you checked out this repository.  Don't forget to ensure that the user and group you are using have write access to the folder you specified in your config file.

`TWISTD_OPTS="--uid [uid] --gid [gid] -y /usr/local/bin/Drupal.org-Git-Daemons/drupalGitSSHDaemon.tac"`

Next, run `sudo /etc/init.d/twistd restart`

------------------------------------------------------

## BeanstalkD Repository Manager

The former beanstalkd repository manager has been deprecated in favor of the [Versioncontrol Git Repository Module](http://drupalcode.org/viewvc/drupal/contributions/modules/versioncontrol_git/versioncontrol_git_repo_manager/?pathrev=DRUPAL-6--2) now included in the [VersionControl Git Backend](http://drupal.org/project/versioncontrol_git).
