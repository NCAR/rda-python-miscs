# rda_python_miscs

RDA Python package to hold miscellaneous utility programs for the
[NSF NCAR Geoscience Data Exchange (GDEX)](https://gdex.ucar.edu).

## Programs

The package provides two categories of programs:

**Run as current user (no setuid required):**

| Command | Alias | Description |
|---------|-------|-------------|
| `bashqsub` | | Submit a job as a bash batch job on a PBS node via qsub |
| `tcshqsub` | | Submit a job as a tcsh batch job on a PBS node via qsub |
| `gdexsub` | `rdasub` | Submit a command as a nohup background process on the local machine |
| `pgwget` | | Download remote files by root name pattern, combining downloaded parts into a single file |
| `gdexls` | | List local files and directories with matching metadata from the GDEX database |
| `gdexps` | `rdaps` | Show process status for local or PBS batch processes, with filtering by PID, owner, or name |
| `gdexzip` | `rdazip` | Compress or uncompress files using a supported format |
| `gdexown` | `rdaown` | Change ownership of files and directories to gdexdata (must be run as root) |
| `pgrst` | | Convert .usg files to RST and push to gdex-docs-* repos on GitHub for readthedocs.io |

**Run as gdexdata via setuid (requires setup below):**

| Command | Alias | Connector script | Description |
|---------|-------|-----------------|-------------|
| `gdexcp` | `rdacp` | `setuid_gdexcp` / `setuid_rdacp` | Copy files and directories across local, remote, Object Store, or Globus endpoints |
| `gdexdrop` | | `setuid_gdexdrop` | Copy local files into a GDEX dataset directory as gdexdata, for data providers outside the DECS group |
| `gdexkill` | `rdakill` | `setuid_gdexkill` / `setuid_rdakill` | Kill local processes and their children, or cancel PBS batch jobs |
| `gdexmod` | `rdamod` | `setuid_gdexmod` / `setuid_rdamod` | Change permission modes for files and directories owned by gdexdata |
| `decsdata_storage` | | `setuid_decsdata_storage` | Move decsdata datasets into the GLADE HSM cold storage to migrate them onto tape |
| `decsdata_restore` | | `setuid_decsdata_restore` | Recall decsdata datasets out of the GLADE HSM cold storage and copy them back |

## Environment setup

Create a Python environment first; package installs in the next section run
inside whichever environment you activate here.

### Option A — Python venv (DECS machines)

```bash
python3 -m venv $ENVHOME          # e.g. /glade/u/home/gdexdata/gdexmsenv
source $ENVHOME/bin/activate
```

### Option B — Conda (DAV/Casper)

```bash
conda create --prefix $ENVHOME python=3.12   # e.g. /glade/work/gdexdata/conda-envs/pg-gdex
conda activate $ENVHOME
```

## Installing rda-python-miscs

Pick whichever install mode fits your workflow.  All four pull in the
transitive dependencies (`rda_python_common`, `rda_python_setuid`)
automatically.

For local development, clone this repo alongside your project and install it
in editable mode so that changes are picked up without re-installing:

```bash
git clone https://github.com/NCAR/rda-python-miscs.git
cd rda-python-miscs
pip install -e .
```

To test a specific branch (e.g. an in-progress feature or fix branch), pass
`-b/--branch` to `git clone`:

```bash
git clone -b <branch-name> https://github.com/NCAR/rda-python-miscs.git
cd rda-python-miscs
pip install -e .
```

For a regular (non-editable) install from a checkout:

```bash
pip install /path/to/rda-python-miscs
```

For a production install on a system that uses the published distribution:

```bash
pip install rda_python_miscs
```

## Setuid Setup

The setuid programs (`gdexcp`, `gdexdrop`, `gdexkill`, `gdexmod`, `decsdata_storage`,
`decsdata_restore` and the `rda*` aliases) execute as the common user `PGLOG['COMMONUSER']` (default `gdexdata`) via
the `rda_python_setuid` mechanism, which is pulled in automatically as a
dependency.  After `pip install` above, choose one of the wiring options
below.

> **Note:** If `rda_python_setuid` is already installed and fully set up in
> your environment, you can skip the compile step (`-c/--compile`) and the
> optional `pgstart` step (`-p/--pgstart`).  The `-l/--link` step is still
> required to wire up this package's own setuid programs.

### Full setuid install (requires sudo access to COMMONUSER)

Run these steps once per environment:

```bash
# 1. Compile the pywrapper C binary (once per environment):
pywrapper-install -c|--compile -n|--username gdexdata

# 2. Wire up all setuid programs in one pass:
pywrapper-install -l|--link all

# 3. Optionally, install a pgstart_<loginname> binary so <loginname> (any
#    user in the same group as PGLOG['COMMONUSER']) can run commands as
#    themselves.  Run either by PGLOG['ADMINUSER'] (default zji, if it has
#    'sudo -u <loginname>'), or by <loginname> directly:
pywrapper-install -p|--pgstart -n|--username <loginname>
```

`pywrapper-install` with no arguments displays the full user guide.

### Simple install (no sudo required, runs as current user)

Users who do not need the setuid mechanism can create direct symlinks instead:

```bash
pywrapper-install -l|--link all -s|--simple
```

This creates `bin/<name> -> bin/setuid_<name>` for every setuid program and
they run as the current user with no privilege change.

### Update an existing installation (no sudo required)

When the package is upgraded and a new `pywrapper.c` is bundled, recompile and
reinstall all setuid binaries using the existing `pgstart_*` binaries:

```bash
pywrapper-install -u|--update
```

### Setup guide

The shared setuid setup guide is shown automatically if any `setuid_*`
connector script is invoked directly before the setuid wrapper has been
configured.

## gdexdrop access list

`gdexdrop` lets data providers who are **not** in the DECS group copy files into
a dataset directory so that the result is owned by `gdexdata`.  It is a
deliberately narrow alternative to `gdexcp`: the destination is always
`/glade/campaign/collections/gdex/data/<dsid>`, a path that escapes the dataset
directory is rejected, and every source must be readable by the calling user
rather than only by `gdexdata`.

An absolute `-t` under `/tmp/` names any sub-path of `/tmp` instead of a sub-path
of the dataset directory, so that a drop can be tried out without touching the
dataset tree.  The dataset of `-ds` is still checked against the access list, and
because `/tmp` is world writable — unlike a dataset directory — the part of the
path that already exists must belong to the calling user or to `gdexdata`.

Everything dropped, including sub-directories created for `-t`, is also set to the
GDEX group `PGLOG['GDEXGRP']`.  The setuid wrapper switches only the user to
`gdexdata`, not the group, so without that step a dropped file would stay in the
calling user's group unless the directory it landed in carried the setgid bit.

Who may drop into which dataset is read from the access list
`/glade/u/home/gdexdata/config/gdexdrop.conf`.  It must be owned by `gdexdata`
and must not be writable by group or others, otherwise `gdexdrop` refuses to
run.  Each line is a login name, a colon, and the colon-separated dataset IDs
that login may drop into, or `all` for every dataset; `#` starts a comment:

```
# login: dsid1[:...:dsidn]
jdoe: d123456:d654321
asmith: d111222
gdexhelp: all
```

The root path, the access list path and the log path are compiled into the
program rather than taken from `PGLOG`, because `PGLOG['DSDHOME']`,
`PGLOG['DSSHOME']` and `PGLOG['LOGPATH']` are all settable from environment
variables of the same name, which the caller controls.

## Cold storage setup

`decsdata_storage` and `decsdata_restore` drive the GLADE HSM through the
`glade_hsm` script, which is not part of this package.  They look it up at
`~benkirk/glade_hsm` unless the environment variable `GLADE_HSM` names another
copy of it:

```bash
export GLADE_HSM=/path/to/glade_hsm
```

Both programs work on the decsdata directory `PGLOG['DECSHOME']` (default
`/glade/campaign/collections/gdex/decsdata`, also reachable as
`/gdex/decsdata`), which option `-w` overrides.  Only members of the DECS group
may run them, and `decsdata_restore` reads Table `sfile` in RDADB to size a
restore, so a working RDADB login is required as well.

Because the decsdata quota is limited, check the space left with `gladequota`
before a large restore:

```bash
pgstart_gdexdata gladequota    # or plain 'gladequota' when logged in as gdexdata
```

`decsdata_restore -x` runs the same check itself and refuses to request a
recall unless twice the size of the data is still available.
