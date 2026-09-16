# osmo-dev

## Overview

The main purpose of this project is building the Osmocom stack (and related
projects such as Open5GS) from source with a top-level Makefile produced by
`gen_makefile.py`. This is described in more detail below.

### Additional scripts

* `net/`: quickly configure, launch and tear down an entire Osmocom core network
  on your box (see `net/README`).

* `ttcn3/tmux`: start a tmux session with a TTCN-3 testsuite and related
  binaries (see `ttcn3/tmux/README.md`).

* `src/`: scripts to sync local git clones with upstream gerrit (see `src/README`).

* `osmo-uninstall.sh`: remove installed binaries, libraries and headers from a
  given prefix, the default is `/usr/local`.

## `gen_makefile.py`

This script generates a `Makefile` that was originally intended to build the
Osmocom core network components, but has since been extended to also build
Open5GS, PyHSS and more. See `all.deps` for a list of supported projects.

The idea is to have all your git clones in `./src`, while keeping one or more
separate build trees in `./make*` dirs.

`gen_makefile.py` gets used by
[`testenv.py`](https://gitea.osmocom.org/ttcn3/osmo-ttcn3-hacks/src/branch/master/_testenv/README.md)
in `osmo-ttcn3-hacks.git` to build projects from source when running without
the `--binary-repo` argument.

### Dependencies

Install required packages first. To have enough dependencies for building and
installing most Osmocom programs, you can run this on Debian-based systems:

```
$ sudo apt install \
  build-essential gcc g++ make automake autoconf libtool pkg-config \
  libtalloc-dev libpcsclite-dev libortp-dev libsctp-dev libssl-dev libdbi-dev \
  libdbd-sqlite3 libsqlite3-dev libpcap-dev libc-ares-dev libgnutls28-dev \
  libsctp-dev sqlite3 libusb-1.0-0-dev libmnl-dev libsofia-sip-ua-glib-dev
```

### Example usage

Build the Osmocom core network with full 2G and 3G support:

```
$ ./gen_makefile.py default.opts iu.opts no_dahdi.opts no_systemd.opts -I -m make
$ cd make
$ make cn
```

If you make modifications in one of the source trees, this `Makefile` will pick
it up, rebuild the project and also rebuild all dependencies (according to
`all.deps`). It is also easily possible to keep sources and build trees in
various configurations, see the command line options of `gen_makefile.py`.

### Make targets

Single projects can be built by name. The following example builds only
libosmo-abis, and its dependencies libosmocore and libosmo-netif:

```
make libosmo-abis
```
This can be used for any project in `all.deps`, e.g. `make osmo-msc`,
`make osmo-bsc` etc.

Top-level make targets exist for specific use cases:

* `cn`: core network components: OsmoMSC, OsmoSGSN, osmo-iuh, OsmoGGSN, OsmoHLR, OsmoMGW,
  OsmoSIPConnector, OsmoSMLC, including all of their dependencies.

* `usrp`:
  Build the CN, OsmoBSC, OsmoBTS and OsmoTRX (default, e.g. when connecting
  to an USRP)

* `cn-bsc`:
  Build the CN and OsmoBSC (e.g. when connecting to an external sysmoBTS)

* `.make.osmo-ttcn3-hacks.clone`:
  Clone the osmo-ttcn3-hacks git repository (it cannot be built by osmo-dev,
  but cloning it is still useful.)

* You will find many other (hidden) `.make.*` files in your `make*/` dir.
  These control the top-level Makefile: removing a file makes sure that the
  given step is rebuilt, including all of its dependencies.
  For example, if you `rm .make.libosmocore.autoconf`, libosmocore and all
  projects depending on libosmocore will be rebuilt from scratch.

### Modify configuration

If you modify the `all.deps` or `*.opts` file, update your `make*` subdir with:

```
make regen
```

This keeps the options intact that were first passed to `gen_makefile.py`.
(They are listed near the top of the generated `make*/Makefile`, convenient to
edit.)

### Configuration files

### all.deps

Whitespace-separated listing of:

```
project_name depends_on_project_1 depends_on_project_2 ...
```

### all.urls

Projects that are not developed at `gerrit.osmocom.org/$project` are listed
here in the following format:

```
project_name    URL
```

### all.buildsystems

Projects that are not using `autotools` need an entry in this file in the
form of:

```
project_name    BUILDSYSTEM
```

Supported buildsystems are:
* `autotools`
* `cmake`
* `erlang`
* `meson`
* `python`

#### `*.opts` files

The `*.opts` files provide options that are passed to `./configure`,
`meson setup` and `cmake`. They have the following format:

```
project_name    OPTION(S)
```

Options can be added to all `./configure` steps of builds that use `autotools`
using the `ALL` keyword, for example:

```
ALL --prefix=/usr
```

(Note that `./configure` just ignores any options it does not understand.)

Find more information about specific `*.opts` files below.

##### `prefix_usr.opts`

By default, the Osmocom install prefix is `/usr/local`, while the systemd
`*.service` files expect binaries installed in `/usr/bin`. To install to `/usr`
instead, it is possible to add `prefix_usr.opts` to the `gen_makefile.py`
arguments, which sets `--prefix=/usr`. Be aware that this will cause problems
with distribution packages.

##### `no_systemd.opts`

`no_systemd.opts` disables installing `*.service` files, which is useful
because these files get installed to `/usr/lib/systemd/system` even if the
prefix is not `/usr`. Using `no_systemd.opts` is required for running
`gen_makefile.py` without the `-I` (`--sudo-make-install`) argument.

### Run without sudo prompts

`make` will ask for the sudo password to run `make install` and `ldconfig`. To
run non-interactively:

```
$ sudo chown -R $USER: /usr/local
$ echo "$USER  ALL= NOPASSWD: $(command -v ldconfig)" | sudo tee /etc/sudoers.d/ldconfig
```

Then call `gen_makefile.py` once without `-I` (`--sudo-make-install`).

## Troubleshooting

### Environment variables

If your system can't find installed libraries (e.g. if you run
`gen_makefile.py` with `--no-ldconfig`), pkg-config files or binaries then
setting these environment variables should help:

```
export LD_LIBRARY_PATH="/usr/local/lib"
export PKG_CONFIG_PATH="/usr/local/lib/pkgconfig"
export PATH="$PATH:/usr/local/bin"
```

WARNING: setting `LD_LIBRARY_PATH` can have adverse effects.

### sanitize.opts and osmo-trx

osmo-trx is never built with the address sanitizer enabled. If you intend to
build osmo-trx, you should not use sanitize.opts, because linking a
sanitizer-enabled libosmocore will not work.
