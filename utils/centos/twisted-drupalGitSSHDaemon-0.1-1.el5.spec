%{!?python_sitelib: %define python_sitelib %(%{__python}26 -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}

Summary:    A TCP server for drupalGitSSHDaemon
Name:       twisted-drupalGitSSHDaemon
Version:    0.1
Release:    1
License:    Unknown
Group:      Networking/Daemons
Source:     twisted-drupalGitSSHDaemon-%{version}.tar.bz2
BuildRoot:  %{_tmppath}/%{name}-%{version}-root
Requires:   python26-twisted
BuildArch:  noarch

%description
Patched from the "automatically created by tap2rpm" rpm

%prep
%setup
%build

%install
[ ! -z "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != '/' ] 		&& rm -rf "$RPM_BUILD_ROOT"
mkdir -p "$RPM_BUILD_ROOT"/etc/twisted-taps
mkdir -p "$RPM_BUILD_ROOT"/etc/init.d
mkdir -p "$RPM_BUILD_ROOT"/var/lib/twisted-taps
mkdir -p "$RPM_BUILD_ROOT"%{python_sitelib}
mkdir -p "$RPM_BUILD_ROOT"/etc/twisted-keys
cp "drupaldaemons.cnf.default" "$RPM_BUILD_ROOT"/etc/drupaldaemons.cnf
cp "drupalGitSSHDaemon.py" "$RPM_BUILD_ROOT"%{python_sitelib}
cp "drupalGitSSHDaemon.tac" "$RPM_BUILD_ROOT"/etc/twisted-taps/
cp "twisted-drupalGitSSHDaemon.init" "$RPM_BUILD_ROOT"/etc/init.d/"twisted-drupalGitSSHDaemon"

%clean
[ ! -z "$RPM_BUILD_ROOT" -a "$RPM_BUILD_ROOT" != '/' ] 		&& rm -rf "$RPM_BUILD_ROOT"

%post
/usr/bin/ssh-keygen -t rsa -f /etc/twisted-keys/default -P ""
/sbin/chkconfig --add twisted-drupalGitSSHDaemon
/sbin/chkconfig --level 35 twisted-drupalGitSSHDaemon
/etc/init.d/twisted-drupalGitSSHDaemon start

%preun
/etc/init.d/twisted-drupalGitSSHDaemon stop
/sbin/chkconfig --del twisted-drupalGitSSHDaemon

%files
%defattr(-,root,root)
%attr(0755,root,root) /etc/init.d/twisted-drupalGitSSHDaemon
%attr(0660,root,root) /etc/twisted-taps/drupalGitSSHDaemon.tac
%attr(0660,root,root) /etc/drupaldaemons.cnf
%attr(0660,root,root) %{python_sitelib}/drupalGitSSHDaemon.py
%attr(0660,root,root) /etc/twisted-keys

%changelog
* Sun Jan 09 2011 Trevor Hardcastle <chizu@spicious.com>
- Created by tap2rpm: twisted-drupalGitSSHDaemon (0.1)
