%define name python26-twisted
%define version 10.2.0
%define release 1

%{!?python_sitelib: %define python_sitelib %(%{__python}26 -c "from distutils.sysconfig import get_python_lib; print get_python_lib(1)")}

Summary: Event-based framework for internet applications
Name: %{name}
Version: %{version}
Release: %{release}
Source0: Twisted-%{version}.tar.bz2
License: MIT
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: x86_64
Vendor: Your Name
Url: http://twistedmatrix.com/
BuildRequires: python26-devel
Requires: python26
Requires: python26-zope.interface
Requires: pycrypto26
Obsoletes: python26-twisted-core

%description
See summary.

%prep
%setup -q -c

%build
cd Twisted-%{version}
%{__python}26 setup.py build

%install
cd Twisted-%{version}
%{__python}26 setup.py install --root=$RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root)
%{python_sitelib}/Twisted-%{version}-py2.6.egg-info
%{python_sitelib}/twisted
%{_bindir}
