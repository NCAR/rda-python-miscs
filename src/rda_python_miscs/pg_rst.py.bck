#
###############################################################################
#
#     Title : pg_rst.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/17/2026
#   Purpose : python class to convert text help documents into
#             reStructuredText (RST) format with help of rst templates
#
# Work File : $DSSHOME/lib/python/pg_rst.py
#    Github : https://github.com/NCAR/rda-shared-libraries.git
#
###############################################################################
import os
import re
from os import path as op
from rda_python_common.pg_file import PgFile
from rda_python_common.pg_util import PgUtil

class PgRST(PgFile, PgUtil):
    def __init__(self):
        super().__init__()
        self.OPTS = {}
        self.ALIAS = {}
        self.sections = []
        self.options = {}
        self.examples = []
        cwd = os.getcwd()
        self.DOCS = {
            'ORIGIN': cwd,
            'DCROOT': cwd,
            'DOCDIR': "",
            'DOCNAM': "",
            'DOCTIT': "",
            'DOCLNK': None,
        }
        self.LINKS = ['dsarch', 'dsupdt', 'dsrqst', 'dscheck']

    def parse_docs(self, docname):
        docfile = f"{self.DOCS['ORIGIN']}/{docname}.usg"
        self.pglog(f"Parsing info for Document '{docname}'", self.LOGWRN)
        section = self.init_section('0', "Preface")
        option = example = None
        with open(docfile, 'r') as fh:
            for line in fh:
                if re.match(r'\s*#', line):
                    continue
                ms = re.match(r'^(.*\S)\s+#', line)
                if ms:
                    line = ms.group(1)
                else:
                    line = line.rstrip()
                while True:
                    ms = re.search(r'(<([A-Z/\-\.]+)>)', line)
                    if ms:
                        line = line.replace(ms.group(1), f"&lt{ms.group(2)}&gt")
                    else:
                        break
                ms = re.match(r'^([\d\.]+)\s+(.+)$', line)
                if ms:
                    section = self.record_section(section, option, example, ms.group(1), ms.group(2))
                    option = example = None
                else:
                    ms = re.match(r'^  -([A-Z]{2}) or -\w+(.*)$', line)
                    if ms:
                        option = self.record_option(section, option, example, ms.group(1), ms.group(2))
                        example = None
                    elif option:
                        ms = re.match(r'^  For( | another )example, (.*)$', line)
                        if ms:
                            example = self.record_example(option, example, ms.group(2))
                        elif example:
                            example['desc'] += line + "\n"
                        else:
                            option['desc'] += line + "\n"
                    else:
                        section['desc'] += line + "\n"
        self.record_section(section, option, example)
        for opt in self.OPTS:
            if opt not in self.options:
                self.pglog(f"Missing option Entry -{opt} (-{self.OPTS[opt][1]}) in Document '{docname}'", self.LOGWRN)
        if self.sections:
            cnt = len(self.sections)
            s = 's' if cnt > 1 else ''
            self.pglog(f"{cnt} Section{s} gathered for '{docname}'", self.LOGWRN)

    def record_section(self, section, option, example, nsecid=None, ntitle=None):
        if option or section['desc'] != "\n":
            if option: self.record_option(section, option)
            self.sections.append(section)
        if nsecid: return self.init_section(nsecid, ntitle)

    def record_option(self, section, option, example, nopt=None, ndesc=None):
        if option:
            if example: self.record_example(option, example)
            self.options[option['opt']] = option
            section['opts'].append(option['opt'])
        if nopt: return self.init_option(section['secid'], nopt, ndesc)

    def record_example(self, option, example, ndesc=None):
        if example:
            ms = re.match(r'^(.*)\.\s*(.*)$', example['desc'])
            if ms:
                example['title'] = ms.group(1)
                example['desc'] = ms.group(2)
            option['exmidxs'].append(len(self.examples))
            self.examples.append(example)
        if ndesc: return self.init_example(option['opt'], ndesc)

    def init_section(self, secid, title):
        section = {
            'secid': secid,
            'title': title,
            'desc': "",
            'level': 0,
            'opts': []
        }
        level = len(re.split(r'\.', secid))
        section['level'] = level
        return section

    def init_option(self, secid, opt, desc):
        option = {}
        types = ("Mode", "Info", "Info", "Action")
        if opt not in self.OPTS:
            self.pglog(f"{opt} -- option not defined for {self.DOCS['DOCNAM']}", self.LGWNEX)
        option['secid'] = secid
        option['opt'] = opt
        ms = re.match(r'^(, | \(Alias: .*\), )(.*)', desc)
        if ms: desc = ms.group(2)
        option['desc'] = desc + "\n"
        option['exmidxs'] = []
        option['name'] = self.OPTS[opt][1]
        if opt in self.ALIAS: option['alias'] = self.ALIAS[opt]
        typidx = self.OPTS[opt][0]
        if typidx > 3: typidx = 3
        option['type'] = types[typidx]
        return option

    def init_example(self, opt, desc):
        example = {'opt': opt, 'title': "", 'desc': desc.title() + "\n"}
        return example

    def get_short_option(self, p):
        plen = len(p)
        if plen == 2 and p in self.options: return p
        for opt in self.OPTS:
            if re.match(rf'^{self.OPTS[opt][1]}$', p, re.I): return opt
        for opt in self.ALIAS:
            for alias in self.ALIAS[opt]:
                if re.match(rf'^{alias}$', p, re.I): return opt
        self.pglog(f"{p} - unknown option for {self.DOCS['DOCNAM']}", self.LGWNEX)

    def get_title_link(self, title):
        for section in self.sections:
            if title == section['title']:
                return f"section{section['secid']}.rst"
        return title

    def get_section(self, secid):
        for section in self.sections:
            if section['secid'] == secid: return section
        self.pglog(f"Unknown Section ID {secid}", self.LGWNEX)

    # --- RST Output Functions ---
    def write_rst_docs(self, docname, opts, alias):
        self.OPTS = opts
        self.ALIAS = alias
        self.parse_docs(docname)
        self.DOCS['DOCNAM'] = docname
        self.DOCS['DOCTIT'] = docname.upper()
        self.DOCS['DOCDIR'] = f"{self.DOCS['DCROOT']}/{docname}"
        self.change_local_directory(self.DOCS['DOCDIR'], self.LGWNEX)
        self.pglog(f"Write RST document '{docname}' under {self.DOCS['DOCDIR']}", self.LOGWRN)
        self.write_rst_index(self.sections[0])
        self.write_rst_toc()
        for section in self.sections:
            self.write_rst_section(section)
        self.pglog(f"RST document files written to {self.DOCS['DOCDIR']}", self.LOGWRN)

    def write_rst_index(self, section):
        hash = {'TITLE': self.DOCS['DOCTIT'], 'SECID': section['secid']}
        self.template_to_rst("index", hash)

    def write_rst_toc(self):
        hash = {'TITLE': self.DOCS['DOCTIT'], 'TOC': self.create_rst_toc()}
        self.template_to_rst("toc", hash)

    def write_rst_section(self, section):
        hash = {'TITLE': section['title'], 'SECID': section['secid'], 'SECTION': self.create_rst_section(section)}
        self.template_to_rst("section", hash, section['secid'])

    def template_to_rst(self, template, hash, extra=None):
        rst_template_dir = os.path.join(os.path.dirname(__file__), 'rst_templates')
        tempfile = os.path.abspath(os.path.join(rst_template_dir, f"{template}.temp"))
        if extra is None:
            extra = ""
        rstfile = os.path.join(self.DOCS['DOCDIR'], f"{template}{extra}.rst")
        with open(tempfile, 'r') as tf, open(rstfile, 'w') as rf:
            idx = 0
            for line in tf:
                idx += 1
                if re.match(r'\s*#', line):
                    continue  # skip comment lines
                ms = re.match(r'^(.*\S)\s+#', line)
                if ms:
                    line = ms.group(1)  # remove comments
                else:
                    line = line.rstrip()
                matches = re.findall(r'__([A-Z_]+)__', line)
                if matches:
                    for key in matches:
                        if key not in hash:
                            self.pglog(f"{key}: not defined at {line}({idx}) {tempfile}", self.LGWNEX)
                            continue
                        if not hash[key]:
                            self.pglog(f"{key}: empty content", self.LGWNEX)
                        line = line.replace(f"__{key}__", hash[key])
                rf.write(line + "\n")
        self.pglog(f"{template}{extra}.rst created from {template}.temp", self.LOGWRN)

    def create_rst_toc(self):
        content = ""
        for section in self.sections:
            content += f"  * {section['secid']} {section['title']}\n"
        if self.examples:
            content += "\n.. rubric:: Appendix A: List of Examples\n\n"
            for idx, example in enumerate(self.examples, 1):
                opt = example['opt']
                option = self.options[opt]
                secid = option['secid']
                content += f"  * Example {idx}: {option['type']} Option -{opt} (-{option['name']}) (see section {secid})\n"
        return content

    def create_rst_section(self, section):
        out = ''
        if section['desc'].strip():
            out += self.rst_description(section['desc']) + '\n'
        for opt in section['opts']:
            out += self.rst_option(opt)
        return out

    def rst_option(self, opt):
        option = self.options[opt]
        out = f".. _{opt}:\n\n**{option['type']} Option -{opt} (-{option['name']})**\n\n"
        if 'alias' in option:
            alias = option['alias']
            out += f"  Alias: {', '.join(alias)}\n\n"
        out += self.rst_description(option['desc']) + '\n'
        if 'exmidxs' in option:
            for idx in option['exmidxs']:
                out += self.rst_example(idx)
        return out

    def rst_example(self, exmidx):
        example = self.examples[exmidx]
        exm = exmidx + 1
        out = f".. _example{exm}:\n\nExample {exm}: {example['title']}\n{'~' * (9 + len(str(exm)) + len(example['title']))}\n\n"
        out += self.rst_description(example['desc']) + '\n'
        return out

    def rst_description(self, desc):
        lines = desc.strip().split('\n')
        out = ''
        for line in lines:
            if not line.strip():
                out += '\n'
            elif re.match(r'^\s*- ', line):
                out += f"* {line.strip()[2:]}\n"
            else:
                out += f"{line}\n"
        return out + '\n'

    def rst_synopsis(self, lines, cnt, secid, dtype):
        out = "\n.. list-table:: Synopsis\n   :widths: 20 80\n   :header-rows: 0\n\n"
        for i in range(cnt):
            line = lines[i].strip()
            if re.search(r'\sor\s', line, re.I):
                out += "   * - Or\n     - " + "\n"
            else:
                ms = re.match(r'^\s*{}\s+(.+)$'.format(self.DOCS['DOCNAM']), line)
                if ms:
                    out += f"   * - ``{self.DOCS['DOCNAM']}``\n     - {ms.group(1)}\n"
                else:
                    out += f"   * - \n     - {line}\n"
        out += "\n"
        return out

    def rst_table(self, lines, cnt, secid):
        out = "\n.. list-table::\n   :widths: 30 70\n   :header-rows: 0\n\n"
        line0 = lines[0].lstrip()
        ms = re.match(r'^\s+-\s+(.*)', line0)
        if ms:
            out += f"   * - {ms.group(1)}\n"
            for i in range(1, cnt):
                line = lines[i].lstrip()
                ms = re.match(r'^\s+-\s+(.*)', line)
                if ms:
                    out += f"   * - {ms.group(1)}\n"
                else:
                    out += f"     - {line}\n"
        elif re.search(r'=>$', line0):
            for i in range(cnt):
                line = lines[i].lstrip()
                parts = re.split(r'\s*=>\s*', line)
                if len(parts) == 2:
                    out += f"   * - {parts[0]}\n     - {parts[1]}\n"
                else:
                    out += f"   * - {line}\n     - \n"
        elif re.search(r'\S\s+-\s+\S', line0):
            for i in range(cnt):
                line = lines[i].lstrip()
                ms = re.match(r'^(.*\S)\s+-\s+(\S.*)$', line)
                if ms:
                    out += f"   * - {ms.group(1)}\n     - {ms.group(2)}\n"
                else:
                    out += f"   * - {line}\n     - \n"
        else:
            for i in range(cnt):
                line = lines[i].lstrip()
                out += f"   * - {line}\n     - \n"
        out += "\n"
        return out

def main():
    import argparse
    import os
    import importlib
    parser = argparse.ArgumentParser(description="Convert text help documents to RST format.")
    parser.add_argument('docname', help='Document name (e.g., dsarch, dsupdt)')
    parser.add_argument('--opts', type=str, default=None, help='Python file with OPTS and ALIAS definitions (module or class)')
    parser.add_argument('--docpath', type=str, default=None, help='Path to directory containing .usg docs (default: same as opts file)')
    parser.add_argument('--dcroot', type=str, default=os.getcwd(), help='Root directory for output RST files (default: current directory)')
    args = parser.parse_args()

    # Try to import opts_module
    opts_module = None
    if args.opts:
        import importlib.util
        spec = importlib.util.spec_from_file_location("opts_module", args.opts)
        opts_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(opts_module)
    else:
        # Try to import as rda_python_{docname}.{docname}
        modname = f"rda_python_{args.docname}.{args.docname}"
        try:
            opts_module = importlib.import_module(modname)
        except ImportError as e:
            raise RuntimeError(f"Could not import opts_module: {modname}. Please provide --opts or ensure the module exists.\n{e}")

    # Try to get OPTS and ALIAS from a class if present, else from module
    OPTS = None
    ALIAS = None
    opts_class = None
    for attr in dir(opts_module):
        obj = getattr(opts_module, attr)
        if isinstance(obj, type):
            # Found a class, try to instantiate and get OPTS/ALIAS
            opts_class = obj
            break
    if opts_class:
        opts_instance = opts_class()
        OPTS = getattr(opts_instance, 'OPTS', None)
        ALIAS = getattr(opts_instance, 'ALIAS', None)
    if OPTS is None or ALIAS is None:
        # Fallback to module-level
        OPTS = getattr(opts_module, 'OPTS', None)
        ALIAS = getattr(opts_module, 'ALIAS', None)
    if OPTS is None or ALIAS is None:
        raise RuntimeError('Could not find OPTS and ALIAS in opts_module (either as class attributes or module variables)')

    # Determine docpath
    if args.docpath:
        docpath = args.docpath
    elif args.opts:
        docpath = os.path.dirname(os.path.abspath(args.opts))
    else:
        # opts_module loaded as a package, get its __file__
        docpath = os.path.dirname(os.path.abspath(getattr(opts_module, '__file__', os.getcwd())))

    pgrst = PgRST()
    pgrst.DOCS['ORIGIN'] = docpath
    pgrst.DOCS['DCROOT'] = args.dcroot
    pgrst.write_rst_docs(args.docname, OPTS, ALIAS)

if __name__ == "__main__":
    main()
