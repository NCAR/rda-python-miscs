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
| `gdexkill` | `rdakill` | `setuid_gdexkill` / `setuid_rdakill` | Kill local processes and their children, or cancel PBS batch jobs |
| `gdexmod` | `rdamod` | `setuid_gdexmod` / `setuid_rdamod` | Change permission modes for files and directories owned by gdexdata |

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

The setuid programs (`gdexcp`, `gdexkill`, `gdexmod` and their `rda*` aliases)
execute as the common user `PGLOG['COMMONUSER']` (default `gdexdata`) via
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
