#!/usr/bin/env python3
#
##################################################################################
#
#     Title: bashqsub
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 11/19/2020
#            2025-03-07 transferred to package rda_python_miscs from
#            https://github.com/NCAR/rda-utility-programs.git
#   Purpose: python script to submit a batch job on PBS node via bash script
#
#    Github: https://github.com/NCAR/rda-pythn-miscs.git
#
##################################################################################

import os
import sys
import re
from os import path as op
from rda_python_common import PgLOG

DEFMODS = {
   'default' : "ncarenv,netcdf,ncl,nco,cdo,conda,grib-util,wgrib2",
}

DEFLIBS = {
   'default' : "conda activate /glade/work/gdexdata/conda-envs/pg-gdex",
}

SWAPMODS = {
}

RESOURCES = {   # resource list for option -l
   'walltime' : '6:00:00',   # if this is changed, change defpbstime in PgCheck.py too
   'select' : '1:ncpus=1:mem=1gb'
}

SOPTIONS = {   # single-dash option values
   'o' : None,    # will set to default if not provided
   'e' : None,
   'A' : "P43713000",
   'q' : "gdex@casper-pbs",
#   'm' : 'a',
   'm' : 'n',
}

#
# main function to excecute this script
#
def main():

   aname = 'bashqsub'
   pname = 'gdexqsub'
   PgLOG.set_help_path(__file__)
   gdexsub = PgLOG.BCHCMDS['PBS']
   coptions = {'cmd' : None, 'cwd' : None, 'env' : None, 'mod' : None, 'res' : 'default'}       # customized options
   copts = '|'.join(coptions)
   option = None
   dcount = 0
   argv = sys.argv[1:]
   if not argv: PgLOG.show_usage(aname)
   PgLOG.PGLOG['LOGFILE'] = pname + ".log"
   PgLOG.cmdlog("{} {}".format(aname, ' '.join(argv)))
   if not PgLOG.valid_command(gdexsub): PgLOG.pglog("{}: miss {} command to submit batch job".format(gdexsub, PgLOG.PGLOG['PBSNAME']), PgLOG.LGWNEX)

   while argv:
      arg = argv.pop(0)
      ms = re.match(r'^-(\w)$', arg)
      if ms:
         option = ms.group(1)
         if option == "b":
            PgLOG.PGLOG['BCKGRND'] = 1
            option = None
         else:
            SOPTIONS[option] = ''
         continue
      ms = re.match(r'^-({})$'.format(copts), arg)
      if ms:
         option = ms.group(1)
         if option == "env": option = 'v'
         continue

      if not option: PgLOG.pglog("{}: Value passed in without leading option for {}".format(arg, gdexsub), PgLOG.LGEREX)
      if arg.find(' ') > -1 and not re.match(r'^[\'\"].*[\'\"]$', arg):   # quote string with space but not quoted yet
         if arg.find("'") > -1:
            arg = '"{}"'.format(arg)
         else:
            arg = "'{}'".format(arg)

      if option in coptions:
         coptions[option] = arg
         if option == "cmd": break
      else:
         SOPTIONS[option] = arg
      option = None

   if not coptions['cmd']: PgLOG.pglog(aname + ": specify command via option -cmd to run", PgLOG.LGWNEX)
   args = PgLOG.argv_to_string(argv, 0)   # append command options
   if not SOPTIONS['o']: SOPTIONS['o'] = "{}/{}/".format(PgLOG.PGLOG['LOGPATH'], pname)
   if not SOPTIONS['e']: SOPTIONS['e'] = "{}/{}/".format(PgLOG.PGLOG['LOGPATH'], pname)
   if 'N' not in SOPTIONS: SOPTIONS['N'] = op.basename(coptions['cmd'])
   msg = "{}-{}{}".format(PgLOG.PGLOG['HOSTNAME'], PgLOG.PGLOG['CURUID'], PgLOG.current_datetime())

   if coptions['cwd']:
      if 's' in coptions['cwd']: coptions['cwd'] = PgLOG.replace_environments(coptions['cwd'], '', PgLOG.LGWNEX)
      msg += "-" + coptions['cwd']
      os.chdir(coptions['cwd'])

   cmd = PgLOG.valid_command(coptions['cmd'])
   if not cmd and not re.match(r'^/', coptions['cmd']): cmd = PgLOG.valid_command('./' + coptions['cmd'])
   if not cmd: PgLOG.pglog(coptions['cmd'] + ": Cannot find given command to run", PgLOG.LGWNEX)
   if args: cmd += " " + args

   sbuf = build_bash_script(cmd, coptions, gdexsub)
   PgLOG.pglog(sbuf, PgLOG.MSGLOG)
   PgLOG.PGLOG['ERR2STD'] = ['bind mouting']
   PgLOG.pgsystem(gdexsub, PgLOG.LOGWRN, 6, sbuf)
   PgLOG.PGLOG['ERR2STD'] = []

   sys.exit(0)

#
# build bash script to submit a PBS batch job
#
def build_bash_script(cmd, coptions, gdexsub):

   buf = "#!/usr/bin/bash\n\n"   # qsub starting bash script

   if 'l' in SOPTIONS: add_resources()
   # add options to bash script for qsub
   for option in SOPTIONS:
      buf += "#PBS -" + option
      if SOPTIONS[option]: buf += " {}".format(SOPTIONS[option])
      buf += "\n"
   for option in RESOURCES:
      buf += "#PBS -l"
      if RESOURCES[option]: buf += " {}={}".format(option, RESOURCES[option])
      buf += "\n"

   # always include the login user's bash resource file
   homedir = "{}/{}".format(PgLOG.PGLOG['USRHOME'], PgLOG.PGLOG['CURUID'])
   buf += "export HOME={}\n".format(homedir)
   buf += "source /etc/profile.d/z00_modules.sh\n"
   buf += "source /glade/u/apps/opt/conda/etc/profile.d/conda.sh\n"
   buf += "source {}/.bashrc\n".format(homedir)
   buf += "pwd; hostname; date\n"
   buf += add_modules(coptions['res'], coptions['mod'])
   buf += set_vm_libs(coptions['res'])
   buf += "\necho {}\n{}\n\ndate\n".format(cmd, cmd)
   
   return buf

#
# check and add resource options 
#
def add_resources():

   for res in re.split(',', SOPTIONS['l']):
      ms = re.match(r'^([^=]+)=(.+)$', res)
      if ms:
         RESOURCES[ms.group(1)] = ms.group(2)
      else:
         PgLOG.pglog(res + ": use '=' to separate resource name & value", PgLOG.LGEREX)
   del SOPTIONS['l']

#
# add module loads for modules provided
#
def add_modules(res, mods):

   mbuf = "\n"
   defmods = DEFMODS[res] if res in DEFMODS else DEFMODS['default']

   dmods = re.split(',', defmods)
   for dmod in dmods:
      ms = re.match(r'^(.+)/', dmod)
      smod = ms.group(1) if ms else dmod
      if smod in SWAPMODS: mbuf += "module unload {}\n".format(SWAPMODS[smod])
      mbuf += "module load {}\n".format(dmod)

   if mods:
      amods = re.split(',', mods)
      for amod in amods:
         if re.match(r'^/', amod):
            mbuf += "module use {}\n".format(amod)
         else:
            ms = re.match(r'^(.+)/', amod)
            smod = ms.group(1) if ms else amod
            if smod in dmods: continue
            if smod in SWAPMODS: mbuf += "module unload {}\n".format(SWAPMODS[smod])
            mbuf += "module load {}\n".format(amod)

   return mbuf

#
# set virtual machine libraries
#
def set_vm_libs(res):

   deflibs = DEFLIBS[res] if res in DEFLIBS else DEFLIBS['default']
   if not deflibs: return ''
   
   dlibs = re.split(',', deflibs)
   libbuf = "\n"
   for dlib in dlibs:
      libbuf += dlib + "\n"

   return libbuf

#
# call main() to start program
#
if __name__ == "__main__": main()
