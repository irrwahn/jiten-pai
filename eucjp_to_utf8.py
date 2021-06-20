#!/usr/bin/python3

"""
    eucjp_to_utf8.py

    Convert optional gzip compressed EUC-JP encoded text to UTF-8.

    Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>
    Modified ("3-clause") BSD License
"""

import sys
import os
import codecs

def usage(msg=''):
    eprint(
"""%s\n
USAGE:
  %s [-d] [-n] [-v] [infile [outfile]]
    -d : decompress gzip compressed input file; default: infer from infile extension
    -n : do not attempt to decode EUC-JP; default: auto-detect
    -v : print informational messages
  Writes to stdout, if no outfile specified.
  Reads from stdin, if no infile specified.
""" % (msg, os.path.basename(sys.argv[0])))
    sys.exit(1)

decomp = False
recode = True
verbose = False
ifile = None
ofile = None

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def veprint(*args, **kwargs):
    if verbose:
        eprint(*args, **kwargs)

for arg in sys.argv[1:]:
    try:
        if arg[0] == '-':
            for opt in arg[1:]:
                if opt == 'd':
                    decomp = True
                elif opt == 'n':
                    recode = False
                elif opt == 'v':
                    verbose = True
                else:
                    usage("Unexpected option: '-%s'" % opt)
        elif not ifile:
            iname = arg
            ifile = open(iname, 'rb')
            if not decomp and iname[-3:] == '.gz':
                veprint('Info: gzip decompression auto-enabled')
                decomp = True
        elif not ofile:
            ofile = open(arg, 'w')
        else:
            usage("Unexpected argument: '%s'" % arg)
    except Exception as e:
        usage(str(e))

if not ofile:
    ofile = sys.stdout
    if not ifile:
        ifile = sys.stdin.detach()

if decomp:
    import gzip
    ifile = gzip.GzipFile(fileobj=ifile)

cnt = 0
for line in ifile:
    try:
        if recode:
            try:
                oline = line.decode('euc_jp')
            except UnicodeDecodeError as e:
                veprint('Info: EUC-JP decoding auto-disabled.')
                oline = line.decode('utf_8')
                recode = False
        else:
            oline = line.decode('utf_8')
        print(oline, end='', file=ofile)
        cnt += 1
    except Exception as e:
        usage('%s%s' % (str(e), "" if decomp else "\n(Forgot '-d'?)"))

veprint('Successfully processed %d lines.' % cnt)
