Nord: an unofficial NordVPN client
==================================

.. badges-start

.. image:: https://img.shields.io/badge/License-GPL%20v3-blue.svg
   :target: https://img.shields.io/badge/License-GPL%20v3-blue.svg
   :alt: GPLv3 License

.. image:: https://badge.fury.io/py/nord.svg
   :target: https://badge.fury.io/py/nord
   :alt: PyPi package

.. image:: https://readthedocs.org/projects/nord/badge/?version=stable
   :target: http://nord.readthedocs.io/en/stable/?badge=stable
   :alt: Documentation Status

.. badges-end
.. doc-start

Overview
--------

.. overview

Nord is a client for interacting with the `NordVPN`_ service.

At its core is a high-level Python API for interacting both with the web service
provided by NordVPN, and for connecting to VPN servers using OpenVPN.

Nord also contains components that expose this API as a command line tool,
and (soon) as a web service and frontend.

.. _NordVPN: https://nordvpn.com

.. overview-end

Licence
-------
Nord is licensed under the terms of the GNU GPLv3.
See the LICENSE_ file for details.

.. _LICENSE: LICENSE

Installation
------------
::

    pip install nord

Usage
-----

Run ``nord --help`` for the full usage instructions.

Connect to a specific NordVPN server::

    nord connect -u my_user -p my_password us893

Connect to any NordVPN server in a given country::

    nord connect -u my_user -p my_password US

You can also supply your password from a file using the ``-f`` flag.
The special value ``-`` means "read from stdin". This is particularly
useful when your password is stored in a utility such as
pass_::

    pass nordvpn_password | nord connect -u my_user -f - us893

.. _pass: https://www.passwordstore.org/

Prerequesites
-------------
- GNU/Linux system
- Python 3.6
- ``openvpn``
- ``sudo``

nord contains many Linux-isms (e.g. using the ``sudo`` program to obtain root
access) so it will certainly not work on Windows, it may possibly work
on OSX and \*BSD, but support for these platforms is not a goal.

Most recent versions of popular GNU/Linux distributions (with the
exception of Debian) have both an OpenVPN client and Python 3.6
in their official repositories. Debian users will have to take
`additional steps`_ to get a Python 3.6 installation.

.. _additional steps: Debian_


Ubuntu 16.10 and newer
**********************
Ubuntu comes with ``sudo`` already installed, so we just need
to install Python and openVPN::

    sudo apt-get install python3.6 openvpn

Fedora 26 and newer
*******************
Fedora comes with ``sudo`` already installed, so we just need
to install Python and openVPN::

    sudo dnf install python36 openvpn

Arch Linux
**********
Run the following as root::

    pacman -S sudo python openvpn

Then configure ``sudo`` by following the `Arch wiki`_
to give privileges to the user that nord will be running as.

.. _Arch wiki: https://wiki.archlinux.org/index.php/sudo

Debian
******
First run the following as root to install the openVPN client and
``sudo`` from the Debian repositories::

    apt install sudo openvpn

Then configure ``sudo`` by following the `Debian wiki`_
to give privileges to the user that nord will be running as.

There are a couple of options for installing Python3.6 on Debian:

- Installing from the ``unstable`` repositories
- Installing from source (easier than you might think

Both of these methods are explained in top-rated answers to this
`stackexchange question`_.

.. _Debian wiki: https://wiki.debian.org/sudo
.. _stackexchange question:  https://unix.stackexchange.com/questions/332641/how-to-install-python-3-6

Developing
----------
::

    git clone https://github.com/jbweston/nord
    cd nord
    virtualenv -p python3.6
    source venv/bin/activate
    pip install -e .[dev]

Building the API documentation
******************************
::

    make -C docs html
    xdg-open docs/build/html/index.html
