# Jiten-pai

A Gjiten-lookalike Japanese dictionary written in Python.

## Prerequisites

Running `jiten-pai.py` requires Python version >= 3.7 installed, plus the
PyQt5 python bindings for Qt5. Tested with Python 3.7.3, PyQt5 5.11.3.

Dictionary files are not included in Jiten-pai, these have to be downloaded
and installed separately, see next section.


## Get and Install Dictionary Files

Jiten-pai supports word dictionary files in EDICT format, as made available by
the [Electronic Dictionary Research and Development Group](http://www.edrdg.org/):

* [EDICT2](http://ftp.edrdg.org/pub/Nihongo/edict2.gz) *(essential)*
    * EDICT main dictionary; revised format; EUC-JP encoding;
    * download file, then unpack and convert to UTF-8:
      > `zcat edict2.gz | recode EUC-JP..UTF-8 > edict2`
    * install in Jiten-pai using the Edit→Preferences dialog
    * **HINT:** In case the `zcat` or `recode` utilities are not available,
      the included simple transcoding utility can be used instead, e.g.:
```
            eucjp_to_utf8.py edict2.gz edict2
            eucjp_to_utf8.py enamdict.gz enamdict
            eucjp_to_utf8.py kanjidic.gz kanjidic
```

* [EDICT](http://ftp.edrdg.org/pub/Nihongo/edict.gz) *(obsolete)*
    * predecessor to EDICT2; legacy format; EUC-JP encoding
    * download file, unpack and convert to UTF-8 *(see above)*
    * install via Edit→Preferences

* [ENAMDICT](http://ftp.edrdg.org/pub/Nihongo/enamdict.gz) *(optional)*
    * named entity dictionary; EDICT format; EUC-JP encoding
    * download file, unpack and convert to UTF-8 *(see above)*
    * install via Edit→Preferences

More word dictionaries and alternative language versions are available at
the [EDRDG archive](http://ftp.edrdg.org/pub/Nihongo/#dic_fil). The
respective accompanying documentation will have the details, and in
particular indicate whether a file is actually in EDICT(2) format. In most
cases a conversion from EUC-JP to UTF-8 will be necessary, see above.

In addition to any of the abovementioned word dictionaries, the KanjiDic
part of Jiten-pai requires installation of one of the `kanjidic` files,
also made available by the EDRDG:

* [KANJIDIC](http://ftp.edrdg.org/pub/Nihongo/kanjidic.gz) *(recommended)*
    * Kanji dictionary; plain text format; EUC-JP encoding
    * contains all kanji covered by the JIS X 0208-1998 standard
    * download file, unpack and convert to UTF-8 *(see above)*
    * install via Edit→Preferences

* [KANJIDIC_COMB](http://ftp.edrdg.org/pub/Nihongo/kanjidic_comb_utf8.gz) *(alternative)*
    * Kanji dictionary; plain text format; UTF-8 encoding
    * additionally contains kanji from JIS X 0212/0213 supplementary sets
    * download file, unpack, install via Edit→Preferences

* [KANJIDIC2](http://ftp.edrdg.org/pub/Nihongo/kanjidic2.xml.gz) *(alternative)*
    * Kanji dictionary; XML format; UTF-8 encoding
    * additionally contains kanji from JIS X 0212/0213 supplementary sets
    * **caveat:** does not support full text search
    * download file, unpack, install via Edit→Preferences

The [EDRDG licence page](http://www.edrdg.org/edrdg/licence.html) provides
dictionary copyright information and licensing terms.


## Notes

* If the search term contains any Katakana or Hiragana, Jiten-pai will
  always report matches for both syllabaries. This is intentional.

* The word search supports Python regular expression syntax to allow for
  more flexible queries. Consequently, backslash-escaping is required when,
  for whatever reason, searching verbatim for regex special characters
  like '.', '(', ')', etc.  Using the '^' and '$' regex anchors is
  strongly discouraged. Equivalent functionality is already provided by
  the various search options. (If this paragraph is all Greek to you,
  chances are you can safely ignore it.)

* During startup Jiten-pai will look for the `vconj.utf8` verb conjugation
  file as well as the `kradfile.utf8` and `radkfile.utf8` kanji radical
  cross-reference files in the following directories, in the given order:
    * `$HOME/.local/share/jiten-pai/`
    * `/usr/local/share/jiten-pai/`
    * `/usr/share/jiten-pai/`
    * `current working directory`

    Without these files verb de-inflection and radical search, respectively,
    will not be available.


## Command Line

Jiten-pai supports a few command line options which might come in handy
for workflow integration.  These should be fairly self explaining:
```
    usage: jiten-pai.py [-h] [-k] [-K] [-c] [-v] [-l KANJI] [-w WORD]

    Jiten-pai Japanese dictionary

    optional arguments:
      -h, --help                      show this help message and exit
      -k, --kanjidic                  start with KanjiDic
      -K                              same as -k, but word dictionary visible
      -c, --clip-kanji                look up kanji from clipboard
      -v, --clip-word                 look up word from clipboard
      -l KANJI, --kanji-lookup KANJI  look up KANJI in kanji dictionary
      -w WORD, --word-lookup WORD     look up WORD in word dictionary

    Only one of these options should be used at a time.
```


## Known issues

* *TBD*


## License

Jiten-pai incorporates parts taken from other projects, namely:

* Kana conversion code adapted from [jaconv](https://github.com/ikegami-yukino/jaconv);
  Copyright (c) 2014 Yukino Ikegami; MIT License

* VCONJ verb de-inflection rule file adapted from XJDIC;
  Copyright (c) 1998-2003 J.W. Breen; GNU General Public License v2.0
  Modifications for Gjiten 1999-2005 by Botond Botyanszki

* RADKFILE and KRADFILE kanji radical cross-reference adapted from
  [The KRADFILE/RADKFILE Project](http://www.edrdg.org/krad/kradinf.html);
  Copyright (c) James William BREEN and The Electronic Dictionary Research
  and Development Group; Creative Commons Attribution-ShareAlike Licence (V3.0)

The remaining majority of Jiten-pai code is distributed under the
Modified ("3-clause") BSD License. See `LICENSE` file for more information.
