# IDAConnect

## Overview

IDAConnect is a collaborative reverse engineering plugin for [IDA Pro](https://www.hex-rays.com/products/ida/) and [Hex-Rays](https://www.hex-rays.com/products/decompiler/index.shtml). It allows to synchronize in real-time the changes made to a database by multiple users, by connecting together different instances of IDA Pro.

The main features of IDAConnect are:
* live recording and replaying of all user interactions;
* loading and saving of IDA databases to a central server;
* interactive IDA status bar widget and custom dialogs;
* Python plugin and server with no extra dependencies;
* and even more to come...

If you have any questions not worthy of a bug report, feel free to ping us at [#idaconnect on freenode](https://kiwiirc.com/client/irc.freenode.net/idaconnect) and ask away.

## Releases

This project is under active development. Feel free to send a PR if you would like to help! :-)

**It is not really stable in its current state, please stayed tuned for a first release of the project!**

## Installation

Install the IDAConnect client into the IDA plugins folder.

- Copy `idaconnect_plugin.py` and the `idaconnect` folder to the IDA plugins folder.
    - On Windows, the folder is at `C:\Program Files\IDA 7.0\plugins`
    - On macOS, the folder is at `/Applications/IDA\ Pro\ 7.0/idaq.app/Contents/MacOS/plugins`
    - On Linux, the folder may be at `/opt/IDA/plugins/`
- Alternatively, you can use the "easy install" method by copying the following line into the console of an IDA Pro instance running with administrator privilege (to be able to write the program files directory):
```
import urllib2; exec urllib2.urlopen('https://raw.githubusercontent.com/IDAConnect/IDAConnect/master/easy_install.py').read()
```

**Warning:** The plugin is only compatible with IDA Pro 7.0 on Windows, macOS, and Linux.

The dedicated server requires PyQt5, which is integrated into IDA. If you're using an external Python installation, we recommand using Python 3, which offers a pre-built package that can be installed with a simple `pip install PyQt5`.

## Usage

IDAConnect loads automatically when IDA is opened, installing new elements into the user interface.

First use the widget in the status bar to add the server of your choice in the *Network Settings*. Then connect to the server using the widget again. Finally, you should be able to access the following menus:

```
- File --> Open from server
- File --> Save to server
```

# Thanks

This project is inspired by [Sol[IDA]rity](https://solidarity.re/). It started after contacting its authors and asking if it was ever going to be released to the public. [Lighthouse](https://github.com/gaasedelen/lighthouse) source code was also carefully studied to understand how to write better IDA plugins.

* Previous plugins, namely [CollabREate](https://github.com/cseagle/collabREate), [IDASynergy](https://github.com/CubicaLabs/IDASynergy), [YaCo](https://github.com/DGA-MI-SSI/YaCo), were studied during the development process;
* The icons are edited and combined versions from the sites [freeiconshop.com](http://freeiconshop.com/) and [www.iconsplace.com](http://www.iconsplace.com).

Thanks to Quarkslab for allowing this release.

# Authors

* Alexandre Adamski <<aadamski@quarkslab.com>>
* Joffrey Guilbon <<jguilbon@quarkslab.com>>
