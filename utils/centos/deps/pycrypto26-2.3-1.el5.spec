%define name pycrypto26
%define realname pycrypto
%define version 2.3
%define unmangled_version 2.3
%define release 1

Summary: Cryptographic modules for Python.
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{realname}-%{unmangled_version}.tar.gz
License: UNKNOWN
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
Vendor: Dwayne C. Litzenberger <dlitz@dlitz.net>
Url: http://www.pycrypto.org/

%description
UNKNOWN

%prep
%setup -n %{realname}-%{unmangled_version}

%build
env CFLAGS="$RPM_OPT_FLAGS" python26 setup.py build

%install
python26 setup.py install -O1 --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
