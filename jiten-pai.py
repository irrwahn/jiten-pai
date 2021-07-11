#!/usr/bin/env python3

"""
jiten-pai.py

Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>

Contributors:
    volpol

Jiten-pai is distributed under the Modified ("3-clause") BSD License.
See `LICENSE` file for more information.
"""


_JITENPAI_VERSION = '0.1.0'
_JITENPAI_NAME = 'Jiten-pai'
_JITENPAI_DIR = 'jiten-pai'
_JITENPAI_CFG = 'jiten-pai.conf'
_JITENPAI_VCONJ = 'vconj.utf8'

_JITENPAI_INFO = """<p>Jiten-pai incorporates parts taken from other projects:
</p><p>
Kana conversion code adapted from <a href="https://github.com/ikegami-yukino/jaconv">jaconv</a>.<br>
Copyright (c) 2014 Yukino Ikegami; MIT License
</p><p>
VCONJ verb de-inflection rule file adapted from XJDIC.<br>
Copyright (c) 1998-2003 J.W. Breen; GNU General Public License v2.0<br>
Modifications for Gjiten 1999-2005 by Botond Botyanszki
</p><p>
RADKFILE and KRADFILE kanji radical cross-reference adapted from
<a href="http://www.edrdg.org/krad/kradinf.html">The KRADFILE/RADKFILE Project</a>.<br>
Copyright (c) James William BREEN and The Electronic Dictionary Research
and Development Group; Creative Commons Attribution-ShareAlike Licence (V3.0)
</p>"""

import sys

_PYTHON_VERSION = float("%d.%d" % (sys.version_info.major, sys.version_info.minor))
if _PYTHON_VERSION < 3.6:
    raise Exception ('Need Python version 3.6 or later, got version ' + str(sys.version))

import platform
import io
import os
import re
import json
import unicodedata
import enum
import base64
from collections import namedtuple
from argparse import ArgumentParser, RawTextHelpFormatter
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

############################################################
# utility functions and classes

def die(rc=0):
    sys.exit(rc)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Note: we only test for common CJK ideographs
_u_CJK_Uni = r'\u4e00-\u9FFF'
_u_CJK_Kana = r'\u3040-\u30ff'
_u_CJK_FullHalf = r'\uFF00-\uFFEF'

_re_kanji = re.compile('^[' + _u_CJK_Uni + ']$')
_re_jap = re.compile('[' + _u_CJK_Uni + _u_CJK_Kana + _u_CJK_FullHalf + ']')

# test, if a single character /might/ be a kanji
def _is_kanji(s):
    return _re_kanji.match(s)

# test, if a string contains any common Japanese characters
def _has_jap(s):
    return _re_jap.search(s)

class ScanMode(enum.Enum):
    JAP = 1
    ENG = 2


############################################################
# configuration

cfg = {
    'kanjidic': '/usr/local/share/jiten-pai/kanjidic',
    'dicts': [
        ['edict2', '/usr/local/share/jiten-pai/edict2'],
    ],
    'dict_load': True,
    'dict_idx': 0,
    'dict_all': False,
    'limit': 100,
    'do_limit': True,
    'auto_adj': True,
    'jap_opt': [True, False, False, False],
    'eng_opt': [True, False, False],
    'romaji': False,
    'nfont': 'sans',
    'nfont_sz': 12.0,
    'lfont': 'IPAPMincho',
    'lfont_sz': 24.0,
    'hl_col': 'blue',
    'deinflect': False,
    # saved, but not editable from GUI:
    'hardlimit': 10000,
    'max_hist': 12,
    'history': [],
    # not saved, run-time only:
    'cfgfile': None,
}

def _get_cfile_path(fname, mode=os.R_OK):
    # try to find a suitable configuration file / prefix
    cdirs = []
    if os.environ.get('APPDATA'):
        cdirs.append(os.environ.get('APPDATA'))
    if os.environ.get('XDG_CONFIG_HOME'):
        cdirs.append(os.environ.get('XDG_CONFIG_HOME'))
    if os.environ.get('HOME'):
        cdirs.append(os.path.join(os.environ.get('HOME'), '.config'))
    cdirs.append(os.path.dirname(os.path.realpath(__file__)))
    for d in cdirs:
        path = os.path.join(d, fname)
        if os.access(path, mode):
            return path
    return fname

def _save_cfg():
    s_cfg = cfg.copy()
    s_cfg.pop('cfgfile', None)
    if cfg['cfgfile']:
        try:
            with open(cfg['cfgfile'], 'w') as cfgfile:
                json.dump(s_cfg, cfgfile, indent=2)
                return
        except Exception as e:
            eprint('_save_cfg:', cfg['cfgfile'], str(e))
    cfgdir = _get_cfile_path('', mode=os.R_OK | os.W_OK | os.X_OK)
    cfname = os.path.join(cfgdir, _JITENPAI_CFG)
    try:
        with open(cfname, 'w') as cfgfile:
            json.dump(s_cfg, cfgfile, indent=2)
            cfg['cfgfile'] = cfname
            return
    except Exception as e:
        eprint('_save_cfg:', cfname, str(e))

def _load_cfg():
    cfname = _get_cfile_path('', mode=os.R_OK)
    cfname = os.path.join(cfname, _JITENPAI_CFG)
    try:
        with open(cfname, 'r') as cfgfile:
            cfg.update(json.load(cfgfile))
            cfg['cfgfile'] = cfname
    except Exception as e:
        eprint('_load_cfg:', cfname, str(e))
    global _dict_lookup
    _dict_lookup = _dict_lookup_load if cfg['dict_load'] else _dict_lookup_noload


############################################################
# import kanjidic
try:
    from kanjidic import kdMainWindow
    _got_kd = True
except Exception as e:
    eprint('kanjidic.py:', e)
    _got_kd = False

############################################################
# verb de-inflection

Vtype = namedtuple('Vtype', 'wclass label')
Vconj = namedtuple('Vconj', 'regex conj infi rule')

_vconj_type = dict()  # format: { rule_no: (wclass, label), ... }
_vconj_deinf = []     # format: [ (regex, conj, infinitve, rule_no), ... ]
_vconj_loaded = False

def _get_dfile_path(fname, mode=os.R_OK):
    # try to locate a data file in some common prefixes:
    cdirs = []
    if os.environ.get('APPDATA'):
        cdirs.append(os.environ.get('APPDATA'))
    if os.environ.get('HOME'):
        cdirs.append(os.path.join(os.environ.get('HOME'), '.local/share'))
    cdirs.append('/usr/local/share')
    cdirs.append('/usr/share')
    cdirs.append(os.path.dirname(os.path.realpath(__file__)))
    for d in cdirs:
        path = os.path.join(d, fname)
        if os.access(path, mode):
            return path
    return fname

# load and parse VCONJ rule file
def _vconj_load():
    global _vconj_loaded
    vcname = _JITENPAI_VCONJ
    if not os.access(vcname, os.R_OK):
        vcname = _get_dfile_path(os.path.join(_JITENPAI_DIR, _JITENPAI_VCONJ), mode=os.R_OK)
    try:
        with open(vcname) as vcfile:
            re_type = re.compile(r'^(\d+)\s+"(\S+)"\s+(.+)$')
            re_deinf = re.compile(r'^\s*([^#\s]+)\s+(\S+)\s+(\d+)\s*$')
            for line in vcfile:
                match = re_type.match(line)
                if match:
                    wclass = re.compile(r'(\((.+?,)*?)' + match.group(2))
                    _vconj_type[int(match.group(1))] = Vtype(wclass, match.group(3))
                    continue
                match = re_deinf.match(line)
                if match:
                    regex = re.compile('%s$' % match.group(1))
                    _vconj_deinf.append(Vconj(regex, match.group(1), match.group(2), int(match.group(3))))
                    continue
        _vconj_loaded = len(_vconj_deinf) > 0
    except Exception as e:
        eprint('_vconj_load:', vcname, str(e))

# collect inflection rules potentially applicable to a verb(-candidate)
Vinf = namedtuple('Vinf', 'infi blurb wclass')

def _vconj_deinflect(verb):
    inf = []
    blurb = ''
    for deinf in _vconj_deinf:
        verb_inf = deinf.regex.sub(deinf.infi, verb)
        if verb_inf != verb:
            blurb = '%s %s → %s' % (_vconj_type[deinf.rule].label, deinf.conj, deinf.infi)
            wclass = _vconj_type[deinf.rule].wclass
            inf.append(Vinf(verb_inf, blurb, wclass))
    return inf


############################################################
# Katakana -> Hiragana <- Romaji conversion code adapted from:
#   https://github.com/ikegami-yukino/jaconv
#   Copyright (c) 2014 Yukino Ikegami
#   MIT License

HIRAGANA = list('ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすず'
                'せぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴ'
                'ふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろわ'
                'をんーゎゐゑゕゖゔゝゞ・「」。、')

FULL_KANA = list('ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソ'
                 'ゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペ'
                 'ホボポマミムメモャヤュユョヨラリルレロワヲンーヮヰヱヵヶヴ'
                 'ヽヾ・「」。、')

HEPBURN = list('aiueoaiueon')
HEPBURN_KANA = list('ぁぃぅぇぉあいうえおん')

def _to_ord_list(chars):
    return list(map(ord, chars))

def _to_dict(_from, _to):
    return dict(zip(_from, _to))

K2H_TABLE = _to_dict(_to_ord_list(FULL_KANA), HIRAGANA)
HEP2KANA = _to_dict(_to_ord_list(HEPBURN), HEPBURN_KANA)

del _to_ord_list
del _to_dict
del HIRAGANA
del FULL_KANA
del HEPBURN
del HEPBURN_KANA

def kata2hira(text):
    return text.translate(K2H_TABLE)

def alphabet2kana(text):
    # replace final h with う, e.g., Itoh -> いとう
    ending_h_pattern = re.compile(r'h$')
    text = re.sub(ending_h_pattern, 'う', text)

    text = text.replace('kya', 'きゃ').replace('kyi', 'きぃ').replace('kyu', 'きゅ')
    text = text.replace('kye', 'きぇ').replace('kyo', 'きょ')
    text = text.replace('gya', 'ぎゃ').replace('gyi', 'ぎぃ').replace('gyu', 'ぎゅ')
    text = text.replace('gye', 'ぎぇ').replace('gyo', 'ぎょ')
    text = text.replace('sha', 'しゃ').replace('shu', 'しゅ').replace('she', 'しぇ')
    text = text.replace('sho', 'しょ')
    text = text.replace('sya', 'しゃ').replace('syi', 'しぃ').replace('syu', 'しゅ')
    text = text.replace('sye', 'しぇ').replace('syo', 'しょ')
    text = text.replace('zya', 'じゃ').replace('zyu', 'じゅ').replace('zyo', 'じょ')
    text = text.replace('zyi', 'じぃ').replace('zye', 'じぇ')
    text = text.replace('ja', 'じゃ').replace('ju', 'じゅ').replace('jo', 'じょ')
    text = text.replace('jya', 'じゃ').replace('jyi', 'じぃ').replace('jyu', 'じゅ')
    text = text.replace('jye', 'じぇ').replace('jyo', 'じょ')
    text = text.replace('dya', 'ぢゃ').replace('dyi', 'ぢぃ').replace('dyu', 'ぢゅ')
    text = text.replace('dye', 'ぢぇ').replace('dyo', 'ぢょ')
    text = text.replace('cha', 'ちゃ').replace('chu', 'ちゅ').replace('che', 'ちぇ')
    text = text.replace('cho', 'ちょ')
    text = text.replace('cya', 'ちゃ').replace('cyi', 'ちぃ').replace('cyu', 'ちゅ')
    text = text.replace('cye', 'ちぇ').replace('cyo', 'ちょ')
    text = text.replace('tya', 'ちゃ').replace('tyi', 'ちぃ').replace('tyu', 'ちゅ')
    text = text.replace('tye', 'ちぇ').replace('tyo', 'ちょ')
    text = text.replace('tsa', 'つぁ').replace('tsi', 'つぃ').replace('tse', 'つぇ')
    text = text.replace('tso', 'つぉ')
    text = text.replace('thi', 'てぃ').replace('t\'i', 'てぃ')
    text = text.replace('tha', 'てゃ').replace('thu', 'てゅ').replace('t\'yu', 'てゅ')
    text = text.replace('the', 'てぇ').replace('tho', 'てょ')
    text = text.replace('dha', 'でゃ').replace('dhi', 'でぃ').replace('d\'i', 'でぃ')
    text = text.replace('dhu', 'でゅ').replace('dhe', 'でぇ').replace('dho', 'でょ')
    text = text.replace('d\'yu', 'でゅ')
    text = text.replace('twa', 'とぁ').replace('twi', 'とぃ').replace('twu', 'とぅ')
    text = text.replace('twe', 'とぇ').replace('two', 'とぉ').replace('t\'u', 'とぅ')
    text = text.replace('dwa', 'どぁ').replace('dwi', 'どぃ').replace('dwu', 'どぅ')
    text = text.replace('dwe', 'どぇ').replace('dwo', 'どぉ').replace('d\'u', 'どぅ')
    text = text.replace('nya', 'にゃ').replace('nyi', 'にぃ').replace('nyu', 'にゅ')
    text = text.replace('nye', 'にぇ').replace('nyo', 'にょ')
    text = text.replace('hya', 'ひゃ').replace('hyi', 'ひぃ').replace('hyu', 'ひゅ')
    text = text.replace('hye', 'ひぇ').replace('hyo', 'ひょ')
    text = text.replace('mya', 'みゃ').replace('myi', 'みぃ').replace('myu', 'みゅ')
    text = text.replace('mye', 'みぇ').replace('myo', 'みょ')
    text = text.replace('rya', 'りゃ').replace('ryi', 'りぃ').replace('ryu', 'りゅ')
    text = text.replace('rye', 'りぇ').replace('ryo', 'りょ')
    text = text.replace('bya', 'びゃ').replace('byi', 'びぃ').replace('byu', 'びゅ')
    text = text.replace('bye', 'びぇ').replace('byo', 'びょ')
    text = text.replace('pya', 'ぴゃ').replace('pyi', 'ぴぃ').replace('pyu', 'ぴゅ')
    text = text.replace('pye', 'ぴぇ').replace('pyo', 'ぴょ')
    text = text.replace('vyi', 'ゔぃ').replace('vyu', 'ゔゅ').replace('vye', 'ゔぇ')
    text = text.replace('vyo', 'ゔょ')
    text = text.replace('fya', 'ふゃ').replace('fyu', 'ふゅ').replace('fyo', 'ふょ')
    text = text.replace('hwa', 'ふぁ').replace('hwi', 'ふぃ').replace('hwe', 'ふぇ')
    text = text.replace('hwo', 'ふぉ').replace('hwyu', 'ふゅ')
    text = text.replace('pha', 'ふぁ').replace('phi', 'ふぃ').replace('phu', 'ふぅ')
    text = text.replace('phe', 'ふぇ').replace('pho', 'ふぉ')
    text = text.replace('xn', 'ん').replace('xa', 'ぁ').replace('xi', 'ぃ')
    text = text.replace('xu', 'ぅ').replace('xe', 'ぇ').replace('xo', 'ぉ')
    text = text.replace('lyi', 'ぃ').replace('xyi', 'ぃ').replace('lye', 'ぇ')
    text = text.replace('xye', 'ぇ').replace('xka', 'ヵ').replace('xke', 'ヶ')
    text = text.replace('lka', 'ヵ').replace('lke', 'ヶ')
    text = text.replace('ca', 'か').replace('ci', 'し').replace('cu', 'く')
    text = text.replace('co', 'こ')
    text = text.replace('qa', 'くぁ').replace('qi', 'くぃ').replace('qu', 'く')
    text = text.replace('qe', 'くぇ').replace('qo', 'くぉ')
    text = text.replace('kwa', 'くぁ').replace('kwi', 'くぃ').replace('kwu', 'くぅ')
    text = text.replace('kwe', 'くぇ').replace('kwo', 'くぉ')
    text = text.replace('gwa', 'ぐぁ').replace('gwi', 'ぐぃ').replace('gwu', 'ぐぅ')
    text = text.replace('gwe', 'ぐぇ').replace('gwo', 'ぐぉ')
    text = text.replace('swa', 'すぁ').replace('swi', 'すぃ').replace('swu', 'すぅ')
    text = text.replace('swe', 'すぇ').replace('swo', 'すぉ')
    text = text.replace('zwa', 'ずぁ').replace('zwi', 'ずぃ').replace('zwu', 'ずぅ')
    text = text.replace('zwe', 'ずぇ').replace('zwo', 'ずぉ')
    text = text.replace('je', 'じぇ')
    text = text.replace('ti', 'ち')
    text = text.replace('xtu', 'っ').replace('xtsu', 'っ')
    text = text.replace('ltu', 'っ').replace('ltsu', 'っ')
    text = text.replace('xya', 'ゃ').replace('lya', 'ゃ')
    text = text.replace('xyu', 'ゅ').replace('lyu', 'ゅ')
    text = text.replace('xyo', 'ょ').replace('lyo', 'ょ')
    text = text.replace('wha', 'うぁ').replace('whi', 'うぃ').replace('whu', 'う')
    text = text.replace('whe', 'うぇ').replace('who', 'うぉ')
    text = text.replace('xwa', 'ゎ').replace('lwa', 'ゎ')
    text = text.replace('tsu', 'つ')
    text = text.replace('ga', 'が').replace('gi', 'ぎ').replace('gu', 'ぐ')
    text = text.replace('ge', 'げ').replace('go', 'ご')
    text = text.replace('za', 'ざ').replace('ji', 'じ').replace('zi', 'じ')
    text = text.replace('zu', 'ず').replace('ze', 'ぜ').replace('zo', 'ぞ')
    text = text.replace('da', 'だ').replace('di', 'ぢ')
    text = text.replace('zu', 'づ').replace('du', 'づ')
    text = text.replace('de', 'で').replace('do', 'ど')
    text = text.replace('va', 'ゔぁ').replace('vi', 'ゔぃ').replace('vu', 'ゔ')
    text = text.replace('ve', 'ゔぇ').replace('vo', 'ゔぉ').replace('vya', 'ゔゃ')
    text = text.replace('ba', 'ば').replace('bi', 'び').replace('bu', 'ぶ')
    text = text.replace('be', 'べ').replace('bo', 'ぼ').replace('pa', 'ぱ')
    text = text.replace('pi', 'ぴ').replace('pu', 'ぷ').replace('pe', 'ぺ')
    text = text.replace('po', 'ぽ')
    text = text.replace('ka', 'か').replace('ki', 'き').replace('ku', 'く')
    text = text.replace('ke', 'け').replace('ko', 'こ').replace('sa', 'さ')
    text = text.replace('shi', 'し').replace('su', 'す').replace('se', 'せ').replace('si', 'し')
    text = text.replace('so', 'そ').replace('ta', 'た').replace('chi', 'ち')
    text = text.replace('te', 'て').replace('to', 'と')
    text = text.replace('na', 'な').replace('ni', 'に').replace('nu', 'ぬ')
    text = text.replace('ne', 'ね').replace('no', 'の').replace('ha', 'は')
    text = text.replace('hi', 'ひ').replace('fu', 'ふ').replace('he', 'へ')
    text = text.replace('ho', 'ほ').replace('ma', 'ま').replace('mi', 'み')
    text = text.replace('mu', 'む').replace('me', 'め').replace('mo', 'も')
    text = text.replace('ra', 'ら').replace('ri', 'り').replace('ru', 'る')
    text = text.replace('re', 'れ').replace('ro', 'ろ')
    text = text.replace('la', 'ら').replace('li', 'り').replace('lu', 'る')
    text = text.replace('le', 'れ').replace('lo', 'ろ')
    text = text.replace('ya', 'や').replace('yu', 'ゆ').replace('yo', 'よ')
    text = text.replace('wa', 'わ').replace('wyi', 'ゐ').replace('wu', 'う')
    text = text.replace('wye', 'ゑ')
    text = text.replace('wo', 'を')
    text = text.replace('nn', 'ん').replace('m', 'ん')
    text = text.replace('tu', 'つ').replace('hu', 'ふ')
    text = text.replace('fa', 'ふぁ').replace('fi', 'ふぃ').replace('fe', 'ふぇ')
    text = text.replace('fo', 'ふぉ').replace('oh', 'おお')
    text = text.replace('l', 'る').replace('-', 'ー')
    text = text.translate(HEP2KANA)
    ret = []
    consonants = frozenset('sdfghjklqwrtypzxcvbnm')
    for (i, char) in enumerate(text):
        if char in consonants:
            char = 'っ'
        ret.append(char)
    return ''.join(ret)

# End of code adapted from jaconv.
############################################################


############################################################
# widgets and layouts with custom styles
class zQVBoxLayout(QVBoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSpacing(0)
        self.setContentsMargins(0,0,0,0)

class zQHBoxLayout(QHBoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSpacing(0)
        self.setContentsMargins(0,0,0,0)

class zQGroupBox(QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
            QGroupBox {
                border: none;
                font-weight: bold;
                padding: 1.4em 0.2em 0em 0.2em;
                margin: 0;
            }"""
        )

class zQTextEdit(QTextEdit):
    kanji = None
    kanji_click = pyqtSignal(str)
    app = None
    _ov_cursor = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kanji = ''
        self.app = QCoreApplication.instance()
        self.setMouseTracking(True)

    def _override_cursor(self):
        if not self._ov_cursor:
            self._ov_cursor = True
            self.app.setOverrideCursor(Qt.WhatsThisCursor)

    def _restore_cursor(self):
        if self._ov_cursor:
            self._ov_cursor = False
            self.app.restoreOverrideCursor()

    def mouseMoveEvent(self, event):
        scr = self.verticalScrollBar().value()
        old_tcur = self.textCursor()
        cwidth = QFontMetrics(QFont(cfg['lfont'], cfg['lfont_sz'])).horizontalAdvance('範')
        tcur = self.cursorForPosition(QPoint(event.pos().x() - cwidth/2, event.pos().y()))
        self.setTextCursor(tcur)
        char = ''
        if not (tcur.atBlockStart() and event.pos().x() - self.pos().x() > cwidth):
            tcur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor);
            char = tcur.selectedText()
        self.setTextCursor(old_tcur)
        self.verticalScrollBar().setValue(scr)
        if _is_kanji(char):
            self.kanji = char
            self._override_cursor()
        else:
            self.kanji = ''
            self._restore_cursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.kanji and len(self.textCursor().selectedText()) < 1:
            self.kanji_click.emit(self.kanji)
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.kanji = ''
        self._restore_cursor()
        super().leaveEvent(event)


############################################################
# Icons

class sQPixmap(QPixmap):
    def __init__(self, *args, imgdata=None, **kwargs):
        super().__init__(*args, **kwargs)
        if imgdata is not None:
            super().loadFromData(base64.b64decode(imgdata))

class jpIcon:
    """ Icon resource storage with only class attributes, not instantiated."""
    initialized = False
    add_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAz1BMVEX///87a6g2Z6U1ZqU3Z6QzY6I6aKQxXp0rWJYrWZYwX50nUpAsWpgjTYoqV5QpVJIoVZImUo4hSockT4oiS4gmUYypwNymvdo0ZaSkvNl7nsgzZKOWsdJnjb0wYJ8xYaCGpMpTfbMsWpgrWZd5
msN/n8d9ncV6msRcg7c+baltkL50lsFylMBmirlojbw1ZqQ1ZqU3aKY5aqg7bKk9bao/b6xBca1AcKsnU5EmUo92mcVKebMhTIkhS4iIqdBYh70gSoeTs9dnlMeQsddrl8m84eAJAAAAFnRSTlMAgfv7gfv39/uB+/v7+4H79/f7gfuBOt2MIAAAAHNJREFUGNNjYCAS
MDIxMaIIMIuJM6MISEhKSaAISMvIysE5LKzycmwKiuxKyhycYAEuFVU1dQ1NLW0dXW6wAI+evoGhkbGJqZk5L1iAj9/CUsDKWtDGVkgYbo6Nnb0Dii0Ojk6oAiLOLiIoAqIiIqLEehMA974KdF73TRoAAAAASUVORK5CYII=
"""
    apply_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABDlBMVEX///8ATwAATAAASQAATQAOaAsBWwEATgARaw4AWwAATgASaxAEUwQATAAVaxITZBIATAAshCMEUwQAVQAXaRUJXwcATQAOaAwDUgMXZhUQXA0ASwACUAIYXRQATgACTgIXVhECTgIaVBIATQAC
TQIcUBQCSAIcUBEATAAATQAATgB2tWOay3u26qF5uGGTxnCZ0pCZ0I+QwW+m0HdYoEKRxWmJxnuIwnqQvWuayGhztGSTyGpZn0GOxGB/wGh7u2aWw2xKjTCKwVtksVCPyVxbnD+KwVd3wFV2vFmdyW1OizGDwkpQrCqCxkVkujJdsi2JvUtOgi1/yDVHug5XwhiOx0RU
gy2R3j6Y1UdNfSlq55gUAAAAK3RSTlMAHXIOIe3YDeu8bPWRG+nWa/6QGOf1MtuV5vYzjfc0mvmd+TWg+qP6NkYkIiPNwAAAAIJJREFUGNNjYCAFMDIxo/BZWLXZ2JHlOXR09ThBLC5uHiDJy6dvYGjED2QJCBqbCDEIi5iamVuIigEFxC2trG0kJG3t7B2kpEE6ZByd
nF1c3dw9PGXlIKbJe3n7+Pr5ByjIwcxXDAwKDglVUkbYqBIWHqGqjOwmtUh1DVRXa2oR70MAwogP6KXmWqMAAAAASUVORK5CYII=
"""
    cancel_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABv1BMVEX////////Pe3u4PDymAgKyJCS1MTGrERG4PT2/WVmoDw+mDw+mEQ+jCgnJe3ueDw+TCgiaBASmCQmtDg65FBOqPDyRDAqUCwuqCwu3GRieIyOUBASmCwu3GhmSCwudCgq0FhWLCQegAACOCwug
CwuxFBKKCQedAACmAACSIyOxFhSKBgKZAACjCwuXPDyHBgKUAACgCwu5GxS9e3uCDg6IAgKUCAiiDQ27HxWhWVmCBQKdWVl4Dg6xe3uKPDxrAAB3DQ15EBBsAQG7SEfMc3PYiorZi4vNdna5QkLJb23QeXewNzelHByuJSO8SUbLcG/CY2G/XVq/V1S5SkbAYWG5U1Cr
KyXCYF7BU06+U1OxSES0TUuqKyavPjelMSvMYVnFRka4PzqGBwWcJiKsOzaqQzqcHhfOUkrMNzfEOjScFRCTHhaMEgmaEgu+HxTLFRXGHRSlEw2QDQSREQWcEgi1FAjHAADLDQSuFgyaEQWXEQWWBQKuGwq8AADIDgWrBgKcEAWfFwiqAAC/FQeACAO/DgarFwiqGgi+
CAO+EwaxFQq8GQ/OHA3QCgO2GQieFQe4GwjMGwnSHArAHAqjFgdfTWjIAAAAQ3RSTlMAAirVzfr70dWT+Pj+/ir47XQcNfDV7hcX3e12Ft75Gd79Z/ku3v1bF+3y/Vtw1f1bF/Aq+HQedvGT/pP4KtXN+fnNf0ybtwAAANpJREFUGNNjYIAARkYGJMDEzMLKxs7BBONz
cjm7uLq5e3BzQvk8nl7ePr5+/gG8YBE+/sAgAUEhYZHgkFB+PqCAaFi4mDiDhGREZFR0jChQQCo2TppBRjY+ITEpOUUKaJ9capq8jEJ6RqaiUla2HCMDo3JOropqXn6BmrpGYZEy0DmaxSVapWXl2joMuhWVmkAz9Kqqa2rr9A0YDI3qG/SAAsYmjU3NLaZm5hatbSbG
IIdYWrV3dHZ19/T2WVlCnGpt0z9h4qTJU2ysYZ6xtbN3cHSys0X2MNz7AP4nLgM0DCzVAAAAAElFTkSuQmCC
"""
    clear_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABblBMVEX///+OWQSUXwiQWgOTXgiSWgOYYguRWwWSWwCTXQaVXwqSXAawfCmWYAqPWATXwhHTvQ6WYgeibhrMzMzfyye5ii6VXgiAgADaxL3WwBLTuQ///wDjxhzaxRXZxR/hzoPXwxDXwg/XvA3ZxBTk
0jHZxE6/vwDbyBLZxBTo1zzZxTHPvxDZxRTm1DbZxBPZxBTj0C/YwxDZxBPXwxHMzADZxBHXwhHZxRXizy3axBjaxRXWxRDWwhDZxBTWwhDaxh7n1TrYwxHVxBLYxBTZwxPXwxDWxA67jEHbql3Wpld5VyLFk0TpuW7aql/aqVzouG3YwhbWwRLfwDPaxcnr2af36HPp
10Deys3bx9bn1bLs22n77W7973L77HLw4Jjhzcbaxtj252D87m/042D05Fru3kz77G/t2FHfyyP87nDu21Du2lT25l/s2kXy4lXj0S/m0EPx4Fzp1z777W3lz0P25mXdyR3kzT7y41nXwg/EU0iUAAAAR3RSTlMASNT9h2D09g7vtoX39EC4XfD0Bfb5wAKL/nUBCav3
/P55E9X1owQO1/n5EMv3+L72+Pz5BTz3+vX3yh995fX5+HsrnO/7OErIQ6MAAACxSURBVBjTY2BAAEYmZhYkLgMrm7sHOxKfg9PTy5sLSYCbx8eXlw/O5RcQ9PMX4obzhQNEAoNExcThAhLBIaFhklLSUK6MrJx8eERklIIihK+krBIdExsXn6CqBuara2gmJsUkx8Ro
aUPU6+impMakpcfE6EEE9A1SMjIzs7JzYAKGuUZ5mfkFhUXFxiZgAVMz8xQLy5LSsjwrqKXWNrZ29uUVlQ6OCH84Obu4Vla6gZgANr4i/9Y42v8AAAAASUVORK5CYII=
"""
    close_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAACSVBMVEUAAACEAACOAACTAACUAACQAACLAAB9AACLAACUAgKZCQmNAACGAAB+AACOAACSAACIAABMAACNAACSAACDAACFAACLAAAAAAAAAACPAACVAAB5AABgAACZAACKAAB6AACQAABzAACVAAAcAACo
AACLAAAAAACgAACrAAAgAAByAAC1AACbAAAAAAAAAACZAACwAAAQAAAAAACaAADAAACxAAAyAAAAAABlAACrAAC6AAC8AACzAACIAAAAAAAAAAAqAAA3AAACAAAAAACwNTXFYGDHZWW3RESqHR3biYnnp6fop6fimpq3NTWrERHafXreiYLhi4PhioThh4TfhITbgYHc
gYG4KSmeAADKSELRf2725eLUi3fbfF/ceGDMbWLy29vUiIjNVFSnAwOvAwLPWDrMkn/////58/HEeVi+ZD/u29bctbK+ODe5EBC5CQDRRAfGVRHEknn38e7q2tTXuLCxNhXFIAy7AgCgAAC9EADSRQDaXwDBXAC2jX/TvrmlQAXSSgDLLwC/DQCnAACmAAC+DQDQQQDW
XACxWBLj08307u2tYjLRWQDRQgDCFgCsAAC3BADHMQC1SRLo1s3hx63NpHf28O27aDLMSgC9EQCtAACxAACzFQDMi3jmxq3JbgXUfADaqnPnyri5NwCzAwCuAgCsGwHQgma/TQXOYQDUbADOaQDal1zCVBCxEAC0AAC6AACrAgCqEwCzLAC7PgDASgDBSwC4NgCsCwC2
AACyAACnAgClCQClCwCnBgCvAAC/AAC7AAB8252hAAAARHRSTlMADlF5fV8dC4n0/aseFs7sNwTC6htlowEDzvkUFv5RMW0taBD0Pway5QtC+3UCCIi6DQ6I+rAYCkew7PTBXgweMjYgD4hci68AAAECSURBVBjTY2AAAUYmZhZWNgYYYOfgdHF1c+fi5oHwefk8PL28
vb19fPkFQHxBIT//gMCg4JDQsHBhEaCAaERkVHRMbFx8QmJSspg4g4RkSmpaekZmVnZ6Tm6elDSDjGx+QWFRenFJemlZeUWlHIN8ZVV1TW1denp9Q2NTc4sCg2JrW3tHZ1d6endPb1//BCUGZZWJkyZPSZ86LX36jJmzZqsyqKnPmTsvff6ChYvSFy9ZqqHJIK6lvWz5
ipWrVq9Zu279Bh1dBgY9/Y2bNm/Zum37jp27DAxBTjUyNtm9Z+++/QcOmpqJgz1jbmFpdWijtY2tkTjUu7p29g6OTs4SIDYAHdlQzb5sNMYAAAAASUVORK5CYII=
"""
    down_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAArlBMVEX///+OkIyLjYiIiISIioWIiYWIiIWIi4WIiYWHioWDhoGQko2DhoCEhoF/gX2LjYmAgHx/gXx6eneFh4KHiYR5fHZ6fnd2dnOAgn6ChIB1d3Nwc218fXpqbWp3eXVnZ2RzdHFhZF5ucG1cX1ld
X1pYWFj////f393w8e/u7u3R0s/X2NX5+fn09PPV1dLd3dvz8/Pc3drz8/Lc3NmMjorb29j9/f3a2tj29vS/wL0NviM0AAAAJnRSTlMAgfQ6y8FHS9nCwvtUy9n7VMFL+/tUR1T7+5BU+1T7VPtU+1b4HR8aBOoAAACTSURBVBjTZY7ZDoJADEXL4A4KCgjIDu6UbRDR
//8xyQQNI/epaU9uDwCLQATgQs6EX4yIUQaEOJnO+o75YikCrC5XSWaELN3ua4BNipmidqiqZJhvAXZagaVugKGXWGj77mJaFVL7YFOsLJPVOm6N9EGxdp3+kec3+MTG934WQdi+2jAYeEXxO4440+SY/LmfvsMH9skMA/2RG/8AAAAASUVORK5CYII=
"""
    find_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAB/lBMVEX///8rZbYuZrczabgvZ7cpYK0vYq5ogsiUqNcvZbApYa4nXKUyYaouOm4XH0oTGkEsN2NDb7AkV50oWZ9JVZciK2MjMFY9QlNlanQqNlUZIk9eZpYqWp8lV50kU5VKZasoMnEzNUBmZmbc3Nv6
+vrp6elQVFwhKV5xh74lVJYmUY83Q4orOGZgYGCfm5vY2NP6+vrx8fGNjY0nM1w3RIAhSoU1PYgzN06BgX7RyMjd3czf38/UzMwxNkotNnkhSoYfRX04QY83PVWNjYnb287b29s3O1EyOoIfRn4fQ3c8SJYxPXGHh4PVysrq6tUuOmo7R48bPnA1TIg8RphaYHGqqqXT
09NaYG43QI1CVpIbPm8ZPW4cPnBDT54+SJ4/TYddZ4s/TIY6RZZHUp0dPGocHiEZPW4eP3JATKFBS6VBSqQ/TJ4kIBwZFhMbPnAxR4QySIUbO2kzQlQgHBkZFhMaPW8dPnEbPnAZGx8aFxQyMzN0bmUcGBUZFhMZFhMrKCMZFhMZFhMZFhOXod22uOrExu68wuiEjdJ0
e7qeo8PY3PB3gcm9wuVja7OLkL9ib7aRmc9qcLuXmtZka7WJjc1RXaJqc7ZQWqRdZa5NV55bZKxKVJxMVqNQWqdSXKQjQ3RwdHtEUZZQV6JRWKRHU5pxbmqGf3Vua2VEPjcZFhO4OR1PAAAAg3RSTlMADn/D8kLq+vvqQkL1+/7+/PUO6vz8toybufz96g5/+fyBWpPn
y4z8+n/D+7ZdOCyfqnK2/PL+jkkcDxAejv7y8v6KQRUHiv7yw/u1RhgMtft/+PxmMBdm/fx/Dur7/Ktlq/3+/mRC9Pv+/vv2Rur4/P378zV/w/Jt7O/97Ujr4TDj4DJK+8EAAADtSURBVBjTY2BgYGBkYmZhYWZiZIACVjb25pbWNg5OLgifm6e9g5ePX6CzS5AbxBcS
7hYRFROXkJSS7pGRBQrIyfcqKCopq6iqqfdpaAIFtPq1dXT19A0MjYxNJmgBBUwnmplbWFpZ21jY2k2yBwo4THZ0cnZxdXVxdnOf4gEU8Jzq5e3j6+fn6+MfMM0TKBAYND04JDQsLDQ8YkZkFFAgOmZmbFx8QkJiUvKslFSQQ9LSZ8/JyMzKnjtv/oKcXLBIXv7CRYuX
FBQWLV1WXAISiS4tKy8vK62orFpeXcOABGrr6lesRBZgaGhc2QQAcnU+aPmKi2wAAAAASUVORK5CYII=
"""
    jiten_pai_png = """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
"""
    ok_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABDlBMVEX///8JIzUJHToAEjcIHz4WM1oOJ00AFDsaNVwMJUsJHzsdOV8OIUMJHDkdNVoeN1kKHTkvTXYOIkILIDUdNVYVMFcGHDcZMVUOIj8aMk0aNFYFHjcLHz8cNVMFGzcKHj0aMUYJGjwLIDsXMEAI
GzsMHjoYMT4HGjoAAAALHzcbND8HHzoKHTpph6h9mrWryt5ig6VwjKiUsshvi6h0kalEYINifpp/m7J+m7Jng59depZnhJ1lgZs7VG9VcYdphZ5ifZgsSGlRa4dbd5RgfZo1TFpNanpmgZ9kgJxje5MtRl1PaolUcJNadpdbdptWcJREX3kqRFNSb5ZffKhigKxQbYkz
TFd0lL1oiKY2Ul62MpKDAAAALXRSTlMAHXIOIezYDeq8bPWRG+jUa/6QGOfzLtqW5/Uzjvc4oPk8qPtBsPxGAbb8S2r7wD5BAAAAhElEQVQY02NgIAUwMjGj8FlYddnYkeU59PQNOEEsLm4eIMnLZ2hkZMwPZAkImpgKMQiLmJlbWIqKAQXEraxtbCUk7eytHaSkQTpk
HJ2cXVzd3D08ZeUgpsl7efv4+vkHKCjCzFcKDAoOCVVWQdioGhYeoaaO5AQNzUgtbRRHaugoMhANAOfbEF197TngAAAAAElFTkSuQmCC
"""
    open_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAB41BMVEUAAABUf7UAAAAAAAAAAAAAAAAJCQlUf7UqKinExMRYh8KTsctKdaZFX4AAGDgAEzMAFDMAEzIAEzIAEzEAEzEAEjAAEjEAGz0oTHb////o5+dKc6dRcpv29vb4+Pj5+Pj19PTr6+v///47UWpR
frhUg7xUgbs9ZJJKapD5+fnv7u6goKDk4d5OYXd4otd8qeFJdq0vUno+Xof49/f39/fy8vKamprx7+/h3ds3T21olM0wUnsrS3H19fWhoKD//PpGXXkqS3MlRmohQ236+fn7+/q4uLi0s7OtrKyysLD08vAOKkoiQWQRNF77+vr6+frf4eXP09jO0tbMz9XJzdHGyM7B
xMrg4uUAFDEYOVsAHkXo6OrO0dXQ0ta1u8OHor6nzeuozeqpzeuozeuqzuu84PxPdp+84PunzOqmy+mmzOqozuuqzuqFq9qCpteAptd/pteHreFIXXhQeamDqdx8o9Z9o9Z+o9aBptiAp9iCp9iBp9iHruFJX3tReqqKruCDqduGqduHqduFqduEqduEqdqJseRKX3w5
Z5tAdrQ/dLBAdLBDerknRGZYf62Hrd+FqdqGqdqDqdqKsONQZIGBqN19o9h+pNh8o9h4o9l8o9l+pNl+o9l5o9l6o9h+o9iBqeD0enAlAAAAGHRSTlMAAANJSz0IyZb+1bq5r0F6e3x9fn+Bf0Lax4JAAAABAElEQVQY02NgYGJmAQFWNgYIYJeQBAMpDjCXkUFaRlJW
Tl5BkVNJWUVVjYuBQV1DUk5OU1ZLW1JHV0/fgIHB0EjSWFPTxNRM0tzC0sqagcHGECQgZ2sHNMfewZGBwclZ0kTOxdVF0c3dw9PLm4HBx1dSzs8/IDAoOCQ0LDyCgSEyKjomNi4+ITEpOTk5JZWbIS09IzMrOyc3L78gLz+/sIihuKS0rKy8vKKysrKqurqmlqGuvqGh
saGpuQVINra2tTN0dHYBQTcQgkBPL0Nff+uEiRNaQcSkCa2TpzDwTJ02fcbMWbNnz5k7b/r8BbwMfPwCgkLCIqKiYsJCggL84gBhOUmZU0MiDgAAAABJRU5ErkJggg==
"""
    properties_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABFFBMVEUAAADX2dLU19DV2dHT18/l5uLV2dHk5+LW2NLP08vP08zLz8fM0MjHy8PIzMTDxsDEx8HAwr3Bw729wLm8v7i6vbZtbW18fXmAgGCysq95eXRVVVXAwruztbD09PKurq7T18/////4+fj29vXR
08739/bO0Mu6vbbY2tX5+fj6+vn7+/vKy8mWmJSeoJvd3tz8/Pysraq8vbrs7eyfoJzh4eD9/f3P0M6rramrrKnP0M3w8fCjpKCUlpKztLCnqKSho5+YmpaWmJPb29jExcKen5vq6+rs7OyZmpbg4N+Qkozn5+Xo6Ob19fO4ubehop6XmZaNj4uQkY60tbK2t7T6+vqy
s6+UlpOwsa3z8/C3urOOkYsDQHnnAAAAIHRSTlMAt/qA/veF+Hz++f7+/v7+/v7+/v7+B8YIvXADtd5hLL2kwkcAAACrSURBVBjTRchne8FgGAbQl1JVtBS1xy1a46Vi79FhS42I+f//B9eThPPxMGaIq4wPTGWCKmF+1EMgSVieKKz4IJ+p9DOFDRkN7BQOZDV4oXgF
5zyX/ypwOClcEEWxWCpXqnijcKNWb6DZanfgpvAA3V4fA/4Njx4/v3/D0XjCbzGdzYWF9L/06oHqar2Rpe36XY8rZbWTZJ//HlD2h2MgGGIsnNKczpFojF0AMAwfwZNd88EAAAAASUVORK5CYII=
"""
    remove_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAk1BMVEX///83Z6QzY6IrWJYrWZYwX50nUpAsWpgjTYoqV5QpVJIhSockT4oxYaAwYJ8vX50vXpwuXZstW5osWpgrWZd5msN/n8d9ncV8m8V6msR4mcN2l8J0lsFylMBmirlojbw1ZqQ1ZqU3aKY5aqg7
bKk9bao/b6xBca1AcKsnU5EmUo8lUY4kT40jTowiTYohTIkhS4icB0FQAAAADXRSTlMAgfv7gfv7+/uB+/uBIADwiwAAAERJREFUGNNjYKATYGTi5eMXEBQSFmFmAQuwioqJS0hKScvIyrGBBdjlFRSVlFVU1dQ1OMACnFyaWto6unr6Btw89HImAFPMBJlfhBn2AAAA
AElFTkSuQmCC
"""
    up_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAAhFBMVEX///+Ii4WIioWJiYaTlZGRk4+IioWFhYGQko2OkIuDhoCFhYF/gXyJi4eAgHx/gX16fHeFh4J5fHaOkIyLjYh6fHh3d3J1eHJ2d3N0d3R3d3N2d3N1d3Tj4+H09PP9/f35+fnv7+3f4N2cnZjf
39ze3tv4+Pfa29jJysfV1tPT09D///8aLa7GAAAAHXRSTlMAVvhU+/uQR/v7VEvB+1TZy/tUgfTCOsLZS0fBy7E7NWcAAAB6SURBVBjTfY3ZDoIwFAUP+yZooSIK1CsURf3//7NtwhYT5m3mnrSAwbItrHHc1nU2Lu5iVZTTg5aiveu7uRj3fG8qQShIRjHiSJIIE+DQ
0pBm6pKlw/N1BE7jm+UoeIGcfcYzUF6qK8C/HLjVTTn9rBf7/C3MG7uLhR8SHQiljWH7zAAAAABJRU5ErkJggg==
"""
    def __new__(cls):
        if cls.initialized:
            return
        cls.initialized = True
        jpIcon.add_pxm = sQPixmap(imgdata=jpIcon.add_png)
        jpIcon.add = QIcon(jpIcon.add_pxm)
        jpIcon.apply_pxm = sQPixmap(imgdata=jpIcon.apply_png)
        jpIcon.apply = QIcon(jpIcon.apply_pxm)
        jpIcon.cancel_pxm = sQPixmap(imgdata=jpIcon.cancel_png)
        jpIcon.cancel = QIcon(jpIcon.cancel_pxm)
        jpIcon.clear_pxm = sQPixmap(imgdata=jpIcon.clear_png)
        jpIcon.clear = QIcon(jpIcon.clear_pxm)
        jpIcon.close_pxm = sQPixmap(imgdata=jpIcon.close_png)
        jpIcon.close = QIcon(jpIcon.close_pxm)
        jpIcon.down_pxm = sQPixmap(imgdata=jpIcon.down_png)
        jpIcon.down = QIcon(jpIcon.down_pxm)
        jpIcon.find_pxm = sQPixmap(imgdata=jpIcon.find_png)
        jpIcon.find = QIcon(jpIcon.find_pxm)
        jpIcon.jiten_pai_pxm = sQPixmap(imgdata=jpIcon.jiten_pai_png)
        jpIcon.jiten_pai = QIcon(jpIcon.jiten_pai_pxm)
        jpIcon.ok_pxm = sQPixmap(imgdata=jpIcon.ok_png)
        jpIcon.ok = QIcon(jpIcon.ok_pxm)
        jpIcon.open_pxm = sQPixmap(imgdata=jpIcon.open_png)
        jpIcon.open = QIcon(jpIcon.open_pxm)
        jpIcon.properties_pxm = sQPixmap(imgdata=jpIcon.properties_png)
        jpIcon.properties = QIcon(jpIcon.properties_pxm)
        jpIcon.remove_pxm = sQPixmap(imgdata=jpIcon.remove_png)
        jpIcon.remove = QIcon(jpIcon.remove_pxm)
        jpIcon.up_pxm = sQPixmap(imgdata=jpIcon.up_png)
        jpIcon.up = QIcon(jpIcon.up_pxm)


############################################################
# 'About' dialog

class aboutDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle('About')
        self.resize(600, 500)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(jpIcon.jiten_pai_pxm)
        self.tag_label = QLabel('%s %s\n'
                                'Copyright (c) 2021, Urban Wallasch\n'
                                'BSD 3-Clause License\n'
                                'Contributors: volpol'
                                % (_JITENPAI_NAME, _JITENPAI_VERSION))
        self.tag_label.setAlignment(Qt.AlignCenter)
        self.tag_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hdr_layout = QHBoxLayout()
        self.hdr_layout.addWidget(self.icon_label, 1)
        self.hdr_layout.addWidget(self.tag_label, 100)
        self.info_pane = QTextBrowser()
        self.info_pane.setReadOnly(True)
        self.info_pane.setOpenExternalLinks(True)
        self.info_pane.viewport().setAutoFillBackground(False)
        self.info_pane.setStyleSheet('QTextEdit {border: none;}')
        self.info_pane.setHtml(_JITENPAI_INFO)
        self.qt_button = QPushButton('About Qt')
        self.qt_button.clicked.connect(lambda: QMessageBox.aboutQt(self))
        self.ok_button = QPushButton('Ok')
        self.ok_button.setIcon(jpIcon.ok)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        self.btn_layout = QHBoxLayout()
        self.btn_layout.addWidget(self.qt_button)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.ok_button)
        self.dlg_layout = QVBoxLayout(self)
        self.dlg_layout.addLayout(self.hdr_layout)
        self.dlg_layout.addSpacing(20)
        self.dlg_layout.addWidget(self.info_pane)
        self.dlg_layout.addLayout(self.btn_layout)


############################################################
# 'Preferences' dialogs

class dictDialog(QDialog):
    name = ''
    path = ''
    def __init__(self, *args, title='', name='', path='(none)', **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.path = path
        self.init_ui(title, name, path)

    def init_ui(self, title, name, path):
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(title)
        self.resize(200, 120)
        self.name_edit = QLineEdit(name)
        self.name_edit.setMinimumWidth(300)
        self.name_edit.textChanged.connect(self.name_chg)
        self.path_edit = QPushButton(path)
        self.path_edit.setStyleSheet("QPushButton {text-align: left; padding: 0.2em;}");
        self.path_edit.setIcon(jpIcon.open)
        self.path_edit.setMinimumWidth(300)
        self.path_edit.clicked.connect(self.path_chg)
        form_layout = QFormLayout()
        form_layout.addRow('Name: ', self.name_edit)
        form_layout.addRow('File: ', self.path_edit)
        add_button = QPushButton('&Apply')
        add_button.setIcon(jpIcon.apply)
        add_button.clicked.connect(self.accept)
        cancel_button = QPushButton('&Cancel')
        cancel_button.setIcon(jpIcon.cancel)
        cancel_button.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(add_button)
        btn_layout.addWidget(cancel_button)
        dlg_layout = QVBoxLayout(self)
        dlg_layout.addLayout(form_layout)
        dlg_layout.addLayout(btn_layout)

    def name_chg(self):
        self.name = self.name_edit.text()

    def path_chg(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Open Dictionary File',
                            os.path.dirname(self.path),
                            options=QFileDialog.DontUseNativeDialog)
        if fn:
            self.path_edit.setText(os.path.basename(fn))
            self.path = fn

    def accept(self):
        if not os.path.exists(self.path):
            mbox = QMessageBox(self)
            mbox.setWindowTitle('File Open Error')
            mbox.setIcon(QMessageBox.Critical)
            mbox.setStandardButtons(QMessageBox.Ok)
            mbox.setText('Dictionary file not found!')
            mbox.exec_()
            return False
        if not self.name:
            mbox = QMessageBox(self)
            mbox.setWindowTitle('Name Error')
            mbox.setIcon(QMessageBox.Critical)
            mbox.setStandardButtons(QMessageBox.Ok)
            mbox.setText('No name supplied for dictionary.')
            mbox.exec_()
            return False
        super().accept()


class prefDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_ui()

    def init_ui(self):
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle('Preferences')
        self.resize(600, 700)
        # fonts
        fonts_group = zQGroupBox('Fonts')
        self.nfont_button = QPushButton('Normal Font')
        self.nfont_button.setToolTip('Select font used in explanatory result text.')
        self.nfont_button.setMinimumWidth(130)
        self.nfont_button.clicked.connect(lambda: self.font_select(self.nfont_edit))
        self.nfont_edit = QLineEdit(cfg['nfont'] + ', ' + str(cfg['nfont_sz']))
        self.nfont_edit.setMinimumWidth(300)
        self.nfont_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lfont_button = QPushButton('Large Font')
        self.lfont_button.setToolTip('Select font used for headwords in results.')
        self.lfont_button.setMinimumWidth(130)
        self.lfont_button.clicked.connect(lambda: self.font_select(self.lfont_edit))
        self.lfont_edit = QLineEdit(cfg['lfont'] + ', ' + str(cfg['lfont_sz']))
        self.lfont_edit.setMinimumWidth(300)
        self.lfont_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.color_button = QPushButton('Highlight Color')
        self.color_button.setToolTip('Select color used to highlight search terms in results and property names in KanjiDic.')
        self.color_button.setMinimumWidth(130)
        self.color_button.clicked.connect(lambda: self.color_select(self.color_edit))
        self.color_edit = QLineEdit(cfg['hl_col'])
        self.font_sample = QTextEdit('')
        self.font_sample.setReadOnly(True)
        self.font_sample.setMinimumSize(450, 50);
        self.font_sample.setMaximumSize(9999, 70);
        self.font_sample.resize(400, 50);
        fonts_layout = QFormLayout(fonts_group)
        fonts_layout.addRow(self.nfont_button, self.nfont_edit)
        fonts_layout.addRow(self.lfont_button, self.lfont_edit)
        fonts_layout.addRow(self.color_button, self.color_edit)
        fonts_layout.addRow('Font Sample:', self.font_sample)
        # search options
        search_group = zQGroupBox('Search Options')
        self.dict_load = QCheckBox('&Load Dictionary on first use')
        self.dict_load.setToolTip('Trade increased memory usage for faster dictionary lookup.')
        self.dict_load.setChecked(cfg['dict_load'])
        self.search_deinflect = QCheckBox('&Verb Deinflection')
        self.search_deinflect.setToolTip('Enable search heuristic for possibly inflected verbs or adjectives.')
        self.search_deinflect.setChecked(cfg['deinflect'])
        self.search_deinflect.setEnabled(_vconj_loaded)
        search_layout = zQVBoxLayout(search_group)
        search_layout.addWidget(self.dict_load)
        search_layout.addWidget(self.search_deinflect)
        search_layout.addSpacing(10)
        # kanjidic options
        kdic_group = zQGroupBox('Kanji Dictionary')
        file_icon = self.style().standardIcon(QStyle.SP_FileIcon)
        self.kdic_button = QPushButton(file_icon, cfg['kanjidic'])
        self.kdic_button.setToolTip('Select location of kanjidic file.')
        self.kdic_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.kdic_button.clicked.connect(self.kanji_dict)
        kdic_layout = zQVBoxLayout(kdic_group)
        kdic_layout.addWidget(self.kdic_button)
        kdic_layout.addSpacing(10)
        # dicts
        dicts_group = zQGroupBox('Word Dictionaries')
        self.dict_list = QTreeWidget()
        self.dict_list.setAlternatingRowColors(True)
        self.dict_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dict_list.setRootIsDecorated(False)
        self.dict_list.setColumnCount(2)
        self.dict_list.setHeaderLabels(['Dictionary File Path', 'Dictionary Name'])
        self.dict_list.itemDoubleClicked.connect(self.edit_dict)
        self.dict_list.itemSelectionChanged.connect(self.dict_list_sel_chg)
        self.dicts_add_button = QPushButton('&Add')
        self.dicts_add_button.setIcon(jpIcon.add)
        self.dicts_add_button.clicked.connect(self.add_dict)
        self.dicts_remove_button = QPushButton('&Remove')
        self.dicts_remove_button.setIcon(jpIcon.remove)
        self.dicts_remove_button.setEnabled(False)
        self.dicts_remove_button.clicked.connect(self.remove_dict)
        self.dicts_up_button = QPushButton('&Up')
        self.dicts_up_button.setIcon(jpIcon.up)
        self.dicts_up_button.setEnabled(False)
        self.dicts_up_button.clicked.connect(self.up_dict)
        self.dicts_down_button = QPushButton('&Down')
        self.dicts_down_button.setIcon(jpIcon.down)
        self.dicts_down_button.setEnabled(False)
        self.dicts_down_button.clicked.connect(self.down_dict)
        self.dicts_prop_button = QPushButton('&Properties')
        self.dicts_prop_button.setIcon(jpIcon.properties)
        self.dicts_prop_button.setEnabled(False)
        self.dicts_prop_button.clicked.connect(self.edit_dict)
        dicts_button_layout = zQHBoxLayout()
        dicts_button_layout.addWidget(self.dicts_add_button)
        dicts_button_layout.addWidget(self.dicts_remove_button)
        dicts_button_layout.addWidget(self.dicts_up_button)
        dicts_button_layout.addWidget(self.dicts_down_button)
        dicts_button_layout.addWidget(self.dicts_prop_button)
        dicts_layout = zQVBoxLayout(dicts_group)
        dicts_layout.addWidget(self.dict_list)
        dicts_layout.addLayout(dicts_button_layout)
        # dialog buttons
        self.cancel_button = QPushButton('&Cancel')
        self.cancel_button.setIcon(jpIcon.cancel)
        self.cancel_button.setToolTip('Close dialog without applying changes')
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button = QPushButton('&Apply')
        self.apply_button.setIcon(jpIcon.apply)
        self.apply_button.setToolTip('Apply current changes')
        self.apply_button.clicked.connect(self.apply)
        self.ok_button = QPushButton('&Ok')
        self.ok_button.setIcon(jpIcon.ok)
        self.ok_button.setToolTip('Apply current changes and close dialog')
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        button_layout = zQHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.ok_button)
        # dialog layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(fonts_group)
        main_layout.addWidget(search_group)
        main_layout.addWidget(kdic_group)
        main_layout.addWidget(dicts_group)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        self.update_font_sample()
        for d in cfg['dicts']:
            item = QTreeWidgetItem([d[1], d[0]])
            self.dict_list.addTopLevelItem(item)
        hint = self.dict_list.sizeHintForColumn(0)
        mwid = int(self.width() * 2 / 3)
        self.dict_list.setColumnWidth(0, mwid)
        self.dict_list.resizeColumnToContents(1)

    def dict_list_sel_chg(self):
        en = len(self.dict_list.selectedItems()) > 0
        self.dicts_remove_button.setEnabled(en)
        self.dicts_up_button.setEnabled(en)
        self.dicts_down_button.setEnabled(en)
        self.dicts_prop_button.setEnabled(en)

    def font_select(self, edit):
        font = QFont()
        try:
            font.fromString(edit.text())
        except:
            font.fromString('sans,12')
        t = QFontDialog.getFont(QFont(font, self))[0].toString().split(',')
        edit.setText(t[0] + ', ' + t[1])
        self.update_font_sample()

    def color_select(self, edit):
        color = QColor()
        color.setNamedColor(edit.text())
        color = QColorDialog.getColor(color, title='Select Highlight Color')
        if color.isValid():
            edit.setText(color.name())
            self.update_font_sample()

    def update_font_sample(self):
        font = QFont()
        font.fromString(self.nfont_edit.text())
        f = font.toString().split(',')
        nfmt = '<div style="font-family: %s; font-size: %spt">' % (f[0], f[1])
        font.fromString(self.lfont_edit.text())
        f = font.toString().split(',')
        lfmt = '<span style="font-family: %s; font-size: %spt;">' % (f[0], f[1])
        hlfmt = '<span style="color: %s;">' % self.color_edit.text()
        html = [nfmt, lfmt, '辞', hlfmt, '典', '</span></span>',
               ' (じてん) (n) dictionary; lexicon; (P);', '</div>' ]
        self.font_sample.setHtml(''.join(html))

    def apply(self):
        def font_parse(s):
            font = QFont()
            font.fromString(s)
            f = font.toString().split(',')
            try:
                f[1] = round(float(f[1]), 1)
            except:
                f[1] = 12.0
            return f[0], f[1]
        cfg['nfont'], cfg['nfont_sz'] = font_parse(self.nfont_edit.text())
        self.nfont_edit.setText('%s, %.1f' % (cfg['nfont'], cfg['nfont_sz']))
        cfg['lfont'], cfg['lfont_sz'] = font_parse(self.lfont_edit.text())
        self.lfont_edit.setText('%s, %.1f' % (cfg['lfont'], cfg['lfont_sz']))
        color = QColor(self.color_edit.text())
        cfg['hl_col'] = color.name()
        self.color_edit.setText(color.name())
        self.update_font_sample()
        cfg['deinflect'] = self.search_deinflect.isChecked()
        cfg['kanjidic'] = self.kdic_button.text()
        cfg['dict_load'] = self.dict_load.isChecked()
        global _dict_lookup
        if cfg['dict_load']:
            _dict_lookup = _dict_lookup_load
        else:
            global _dict
            _dict = {}
            _dict_lookup = _dict_lookup_noload
        d = []
        it = QTreeWidgetItemIterator(self.dict_list)
        while it.value():
            item = it.value()
            path = item.data(0, Qt.DisplayRole)
            name = item.data(1, Qt.DisplayRole)
            d.append([name, path])
            it += 1
        cfg['dicts'] = d
        _save_cfg()

    def accept(self):
        self.apply()
        super().accept()

    def kanji_dict(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Select Kanji Dictionary File',
                os.path.dirname(self.kdic_button.text()),
                options=QFileDialog.DontUseNativeDialog)
        if fn:
            self.kdic_button.setText(fn)

    def add_dict(self):
        dlg = dictDialog(self, title='Add Dictionary File')
        res = dlg.exec_()
        if res == QDialog.Accepted and dlg.name and dlg.path:
            item = QTreeWidgetItem([dlg.path, dlg.name])
            self.dict_list.addTopLevelItem(item)
            self.dict_list.setCurrentItem(item)

    def remove_dict(self):
        if len(self.dict_list.selectedItems()) < 1:
            return
        sel = self.dict_list.selectedItems()[0]
        idx = self.dict_list.indexOfTopLevelItem(sel)
        self.dict_list.takeTopLevelItem(idx)

    def edit_dict(self):
        if len(self.dict_list.selectedItems()) < 1:
            return
        sel = self.dict_list.selectedItems()[0]
        path = sel.data(0, Qt.DisplayRole)
        name = sel.data(1, Qt.DisplayRole)
        dlg = dictDialog(self, title='Dictionary File Properties', name=name, path=path)
        res = dlg.exec_()
        if res == QDialog.Accepted and dlg.name and dlg.path:
            sel.setData(0, Qt.DisplayRole, dlg.path)
            sel.setData(1, Qt.DisplayRole, dlg.name)

    def up_dict(self):
        if len(self.dict_list.selectedItems()) < 1:
            return
        sel = self.dict_list.selectedItems()[0]
        idx = self.dict_list.indexOfTopLevelItem(sel)
        if idx < 1:
            return;
        item = self.dict_list.takeTopLevelItem(idx)
        if item:
            self.dict_list.insertTopLevelItem(idx - 1, item)
            self.dict_list.setCurrentItem(item)

    def down_dict(self):
        if len(self.dict_list.selectedItems()) < 1:
            return
        sel = self.dict_list.selectedItems()[0]
        idx = self.dict_list.indexOfTopLevelItem(sel)
        if idx >= self.dict_list.topLevelItemCount() - 1:
            return;
        item = self.dict_list.takeTopLevelItem(idx)
        if item:
            self.dict_list.insertTopLevelItem(idx + 1, item)
            self.dict_list.setCurrentItem(item)


############################################################
# main window class

class jpMainWindow(QMainWindow):
    kanji_dlg = None

    def __init__(self, *args, title='', cl_args=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_ui(title)
        # evaluate command line arguments
        if cl_args is not None:
            if cl_args.kanjidic:
                self.kanjidic()
            elif cl_args.K:
                self.show()
                self.kanjidic()
            elif cl_args.kanji_lookup:
                self.kanjidic(cl_args.kanji_lookup)
            elif cl_args.clip_kanji:
                self.kanjidic(self.clipboard.text())
            elif cl_args.word_lookup:
                self.show()
                self.search_box.setCurrentText(cl_args.word_lookup)
                self.search()
            elif cl_args.clip_word:
                self.show()
                self.kbd_paste()
                self.search()
            else:
                self.show()

    def init_ui(self, title=''):
        jpIcon()
        self.setWindowTitle(title)
        self.setWindowIcon(jpIcon.jiten_pai)
        self.resize(800, 600)
        self.clipboard = QApplication.clipboard()
        # menu
        menubar = QMenuBar(self)
        file_menu = menubar.addMenu('&File')
        quit_action = QAction('&Quit', self)
        quit_action.setShortcut('Ctrl+Q')
        quit_action.triggered.connect(self.closeEvent)
        file_menu.addAction(quit_action)
        edit_menu = menubar.addMenu('&Edit')
        copy_action = QAction('&Copy', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self.kbd_copy)
        paste_action = QAction('&Paste', self)
        paste_action.setShortcut('Ctrl+V')
        paste_action.triggered.connect(self.kbd_paste)
        pref_action = QAction('Prefere&nces', self)
        pref_action.triggered.connect(self.pref_dlg)
        edit_menu.addAction(copy_action)
        edit_menu.addAction(paste_action)
        edit_menu.addSeparator()
        edit_menu.addAction(pref_action)
        tools_menu = menubar.addMenu('&Tools')
        if _got_kd:
            kanjidic_action = QAction('&KanjiDic', self)
            kanjidic_action.triggered.connect(self.kanjidic)
            kanjidic_action.setShortcut('Alt+K')
            tools_menu.addAction(kanjidic_action)
        help_menu = menubar.addMenu('&Help')
        about_action = QAction('&About', self)
        help_menu.addAction(about_action)
        about_action.triggered.connect(self.about_dlg)
        # japanese search options
        japopt_group = zQGroupBox('Japanese Search Options')
        self.japopt_exact = QRadioButton('E&xact Matches')
        self.japopt_exact.setChecked(cfg['jap_opt'][0])
        self.japopt_start = QRadioButton('&Start With Expression')
        self.japopt_start.setChecked(cfg['jap_opt'][1])
        self.japopt_end = QRadioButton('E&nd With Expression')
        self.japopt_end.setChecked(cfg['jap_opt'][2])
        self.japopt_any = QRadioButton('&Any Matches')
        self.japopt_any.setChecked(cfg['jap_opt'][3])
        japopt_layout = zQVBoxLayout()
        japopt_layout.addWidget(self.japopt_exact)
        japopt_layout.addWidget(self.japopt_start)
        japopt_layout.addWidget(self.japopt_end)
        japopt_layout.addWidget(self.japopt_any)
        japopt_layout.addStretch()
        japopt_group.setLayout(japopt_layout)
        # english search options
        self.engopt_group = zQGroupBox('English Search Options')
        self.engopt_expr = QRadioButton('Wh&ole Expressions')
        self.engopt_expr.setChecked(cfg['eng_opt'][0])
        self.engopt_word = QRadioButton('&Whole Words')
        self.engopt_word.setChecked(cfg['eng_opt'][1])
        self.engopt_any = QRadioButton('Any &Matches')
        self.engopt_any.setChecked(cfg['eng_opt'][2])
        def _english_toggle():
            en = not self.search_romaji.isChecked()
            self.engopt_expr.setEnabled(en)
            self.engopt_word.setEnabled(en)
            self.engopt_any.setEnabled(en)
        self.search_romaji = QCheckBox('&Rōmaji Input')
        self.search_romaji.toggled.connect(_english_toggle)
        self.search_romaji.setChecked(cfg['romaji'])
        engopt_layout = zQVBoxLayout()
        engopt_layout.addWidget(self.engopt_expr)
        engopt_layout.addWidget(self.engopt_word)
        engopt_layout.addWidget(self.engopt_any)
        engopt_layout.addWidget(self.search_romaji)
        engopt_layout.addStretch()
        self.engopt_group.setLayout(engopt_layout)
        # general search options
        genopt_group = zQGroupBox('General Options')
        genopt_dict_layout = zQHBoxLayout()
        self.genopt_dictsel = QComboBox()
        for d in cfg['dicts']:
            self.genopt_dictsel.addItem(d[0], d[1])
        idx = cfg['dict_idx']
        if idx >= self.genopt_dictsel.count():
            idx = 0
        self.genopt_dictsel.setCurrentIndex(idx)
        self.genopt_dict = QRadioButton('Search &Dict: ')
        self.genopt_dict.setChecked(not cfg['dict_all'])
        self.genopt_dictsel.setEnabled(not cfg['dict_all'])
        self.genopt_dict.toggled.connect(self.genopt_dictsel.setEnabled)
        genopt_dict_layout.addWidget(self.genopt_dict)
        genopt_dict_layout.addWidget(self.genopt_dictsel)
        self.genopt_alldict = QRadioButton('Search All D&ictionaries')
        self.genopt_alldict.setChecked(cfg['dict_all'])
        self.genopt_auto = QCheckBox('A&uto Adjust Options')
        self.genopt_auto.setToolTip('Relax options when current search settings yield no results.')
        self.genopt_auto.setTristate(False)
        self.genopt_auto.setChecked(cfg['auto_adj'])
        self.genopt_dolimit = QCheckBox('&Limit Results: ')
        self.genopt_dolimit.setTristate(False)
        self.genopt_dolimit.setChecked(cfg['do_limit'])
        self.genopt_limit = QSpinBox()
        self.genopt_limit.setMinimum(1)
        self.genopt_limit.setMaximum(cfg['hardlimit'])
        self.genopt_limit.setValue(cfg['limit'])
        self.genopt_limit.setMinimumWidth(130)
        self.genopt_limit.setEnabled(cfg['do_limit'])
        self.genopt_dolimit.toggled.connect(self.genopt_limit.setEnabled)
        genopt_limit_layout = zQHBoxLayout()
        genopt_limit_layout.addWidget(self.genopt_dolimit)
        genopt_limit_layout.addWidget(self.genopt_limit)
        genopt_layout = zQVBoxLayout()
        genopt_layout.addLayout(genopt_dict_layout)
        genopt_layout.addWidget(self.genopt_alldict)
        genopt_layout.addWidget(self.genopt_auto)
        genopt_layout.addLayout(genopt_limit_layout)
        genopt_layout.addStretch()
        genopt_group.setLayout(genopt_layout)
        # options layout
        opt_layout = zQHBoxLayout()
        opt_layout.addWidget(japopt_group)
        opt_layout.addWidget(self.engopt_group)
        opt_layout.addWidget(genopt_group)
        opt_layout.addStretch()
        # search area
        search_group = zQGroupBox('Enter expression')
        self.search_box = QComboBox()
        self.search_box.setMaxCount(int(cfg['max_hist']))
        for h in cfg['history']:
            self.search_box.insertItem(self.search_box.count(), h)
        self.search_box.setCurrentIndex(-1)
        self.search_box.setEditable(True)
        self.search_box.setMinimumWidth(400)
        self.search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_box_edit_style = self.search_box.lineEdit().styleSheet()
        self.search_box_edit_valid = True
        self.search_box.lineEdit().textChanged.connect(self.on_search_edit)
        self.search_box.lineEdit().returnPressed.connect(self.search)
        search_button = QPushButton('Search')
        search_button.setDefault(True)
        search_button.setIcon(jpIcon.find)
        search_button.clicked.connect(self.search)
        clear_button = QPushButton('&Clear')
        clear_button.setIcon(jpIcon.clear)
        clear_button.clicked.connect(self.search_clear)
        search_layout = zQHBoxLayout()
        search_layout.addWidget(self.search_box, 100)
        search_layout.addWidget(search_button, 5)
        search_layout.addWidget(clear_button, 1)
        search_group.setLayout(search_layout)
        # result area
        self.result_group = zQGroupBox('Search results:')
        self.result_pane = zQTextEdit()
        self.result_pane.setReadOnly(True)
        self.result_pane.setText('')
        self.result_pane.kanji_click.connect(self.kanjidic)
        result_layout = zQVBoxLayout()
        result_layout.addWidget(self.result_pane)
        self.result_group.setLayout(result_layout)
        # set up main window layout
        main_frame = QWidget()
        main_layout = QVBoxLayout(main_frame)
        main_layout.addWidget(menubar)
        main_layout.addLayout(opt_layout, 1)
        main_layout.addWidget(search_group, 1)
        main_layout.addWidget(self.result_group, 1000)
        self.setCentralWidget(main_frame)
        self.search_box.setFocus()

    def kbd_copy(self):
        self.clipboard.setText(self.result_pane.textCursor().selectedText())

    def kbd_paste(self):
        self.search_box.setCurrentText(self.clipboard.text())
        self.search_box.setFocus()

    def closeEvent(self, event=None):
        # update config:
        cfg['jap_opt'] = [self.japopt_exact.isChecked(),
                          self.japopt_start.isChecked(),
                          self.japopt_end.isChecked(),
                          self.japopt_any.isChecked() ]
        cfg['eng_opt'] = [self.engopt_expr.isChecked(),
                          self.engopt_word.isChecked(),
                          self.engopt_any.isChecked()]
        cfg['dict_idx'] = self.genopt_dictsel.currentIndex()
        cfg['dict_all'] = self.genopt_alldict.isChecked()
        cfg['auto_adj'] = self.genopt_auto.isChecked()
        cfg['limit'] = self.genopt_limit.value()
        cfg['do_limit'] = self.genopt_dolimit.isChecked()
        cfg['romaji'] = self.search_romaji.isChecked()
        cfg['history'] = [self.search_box.itemText(i) for i in range(min(cfg['max_hist'], self.search_box.count()))]
        _save_cfg()
        die()

    def pref_dlg(self):
        dlg = prefDialog(self)
        res = dlg.exec_()
        if res == QDialog.Accepted:
            if self.kanji_dlg:
                self.kanji_dlg.init_cfg()
                self.kanji_dlg.init_dic()
                self.kanji_dlg.update_search()
            idx = self.genopt_dictsel.currentIndex()
            self.genopt_dictsel.clear()
            for d in cfg['dicts']:
                self.genopt_dictsel.addItem(d[0], d[1])
            if idx >= self.genopt_dictsel.count() or idx < 0:
                idx = 0
            self.genopt_dictsel.setCurrentIndex(idx)
            self.search()

    def about_dlg(self):
        dlg = aboutDialog(self)
        dlg.exec_()

    def kanjidic_clicked(self, kanji=''):
        if kanji:
            self.show()
            self.search_box.setCurrentText(kanji)
            self.activateWindow()
            self.search()

    def kanjidic(self, kanji=''):
        if not self.kanji_dlg:
            self.kanji_dlg = kdMainWindow(parent=self)
            self.kanji_dlg.kanji_click.connect(self.kanjidic_clicked)
        self.kanji_dlg.showNormal()
        self.kanji_dlg.show_info(kanji)
        self.kanji_dlg.activateWindow()

    def on_search_edit(self, text):
        try:
            re.compile(text, re.IGNORECASE)
            self.search_box.lineEdit().setStyleSheet(self.search_box_edit_style)
            self.search_box_edit_valid = True
        except Exception as e:
            self.search_box.lineEdit().setStyleSheet('QLineEdit { background-color: #ffffd8; }');
            self.search_box_edit_valid = False

    def search_clear(self):
        self.search_box.setFocus()
        self.search_box.setCurrentIndex(-1)
        self.search_box.clearEditText()

    TERM_END = r'(\(.+?\))?(;|$)'
    def _search_apply_options(self, term, mode):
        s_term = term
        if mode == ScanMode.JAP:
            s_term = kata2hira(s_term)
            if self.japopt_exact.isChecked():
                s_term = r'(^|;)' + s_term
                s_term = s_term + self.TERM_END
            elif self.japopt_start.isChecked():
                s_term = r'(^|;)' + s_term
            elif self.japopt_end.isChecked():
                s_term = s_term + self.TERM_END
        else:
            if self.engopt_expr.isChecked():
                s_term = r'\W( to)? ' + s_term + r'(\s+\(.*\))?;'
            elif self.engopt_word.isChecked():
                s_term = r'\b' + s_term + r'\b'
        return s_term

    def _search_relax(self, mode):
        if mode == ScanMode.JAP:
            if self.japopt_exact.isChecked():
                self.japopt_start.setChecked(True);
                return True
            elif self.japopt_start.isChecked():
                self.japopt_end.setChecked(True);
                return True
            elif self.japopt_end.isChecked():
                self.japopt_any.setChecked(True);
                return True
        else:
            if self.engopt_expr.isChecked():
                self.engopt_word.setChecked(True);
                return True
            elif self.engopt_word.isChecked():
                self.engopt_any.setChecked(True);
                return True
        return False

    def _search_show_progress(self):
        self.result_group.setTitle(self.result_group.title() + '.')
        QApplication.processEvents()

    def _search_show_dict_error(self, dname):
        mbox = QMessageBox(self)
        mbox.setWindowTitle('Dictionary Error')
        mbox.setIcon(QMessageBox.Critical)
        mbox.setStandardButtons(QMessageBox.Ok)
        mbox.setText("Dictionary '%s' configured incorrectly!" % dname)
        mbox.exec_()
        mbox.hide()
        QApplication.processEvents()

    def _search_deinflected(self, inflist, dic, mode, limit):
        result = []
        ok = True
        for inf in inflist:
            # perform lookup for the infinitive form
            s_term = r'(^|;)' + inf.infi + self.TERM_END
            res, ok = _dict_lookup(dic, s_term, mode, limit)
            # keep only results belonging to a suitable word class and
            # attach the inflection info; reject everything else
            for r in res:
                if inf.wclass.search(r.gloss):
                    result.append(EntryEx(r.headword, r.reading, r.gloss, inf))
                    limit -= 1
            if limit <= 0 or not ok:
                break
        return result, ok

    def search(self):
        self.search_box.setFocus()
        # validate input
        term = self.search_box.currentText().strip()
        if len(term) < 1:
            return
        if not self.search_box_edit_valid:
            self.search_box.lineEdit().setStyleSheet('QLineEdit { background-color: #ffc8b8; }');
            return
        self.search_box.setCurrentText(term)
        self.result_pane.setEnabled(False)
        # save to history
        for i in range(self.search_box.count()):
            if self.search_box.itemText(i) == term:
                self.search_box.removeItem(i)
                break
        self.search_box.insertItem(0, term)
        self.search_box.setCurrentIndex(0)
        # convert Romaji
        if self.search_romaji.isChecked():
            term = alphabet2kana(term)
        # convert Katakana to Hiragana
        term = kata2hira(term)
        # result limiting
        slimit = self.genopt_limit.value() if self.genopt_limit.isEnabled() else cfg['hardlimit']
        limit = slimit
        # search
        self.result_group.setTitle('Search results: ...')
        QApplication.processEvents()
        mode = ScanMode.JAP if _has_jap(term) else ScanMode.ENG
        if self.genopt_dict.isChecked():
            dics = [[self.genopt_dictsel.currentText(), self.genopt_dictsel.itemData(self.genopt_dictsel.currentIndex())]]
        else:
            dics = cfg['dicts']
        result = []
        # de-inflect verb
        inflist = []
        if cfg['deinflect'] and mode == ScanMode.JAP and _vconj_loaded:
            inflist = _vconj_deinflect(term)
        # perform lookup
        rdiff = 0
        for d in dics:
            ok = True
            # add dictionary caption
            if len(dics) > 1:
                result.append(Entry('#', '', d[0]))
                rdiff += 1
            # search de-inflected verbs
            if len(inflist) > 0:
                r, ok = self._search_deinflected(inflist, d[1], mode, limit)
                self._search_show_progress()
                result.extend(r)
                limit -= len(r)
                if limit <= 0:
                    break
                if not ok:
                    self._search_show_dict_error(d[0])
                    continue
            # 'normal' search
            rlen = len(result)
            while ok:
                s_term = self._search_apply_options(term, mode)
                r, ok = _dict_lookup(d[1], s_term, mode, limit)
                self._search_show_progress()
                result.extend(r)
                limit -= len(r)
                if not ok:
                    self._search_show_dict_error(d[0])
                # relax search options
                if limit <= 0 or len(result) != rlen \
                   or not self.genopt_auto.isChecked() \
                   or not self._search_relax(mode):
                        break;
            if limit <= 0:
                break
        # report results
        rlen = len(result)
        self.result_group.setTitle('Search results: %d%s' % (rlen - rdiff, '+' if (rlen-rdiff)>=slimit else ''))
        QApplication.processEvents()
        # format result
        if rlen > cfg['hardlimit'] / 2:
            self.result_pane.setPlainText('Formatting...')
            QApplication.processEvents()
        re_term = re.compile(term, re.IGNORECASE)
        re_entity = re.compile(r'EntL\d+X?; *$', re.IGNORECASE)
        re_mark = re.compile(r'(\(.+?\))')
        nfmt = '<div style="font-family:%s;font-size:%.1fpt">' % (cfg['nfont'], cfg['nfont_sz'])
        lfmt = '<span style="font-family:%s;font-size:%.1fpt;">' % (cfg['lfont'], cfg['lfont_sz'])
        hlfmt = '<span style="color:%s;">' % cfg['hl_col']
        html = [''] * (rlen + 2)
        html[0] = nfmt
        def hl_jap(rex, word):
            hlw = []
            start = 0
            for match in rex.finditer(kata2hira(word)):
                hlw.append('%s%s%s</span>' % (word[start:match.span()[0]], hlfmt, word[match.span()[0]:match.span()[1]]))
                start = match.span()[1]
            hlw.append(word[start:])
            return ''.join(hlw)
        for idx, res in enumerate(result):
            # handle dictionary caption
            if res.headword == '#':
                html[idx+1] = '<p>Matches in <span style="color:#bc3031;">%s</span>:</p>' % res.gloss
                continue
            # render edict2 priority markers in small font (headwords only)
            headword = re_mark.sub(r'<small>\1</small>', res.headword)
            # line break edict2 multi-headword entries
            headword = headword.replace(';', '<br>')
            # parenthesize reading
            reading = '(%s)' % res.reading if res.reading else ''
            # for now just drop the edict2 entry number part from gloss,
            # in future this could be used to e.g. link somewhere relevant
            gloss = re_entity.sub('', res.gloss)
            # highlight matches
            verb_message = ''
            if mode == ScanMode.JAP:
                if len(res) > 3:
                    verb_message = '<span style="color:#bc3031;">Possible inflected verb or adjective:</span> %s<br>' % res.inf.blurb
                    rex = re.compile(res.inf.infi, re.IGNORECASE)
                else:
                    rex = re_term
                headword = hl_jap(rex, headword)
                reading = hl_jap(rex, reading)
            else:
                gloss = re_term.sub(lambda m: '%s%s</span>'%(hlfmt,m.group(0)), gloss)
            # assemble display line
            html[idx+1] = '<p>%s%s%s</span>%s %s</p>\n' % (verb_message, lfmt, headword, reading, gloss)
        html[rlen + 1] = '</div>'
        self.result_pane.setHtml(''.join(html))
        self.result_pane.setEnabled(True)


############################################################
# dictionary load and lookup
#
# edict example lines:
# 〆日 [しめび] /(n) time limit/closing day/settlement day (payment)/deadline/
# ハート /(n) heart/(P)/

Entry = namedtuple('Entry', 'headword reading gloss')
EntryEx = namedtuple('EntryEx', 'headword reading gloss inf')

_dict_lookup = None

_dict = {}      # format: { 'filename_1': [Entry_0, ...], ... }

def _dict_split_line(line):
    # manually splitting the line is actually faster than regex
    try:
        p1 = line.split('[', 1)
        if len(p1) < 2:
            p1 = line.split('/', 1)
            p2 = ['', p1[1]]
        else:
            p2 = p1[1].split(']', 1)
        headword = p1[0].strip()
        reading = p2[0].strip()
        gloss = ' ' + p2[1].lstrip('/ ').rstrip(' \t\r\n').replace('/', '; ')
    except Exception as e:
        eprint('malformed line:', line, ':', str(e))
        headword = reading = gloss = ''
    return Entry(headword, reading, gloss)

def _dict_load(dict_fname):
    dic = _dict.get(dict_fname, [])
    if not dic:
        try:
            with open(dict_fname) as dict_file:
                for line in dict_file:
                    entry = _dict_split_line(line)
                    if entry.headword:
                        dic.append(entry)
            _dict[dict_fname] = dic
        except Exception as e:
            eprint('_dict_load:', dict_fname, str(e))
    return dic

def _dict_matches(dic, pattern, mode, limit):
    result = []
    cnt = 0
    re_pattern = re.compile(pattern, re.IGNORECASE)
    for entry in dic:
        if (mode == ScanMode.JAP and (re_pattern.search(kata2hira(entry.headword)) \
                                   or re_pattern.search(kata2hira(entry.reading)))) \
        or (mode == ScanMode.ENG and re_pattern.search(entry.gloss)):
            result.append(entry)
            cnt += 1
            if limit and cnt >= limit:
                break
    return result

def _dict_lookup_load(dict_fname, pattern, mode, limit=0):
    dic = _dict_load(dict_fname)
    if dic:
        return _dict_matches(dic, pattern, mode, limit), True
    return [], False

def _dict_lookup_noload(dict_fname, pattern, mode, limit=0):
    try:
        with open(dict_fname) as dict_file:
            dic = map(_dict_split_line, dict_file)
            return _dict_matches(dic, pattern, mode, limit), True
    except Exception as e:
        eprint('_dict_lookup_noload:', dict_fname, str(e))
    return [], False


############################################################
# main function

def _parse_cmdline():
    parser = ArgumentParser(
        formatter_class=lambda prog: RawTextHelpFormatter(prog, max_help_position=40),
        description='Jiten-pai Japanese dictionary',
        epilog='Only one of these options should be used at a time.\n'
    )
    parser.add_argument('-k', '--kanjidic', action='count', help='start with KanjiDic')
    parser.add_argument('-K', action='count', help='same as -k, but word dictionary visible')
    parser.add_argument('-c', '--clip-kanji', action='count', help='look up kanji from clipboard')
    parser.add_argument('-v', '--clip-word', action='count', help='look up word from clipboard')
    parser.add_argument('-l', '--kanji-lookup', metavar='KANJI', help='look up KANJI in kanji dictionary')
    parser.add_argument('-w', '--word-lookup', metavar='WORD', help='look up WORD in word dictionary')
    return parser.parse_args()

def main():
    global app
    _load_cfg()
    _vconj_load()
    cl_args = _parse_cmdline()
    # set up window
    os.environ['QT_LOGGING_RULES'] = 'qt5ct.debug=false'
    app = QApplication(sys.argv)
    app.setApplicationName(_JITENPAI_NAME)
    root = jpMainWindow(title=_JITENPAI_NAME + ' ' + _JITENPAI_VERSION, cl_args=cl_args)
    die(app.exec_())

# run application
if __name__== "__main__":
    app = None
    main()

# EOF
