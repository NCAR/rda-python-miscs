#!/usr/bin/env python3
#
##################################################################################
#
#     Title: miscs-setup
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 2026-05-12
#   Purpose: Display the setuid setup guide for rda_python_miscs after pip install.
#            Run automatically when a setuid_ connector script is invoked directly
#            instead of through the program -> pywrapper setuid symlink.
#
#    Github: https://github.com/NCAR/rda-python-miscs.git
#
##################################################################################

import sys


SETUP_GUIDE = """
 rda_python_miscs - Setuid Setup Guide
 ======================================

 The following programs must run as the common user 'gdexdata' via the
 rda_python_setuid mechanism:

   rdacp / gdexcp    - Copy files and directories as gdexdata
   rdakill / gdexkill - Kill processes or cancel PBS jobs as gdexdata
   rdamod / gdexmod  - Change file permission modes as gdexdata

 rda_python_setuid is installed automatically as a dependency.

 If you are seeing this message after running a setuid_ connector script
 directly, the setuid wrapper has not been set up yet.  Follow the steps below.

 Run 'pywrapper-install' with no arguments for the full pywrapper user guide.

 Environment Setup
 -----------------

   Option A - Python venv (DECS machines):
      python3 -m venv $ENVHOME    # e.g. /glade/u/home/gdexdata/gdexmsenv
      source $ENVHOME/bin/activate
      pip install rda_python_miscs

   Option B - Conda (DAV/Casper):
      conda activate pg-gdex      # e.g. /glade/work/gdexdata/conda-envs/pg-gdex
      pip install rda_python_miscs

 Full Setuid Install (requires sudo access to gdexdata)
 ------------------------------------------------------

   # Compile the pywrapper C binary (once per environment):
   pywrapper-install -c|--compile -n|--username gdexdata

   # Wire up all setuid programs in one pass:
   pywrapper-install -l|--link all

 Simple Install (no sudo required, runs as current user)
 -------------------------------------------------------

   pywrapper-install -l|--link all -s|--simple

   This creates bin/<name> -> bin/setuid_<name> for every setuid program.
   The programs run as the current user with no privilege change.

 Update Existing Installation (no sudo required)
 -----------------------------------------------

   pywrapper-install -u|--update

   Recompiles pywrapper and reinstalls all pgstart_* setuid binaries
   using the existing pgstart_* binaries already in bin/.

"""


def main():
   print(SETUP_GUIDE)
   sys.exit(0)


if __name__ == '__main__': main()
