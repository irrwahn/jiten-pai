#!/usr/bin/python3

"""
    eucjp_to_utf8.py

    Convert EUC-JP encoded text to UTF-8.
    Input files with .gz extension are automatically decompressed.

    USAGE:  eucjp_to_utf8.py [infile [outfile]]

    Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>
    Modified ("3-clause") BSD License
"""

import sys
import codecs

if len(sys.argv) > 1:
    iname = sys.argv[1]
    ifile = open(iname, 'rb')
    if iname[-3:] == '.gz':
        import gzip
        ifile = gzip.GzipFile(fileobj=ifile)
else:
    ifile = sys.stdin.detach()

ofile = open(sys.argv[2], 'w') if len(sys.argv) > 2 else sys.stdout

for line in ifile:
    print(line.decode('euc_jp'), end='', file=ofile)
