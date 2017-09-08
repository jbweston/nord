Nord: NordVPN client
====================

**This package is a work in progress -- it is not in a usable state***

## Overview
Nord is a client for interacting with the [NordVPN](https://nordvpn.com)
service. At its core is a high-level Python API that supports operations such
as connecting to the server in a given country that is most likely to give you
the best performance. Nord also contains components that expose this API as a
command line tool, and as a web service and a frontend.

## Licence
Nord is licensed under the terms of the GNU GPLv3.
See the [LICENSE](LICENSE) file for details.

## Prerequesites
+ GNU/Linux system
+ `openvpn`
+ `sudo`
+ Python 3.6

nord contains many Linux-isms (e.g. using the `sudo` program to obtain root
access) so it will certainly not work on Windows, it may possibly work
on OSX and *BSD, but support for these platforms is not a goal.

Most recent versions of popular GNU/Linux distributions (with the
exception of Debian) have both an OpenVPN client and Python 3.6
in their official repositories. Debian users will have to take
[additional steps](Debian) to get a Python 3.6 installation.


### Ubuntu 16.10 and newer
Ubuntu comes with `sudo` already installed, so we just need
to install Python and openVPN:
```
sudo apt-get install python3.6 openvpn
```

### Fedora 26 and newer
Fedora comes with `sudo` already installed, so we just need
to install Python and openVPN:
```
sudo dnf install python36 openvpn
```

### Arch Linux
Run the following as root:
```
pacman -S sudo python openvpn
```
Then configure `sudo` by following the [Arch wiki](https://wiki.archlinux.org/index.php/sudo)
to give privileges to the user that nord will be running as.

### Debian
First run the following as root to install the openVPN client and
`sudo` from the Debian repositories:
```
apt install sudo openvpn
```
Then configure `sudo` by following the [Debian wiki](https://wiki.debian.org/sudo)
to give privileges to the user that nord will be running as.

There are a couple of options for installing Python3.6 on Debian:

+ Installing from the `unstable` repositories
+ Installing from source (easier than you might think

Both of these methods are explained in top-rated answers to this
[stackexchange question](https://unix.stackexchange.com/questions/332641/how-to-install-python-3-6).


## Installing
```
pip install nord
```

## Developing
```
git clone https://github.com/jbweston/nord
cd nord
pip install -e .[dev]
```
