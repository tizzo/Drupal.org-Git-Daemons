# Centos 5.5 package
## Requirements:
- python26
- python26-twisted-10.2.0
- pycrypto26-2.3

## Building
    tar cjhf twisted-drupalGitSSHDaemon-0.1.tar.bz2 twisted-drupalGitSSHDaemon-0.1
    # Copy .tar.bz2 to {rpmbuild_topdir}/SOURCES
    # Copy .spec to {rpmbuild_topdir}/SPECS
    rpmbuild -ba twisted-drupalGitSSHDaemon-0.1-1.el5.spec