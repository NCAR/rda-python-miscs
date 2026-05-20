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
| `rdasub` | `gdexsub` | Submit a command as a nohup background process on the local machine |
| `pgwget` | | Download remote files by root name pattern, combining downloaded parts into a single file |
| `gdexls` | | List local files and directories with matching metadata from the GDEX database |
| `rdaps` | `gdexps` | Show process status for local or PBS batch processes, with filtering by PID, owner, or name |
| `rdazip` | `gdexzip` | Compress or uncompress files using a supported format |
| `rdaown` | `gdexown` | Change ownership of files and directories to rdadata (must be run as root) |
| `pgrst` | | Convert .usg files to RST and push to gdex-docs-* repos on GitHub for readthedocs.io |

**Run as gdexdata via setuid (requires setup below):**

| Command | Alias | Connector script | Description |
|---------|-------|-----------------|-------------|
| `rdacp` | `gdexcp` | `setuid_rdacp` / `setuid_gdexcp` | Copy files and directories across local, remote, Object Store, or Globus endpoints |
| `rdakill` | `gdexkill` | `setuid_rdakill` / `setuid_gdexkill` | Kill local processes and their children, or cancel PBS batch jobs |
| `rdamod` | `gdexmod` | `setuid_rdamod` / `setuid_gdexmod` | Change permission modes for files and directories owned by rdadata |

## Installing rda-python-common

For local development, clone this repo alongside your project and install it
in editable mode so that changes are picked up without re-installing:

```bash
git clone https://github.com/NCAR/rda-python-common.git
cd rda-python-common
pip install -e .
```

For a regular (non-editable) install from a checkout:

```bash
pip install /path/to/rda-python-common
```

For a production install on a system that uses the published distribution:

```bash
pip install rda_python_common
```

The package brings in its own transitive dependencies (`psycopg2-binary`,
`rda-python-globus`, `unidecode`, `hvac`).

## Setuid Setup

The setuid programs (`rdacp`, `rdakill`, `rdamod` and their `gdex*` aliases)
execute as the common user `gdexdata` via the `rda_python_setuid` mechanism.
`rda_python_setuid` is declared as a dependency and installed automatically
with this package.

### Environment setup

#### Option A — Python venv (DECS machines)

```bash
python3 -m venv $ENVHOME          # e.g. /glade/u/home/gdexdata/gdexmsenv
source $ENVHOME/bin/activate
pip install rda_python_miscs
```

#### Option B — Conda (DAV/Casper)

```bash
conda activate pg-gdex            # e.g. /glade/work/gdexdata/conda-envs/pg-gdex
pip install rda_python_miscs
```

### Full setuid install (requires sudo access to gdexdata)

Run these steps once per environment after `pip install`:

```bash
# Compile the pywrapper C binary (once per environment):
pywrapper-install -c|--compile -n|--username gdexdata

# Wire up all setuid programs in one pass:
pywrapper-install -l|--link all
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

After `pip install`, run `miscs-setup` at any time to display the setup guide:

```bash
miscs-setup
```

The guide is also shown automatically if any `setuid_*` connector script is
invoked directly before the setuid wrapper has been configured.
