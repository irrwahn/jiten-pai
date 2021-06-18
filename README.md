# Jiten-pai

A Gjiten-lookalike Japanese dictionary written in Python.

## Prerequisites

Running `jiten-pai.py` requires Python version >= 3.7 installed, plus the
PyQt5 python bindings for Qt5. Tested with Python 3.7.3, PyQt5 5.11.3.

Dictionary files are not included in Jiten-pai, these have to be downloaded
and installed separately, see next section.


## Get and Install Dictionary Files

Jiten-pai supports dictionary files in EDICT format, as made available by the
[Electronic Dictionary Research and Development Group](http://www.edrdg.org/)
as part of the *Japanese/English Dictionary Project*:

* [EDICT2u](http://ftp.edrdg.org/pub/Nihongo/edict2u.gz) *(recommended)*
    * EDICT main dictionary, modern format, UTF-8 coding
    * download file to a convenient location, unpack like this:
      > `gunzip edict2u.gz`
    * install in Jiten-pai using the Edit->Preferences dialog

* [EDICT](http://ftp.edrdg.org/pub/Nihongo/edict.gz) *(not recommended)*
    * same as above, legacy format, EUC-JP coding
    * download file, then unpack and convert to UTF-8:
      > `zcat edict.gz | recode EUC-JP..UTF-8 > edict`
    * install using Edit->Preferences

The following is part of the *Japanese Proper Names Dictionary project*:

* [ENAMDICT](http://ftp.edrdg.org/pub/Nihongo/enamdict.gz) *(optional)*
    * named entity dictionary, EUC-JP coding
    * download file, then unpack and convert to UTF-8:
      > `zcat enamdict.gz | recode EUC-JP..UTF-8 > enamdict`
    * install using Edit->Preferences

Additional dictionaries and alternative language versions are available at
the EDRDG, see the [FTP archive](http://ftp.edrdg.org/pub/Nihongo/#dic_fil).
The respective accompanying documentation will have the details, and in
particular indicate whether a file is actually in EDICT format. In many
cases a conversion from EUC-JP to UTF-8 will be necessary, as outlined in
the examples above.

**HINT:** In case the `recode` utility is not available, the included
transcoding script may be used instead, e.g.:
> `./eucjp_to_utf8.py enamdict.gz enamdict`


## Notes

@@@ ToDo

* If the search term contains any Katakana or Hiragana, Jiten-pai will
  always report matches for both syllabaries. This is intentional.

* During startup Jiten-pai will look for the `vconj.utf8` verb conjugation
  file in the following directories, in the given order:
    * `$HOME/.local/share/jiten-pai/`
    * `/usr/local/share/jiten-pai/`
    * `/usr/share/jiten-pai/`
    * `current working directory`

    Without this file the verb de-inflection option will not be available.


## Known issues

@@@ ToDo

* KanjiDic is not implemented yet.

* ...

## License

Jiten-pai incorporates parts taken from other projects, namely:

* Kana conversion code adapted from [jaconv](https://github.com/ikegami-yukino/jaconv),
  Copyright (c) 2014 Yukino Ikegami, MIT License

* VCONJ verb de-inflection rule file taken from [Gjiten](http://gjiten.sourceforge.net/),
  Copyright (c) 1999-2005 Botond Botyanszki, GNU General Public License v2.0

The remaining majority of Jiten-pai code is distributed under the
Modified ("3-clause") BSD License. See `LICENSE` file for more information.
