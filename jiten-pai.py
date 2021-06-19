#!/usr/bin/env python3

"""
jiten-pai.py

Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>

Contributors:
    volpol

Jiten-pai is distributed under the Modified ("3-clause") BSD License.
See `LICENSE` file for more information.
"""


_JITENPAI_VERSION = '0.0.8'
_JITENPAI_NAME = 'Jiten-pai'
_JITENPAI_DIR = 'jiten-pai'
_JITENPAI_CFG = 'jiten-pai.conf'
_JITENPAI_VCONJ = 'vconj.utf8'

_JITENPAI_HELP = 'todo'

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
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


############################################################
# utility functions and classes

def die(rc=0):
    sys.exit(rc)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def contains_cjk(s):
    for c in s:
        if "Lo" == unicodedata.category(c):
            return True
    return False

class ScanMode(enum.Enum):
    JAP = 1
    ENG = 2


############################################################
# configuration

cfg = {
    'dicts': [
        ['edict', '/usr/share/gjiten/dics/edict'],
        ['enamdict', '/usr/share/gjiten/dics/enamdict'],
    ],
    'dict_idx': 0,
    'dict_all': False,
    'limit': 100,
    'hardlimit': 10000,
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
    'max_hist': 12,
    'history': [],
    # run-time only, not saved:
    'cfgfile': None,
}

def _get_cfile_path(fname, mode=os.R_OK):
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
            return
    except Exception as e:
        eprint('_load_cfg:', cfname, str(e))


############################################################
# verb de-inflection

_vc_type = dict()
_vc_deinf = []
_vc_loaded = False

def _get_dfile_path(fname, mode=os.R_OK):
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

def _vc_load():
    global _vc_loaded
    vcname = _JITENPAI_VCONJ
    if not os.access(vcname, os.R_OK):
        vcname = _get_dfile_path(os.path.join(_JITENPAI_DIR, _JITENPAI_VCONJ), mode=os.R_OK)
    try:
        with open(vcname) as vcfile:
            re_type = re.compile(r'^(\d+)\s+(.+)$')
            re_deinf = re.compile(r'^\s*([^#\s]+)\s+(\S+)\s+(\d+)\s*$')
            for line in vcfile:
                match = re_type.match(line)
                if match:
                    _vc_type[match.group(1)] = match.group(2)
                    continue
                match = re_deinf.match(line)
                if match:
                    r = re.compile('%s$' % match.group(1))
                    _vc_deinf.append([r, match.group(1), match.group(2), match.group(3)])
                    continue
        _vc_loaded = len(_vc_deinf) > 0
    except Exception as e:
        eprint('_vc_load:', vcname, str(e))

def _vc_deinflect(verb):
    inf = []
    blurb = ''
    for p in _vc_deinf:
        v = p[0].sub(p[2], verb)
        if v != verb:
            blurb = '%s %s → %s' % (_vc_type[p[3]], p[1], p[2])
            inf.append([v, blurb])
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
    add_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAA0lBMVEX///87a6g2Z6U1ZqU3Z6QzY6I6aKQxXp0rWJYrWZYwX50nUpAsWpgjTYoqV5QpVJIo
VZImUo4hSockT4oiS4gmUYypwNymvdo0ZaSkvNl7nsgzZKOWsdJnjb0wYJ8xYaCGpMpTfbMsWpgrWZd5msN/n8d9ncV6msRcg7c+baltkL50lsFylMBmirlojbw1ZqQ1ZqU3aKY5aqg7bKk9bao/b6xBca1AcKsnU5EmUo92mcVKebMhTIkhS4iIqdBYh70gSoeTs9dn
lMeQsddrl8n///95XeUxAAAAFnRSTlMAgfv7gfv39/uB+/v7+4H79/f7gfuBOt2MIAAAAAFiS0dEAIgFHUgAAAAHdElNRQflBhAJFBUZpoqfAAAAc0lEQVQY02NgIBIwMjExoggwi4kzowhISEpJoAhIy8jKwTksrPJybAqK7ErKHJxgAS4VVTV1DU0tbR1dbrAAj56+
gaGRsYmpmTkvWICP38JSwMpa0MZWSBhujo2dvQOKLQ6OTqgCIs4uIigCoiIiosR6EwD3vgp0XvdNGgAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMDkb0F0AAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6
MDBIRmjhAAAAAElFTkSuQmCC
"""
    apply_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAABEVBMVEX///8ATwAATAAASQAATQAOaAsBWwEATgARaw4AWwAATgASaxAEUwQATAAVaxITZBIA
TAAshCMEUwQAVQAXaRUJXwcATQAOaAwDUgMXZhUQXA0ASwACUAIYXRQATgACTgIXVhECTgIaVBIATQACTQIcUBQCSAIcUBEATAAATQAATgB2tWOay3u26qF5uGGTxnCZ0pCZ0I+QwW+m0HdYoEKRxWmJxnuIwnqQvWuayGhztGSTyGpZn0GOxGB/wGh7u2aWw2xKjTCK
wVtksVCPyVxbnD+KwVd3wFV2vFmdyW1OizGDwkpQrCqCxkVkujJdsi2JvUtOgi1/yDVHug5XwhiOx0RUgy2R3j6Y1UdNfSn///9jJoMPAAAAK3RSTlMAHXIOIe3YDeu8bPWRG+nWa/6QGOf1MtuV5vYzjfc0mvmd+TWg+qP6NkYkIiPNwAAAAAFiS0dEAIgFHUgAAAAH
dElNRQflBhAJFBUZpoqfAAAAgklEQVQY02NgIAUwMjGj8FlYtdnYkeU5dHT1OEEsLm4eIMnLp29gaMQPZAkIGpsIMQiLmJqZW4iKAQXELa2sbSQkbe3sHaSkQTpkHJ2cXVzd3D08ZeUgpsl7efv4+vkHKMjBzFcMDAoOCVVSRtioEhYeoaqM7Ca1SHUNVFdrahHvQwDC
iA/opeZaowAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMDkb0F0AAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDBIRmjhAAAAAElFTkSuQmCC
"""
    cancel_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAABwlBMVEX////////Pe3u4PDymAgKyJCS1MTGrERG4PT2/WVmoDw+mDw+mEQ+jCgnJe3ueDw+T
CgiaBASmCQmtDg65FBOqPDyRDAqUCwuqCwu3GRieIyOUBASmCwu3GhmSCwudCgq0FhWLCQegAACOCwugCwuxFBKKCQedAACmAACSIyOxFhSKBgKZAACjCwuXPDyHBgKUAACgCwu5GxS9e3uCDg6IAgKUCAiiDQ27HxWhWVmCBQKdWVl4Dg6xe3uKPDxrAAB3DQ15EBBs
AQG7SEfMc3PYiorZi4vNdna5QkLJb23QeXewNzelHByuJSO8SUbLcG/CY2G/XVq/V1S5SkbAYWG5U1CrKyXCYF7BU06+U1OxSES0TUuqKyavPjelMSvMYVnFRka4PzqGBwWcJiKsOzaqQzqcHhfOUkrMNzfEOjScFRCTHhaMEgmaEgu+HxTLFRXGHRSlEw2QDQSREQWc
Egi1FAjHAADLDQSuFgyaEQWXEQWWBQKuGwq8AADIDgWrBgKcEAWfFwiqAAC/FQeACAO/DgarFwiqGgi+CAO+EwaxFQq8GQ/OHA3QCgO2GQieFQe4GwjMGwnSHArAHAqjFgf////FCuQlAAAAQ3RSTlMAAirVzfr70dWT+Pj+/ir47XQcNfDV7hcX3e12Ft75Gd79Z/ku
3v1bF+3y/Vtw1f1bF/Aq+HQedvGT/pP4KtXN+fnNf0ybtwAAAAFiS0dEAIgFHUgAAAAHdElNRQflBhAJFBUZpoqfAAAA2klEQVQY02NggABGRgYkwMTMwsrGzsEE43NyObu4url7cHNC+TyeXt4+vn7+AbxgET7+wCABQSFhkeCQUH4+oIBoWLiYOIOEZERkVHSMKFBA
KjZOmkFGNj4hMSk5RQpon1xqmryMQnpGpqJSVrYcIwOjck6uimpefoGaukZhkTLQOZrFJVqlZeXaOgy6FZWaQDP0qqprauv0DRgMjeob9IACxiaNTc0tpmbmFq1tJsYgh1hatXd0dnX39PZZWUKcam3TP2HipMlTbKxhnrG1s3dwdLKzRfYw3PsA/icuAzQMLNUAAAAl
dEVYdGRhdGU6Y3JlYXRlADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDA5G9BdAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDIxLTA2LTE2VDA3OjIwOjIxKzAyOjAwSEZo4QAAAABJRU5ErkJggg==
"""
    clear_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAABcVBMVEX///+OWQSUXwiQWgOTXgiSWgOYYguRWwWSWwCTXQaVXwqSXAawfCmWYAqPWATXwhHT
vQ6WYgeibhrMzMzfyye5ii6VXgiAgADaxL3WwBLTuQ///wDjxhzaxRXZxR/hzoPXwxDXwg/XvA3ZxBTk0jHZxE6/vwDbyBLZxBTo1zzZxTHPvxDZxRTm1DbZxBPZxBTj0C/YwxDZxBPXwxHMzADZxBHXwhHZxRXizy3axBjaxRXWxRDWwhDZxBTWwhDaxh7n1TrYwxHV
xBLYxBTZwxPXwxDWxA67jEHbql3Wpld5VyLFk0TpuW7aql/aqVzouG3YwhbWwRLfwDPaxcnr2af36HPp10Deys3bx9bn1bLs22n77W7973L77HLw4Jjhzcbaxtj252D87m/042D05Fru3kz77G/t2FHfyyP87nDu21Du2lT25l/s2kXy4lXj0S/m0EPx4Fzp1z777W3l
z0P25mXdyR3kzT7y41nXwg/////PJyqrAAAAR3RSTlMASNT9h2D09g7vtoX39EC4XfD0Bfb5wAKL/nUBCav3/P55E9X1owQO1/n5EMv3+L72+Pz5BTz3+vX3yh995fX5+HsrnO/7OErIQ6MAAAABYktHRACIBR1IAAAAB3RJTUUH4gwOFCwjMg6bawAAALFJREFUGNNj
YEAARiZmFiQuAyubuwc7Ep+D09PLmwtJgJvHx5eXD87lFxD08xfihvOFA0QCg0TFxOECEsEhoWGSUtJQroysnHx4RGSUgiKEr6SsEh0TGxefoKoG5qtraCYmxSTHxGhpQ9Tr6KakxqSlx8ToQQT0DVIyMjOzsnNgAoa5RnmZ+QWFRcXGJmABUzPzFAvLktKyPCuopdY2
tnb25RWVDo4Ifzg5u7hWVrqBmAA2viL/1jja/wAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMjozNyswMjowMJKUNcQAAAAldEVYdGRhdGU6bW9kaWZ5ADIwMTgtMTItMTRUMTk6NDQ6MzUrMDE6MDA3gAxHAAAAAElFTkSuQmCC
"""
    close_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAACSVBMVEUAAACEAACOAACTAACUAACQAACLAAB9AACLAACUAgKZCQmNAACGAAB+AACOAACSAACI
AABMAACNAACSAACDAACFAACLAAAAAAAAAACPAACVAAB5AABgAACZAACKAAB6AACQAABzAACVAAAcAACoAACLAAAAAACgAACrAAAgAAByAAC1AACbAAAAAAAAAACZAACwAAAQAAAAAACaAADAAACxAAAyAAAAAABlAACrAAC6AAC8AACzAACIAAAAAAAAAAAqAAA3AAAC
AAAAAACwNTXFYGDHZWW3RESqHR3biYnnp6fop6fimpq3NTWrERHafXreiYLhi4PhioThh4TfhITbgYHcgYG4KSmeAADKSELRf2725eLUi3fbfF/ceGDMbWLy29vUiIjNVFSnAwOvAwLPWDrMkn/////58/HEeVi+ZD/u29bctbK+ODe5EBC5CQDRRAfGVRHEknn38e7q
2tTXuLCxNhXFIAy7AgCgAAC9EADSRQDaXwDBXAC2jX/TvrmlQAXSSgDLLwC/DQCnAACmAAC+DQDQQQDWXACxWBLj08307u2tYjLRWQDRQgDCFgCsAAC3BADHMQC1SRLo1s3hx63NpHf28O27aDLMSgC9EQCtAACxAACzFQDMi3jmxq3JbgXUfADaqnPnyri5NwCzAwCu
AgCsGwHQgma/TQXOYQDUbADOaQDal1zCVBCxEAC0AAC6AACrAgCqEwCzLAC7PgDASgDBSwC4NgCsCwC2AACyAACnAgClCQClCwCnBgCvAAC/AAC7AAB8252hAAAARHRSTlMADlF5fV8dC4n0/aseFs7sNwTC6htlowEDzvkUFv5RMW0taBD0Pway5QtC+3UCCIi6DQ6I
+rAYCkew7PTBXgweMjYgD4hci68AAAABYktHRGdb0+mzAAAAB3RJTUUH5QYQCRQVGaaKnwAAAQJJREFUGNNjYAABRiZmFlY2Bhhg5+B0cXVz5+LmgfB5+Tw8vby9vX18+QVAfEEhP/+AwKDgkNCwcGERoIBoRGRUdExsXHxCYlKymDiDhGRKalp6RmZWdnpObp6UNIOM
bH5BYVF6cUl6aVl5RaUcg3xlVXVNbV16en1DY1NziwKDYmtbe0dnV3p6d09vX/8EJQZllYmTJk9JnzotffqMmbNmqzKoqc+ZOy99/oKFi9IXL1mqockgrqW9bPmKlatWr1m7bv0GHV0GBj39jZs2b9m6bfuOnbsMDEFONTI22b1n7779Bw6amomDPWNuYWl1aKO1ja2R
ONS7unb2Do5OzhIgNgAd2VDNvmw0xgAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMDkb0F0AAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDBIRmjhAAAAAElFTkSuQmCC
"""
    down_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAArlBMVEX///+OkIyLjYiIiISIioWIiYWIiIWIi4WIiYWHioWDhoGQko2DhoCEhoF/gX2LjYmA
gHx/gXx6eneFh4KHiYR5fHZ6fnd2dnOAgn6ChIB1d3Nwc218fXpqbWp3eXVnZ2RzdHFhZF5ucG1cX1ldX1pYWFj////f393w8e/u7u3R0s/X2NX5+fn09PPV1dLd3dvz8/Pc3drz8/Lc3NmMjorb29j9/f3a2tj29vS/wL0NviM0AAAAJnRSTlMAgfQ6y8FHS9nCwvtU
y9n7VMFL+/tUR1T7+5BU+1T7VPtU+1b4HR8aBOoAAAABYktHRACIBR1IAAAAB3RJTUUH5QYQCRQVGaaKnwAAAJNJREFUGNNljtkOgkAMRcvgDgoKCMgO7pRtENH//zHJBA0j96lpT24PAItABOBCzoRfjIhRBoQ4mc76jvliKQKsLldJZoQs3e5rgE2KmaJ2qKpkmG8B
dlqBpW6AoZdYaPvuYloVUvtgU6wsk9U6bo30QbF2nf6R5zf4xMb3fhZB2L7aMBh4RfE7jjjT5Jj8uZ++wwf2yQwD/ZEb/wAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMDkb0F0AAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjEtMDYtMTZU
MDc6MjA6MjErMDI6MDBIRmjhAAAAAElFTkSuQmCC
"""
    find_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAACAVBMVEX///8rZbYuZrczabgvZ7cpYK0vYq5ogsiUqNcvZbApYa4nXKUyYaouOm4XH0oTGkEs
N2NDb7AkV50oWZ9JVZciK2MjMFY9QlNlanQqNlUZIk9eZpYqWp8lV50kU5VKZasoMnEzNUBmZmbc3Nv6+vrp6elQVFwhKV5xh74lVJYmUY83Q4orOGZgYGCfm5vY2NP6+vrx8fGNjY0nM1w3RIAhSoU1PYgzN06BgX7RyMjd3czf38/UzMwxNkotNnkhSoYfRX04QY83
PVWNjYnb287b29s3O1EyOoIfRn4fQ3c8SJYxPXGHh4PVysrq6tUuOmo7R48bPnA1TIg8RphaYHGqqqXT09NaYG43QI1CVpIbPm8ZPW4cPnBDT54+SJ4/TYddZ4s/TIY6RZZHUp0dPGocHiEZPW4eP3JATKFBS6VBSqQ/TJ4kIBwZFhMbPnAxR4QySIUbO2kzQlQgHBkZ
FhMaPW8dPnEbPnAZGx8aFxQyMzN0bmUcGBUZFhMZFhMrKCMZFhMZFhMZFhOXod22uOrExu68wuiEjdJ0e7qeo8PY3PB3gcm9wuVja7OLkL9ib7aRmc9qcLuXmtZka7WJjc1RXaJqc7ZQWqRdZa5NV55bZKxKVJxMVqNQWqdSXKQjQ3RwdHtEUZZQV6JRWKRHU5pxbmqG
f3Vua2VEPjcZFhP///8kUNFRAAAAg3RSTlMADn/D8kLq+vvqQkL1+/7+/PUO6vz8toybufz96g5/+fyBWpPny4z8+n/D+7ZdOCyfqnK2/PL+jkkcDxAejv7y8v6KQRUHiv7yw/u1RhgMtft/+PxmMBdm/fx/Dur7/Ktlq/3+/mRC9Pv+/vv2Rur4/P378zV/w/Jt7O/9
7Ujr4TDj4DJK+8EAAAABYktHRACIBR1IAAAAB3RJTUUH5QYQCRQVGaaKnwAAAO1JREFUGNNjYGBgYGRiZmFhZmJkgAJWNvbmltY2Dk4uCJ+bp72Dl49foLNLkBvEFxLuFhEVE5eQlJLukZEFCsjJ9yooKimrqKqp92loAgW0+rV1dPX0DQyNjE0maAEFTCeamVtYWlnb
WNjaTbIHCjhMdnRydnF1dXF2c5/iARTwnOrl7ePr5+fr4x8wzRMoEBg0PTgkNCwsNDxiRmQUUCA6ZmZsXHxCQmJS8qyUVJBD0tJnz8nIzMqeO2/+gpxcsEhe/sJFi5cUFBYtXVZcAhKJLi0rLy8rraisWl5dw4AEauvqV6xEFmBoaFzZBABydT5o+YqLbAAAACV0RVh0
ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMDkb0F0AAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDBIRmjhAAAAAElFTkSuQmCC
"""
    ok_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAABEVBMVEX///8JIzUJHToAEjcIHz4WM1oOJ00AFDsaNVwMJUsJHzsdOV8OIUMJHDkdNVoeN1kK
HTkvTXYOIkILIDUdNVYVMFcGHDcZMVUOIj8aMk0aNFYFHjcLHz8cNVMFGzcKHj0aMUYJGjwLIDsXMEAIGzsMHjoYMT4HGjoAAAALHzcbND8HHzoKHTpph6h9mrWryt5ig6VwjKiUsshvi6h0kalEYINifpp/m7J+m7Jng59depZnhJ1lgZs7VG9VcYdphZ5ifZgsSGlR
a4dbd5RgfZo1TFpNanpmgZ9kgJxje5MtRl1PaolUcJNadpdbdptWcJREX3kqRFNSb5ZffKhigKxQbYkzTFd0lL1oiKY2Ul7///+XLON3AAAALXRSTlMAHXIOIezYDeq8bPWRG+jUa/6QGOfzLtqW5/Uzjvc4oPk8qPtBsPxGAbb8S2r7wD5BAAAAAWJLR0QAiAUdSAAA
AAd0SU1FB+UGEAkUFRmmip8AAACESURBVBjTY2AgBTAyMaPwWVh12diR5Tn09A04QSwubh4gyctnaGRkzA9kCQiamAoxCIuYmVtYiooBBcStrG1sJSTt7K0dpKRBOmQcnZxdXN3cPTxl5SCmyXt5+/j6+QcoKMLMVwoMCg4JVVZB2KgaFh6hpo7kBA3NSC1tFEdq6Cgy
EA0A59sQXX3tOeAAAAAldEVYdGRhdGU6Y3JlYXRlADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDA5G9BdAAAAJXRFWHRkYXRlOm1vZGlmeQAyMDIxLTA2LTE2VDA3OjIwOjIxKzAyOjAwSEZo4QAAAABJRU5ErkJggg==
"""
    open_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAB41BMVEUAAABUf7UAAAAAAAAAAAAAAAAJCQlUf7UqKinExMRYh8KTsctKdaZFX4AAGDgAEzMA
FDMAEzIAEzIAEzEAEzEAEjAAEjEAGz0oTHb////o5+dKc6dRcpv29vb4+Pj5+Pj19PTr6+v///47UWpRfrhUg7xUgbs9ZJJKapD5+fnv7u6goKDk4d5OYXd4otd8qeFJdq0vUno+Xof49/f39/fy8vKamprx7+/h3ds3T21olM0wUnsrS3H19fWhoKD//PpGXXkqS3Ml
RmohQ236+fn7+/q4uLi0s7OtrKyysLD08vAOKkoiQWQRNF77+vr6+frf4eXP09jO0tbMz9XJzdHGyM7BxMrg4uUAFDEYOVsAHkXo6OrO0dXQ0ta1u8OHor6nzeuozeqpzeuozeuqzuu84PxPdp+84PunzOqmy+mmzOqozuuqzuqFq9qCpteAptd/pteHreFIXXhQeamD
qdx8o9Z9o9Z+o9aBptiAp9iCp9iBp9iHruFJX3tReqqKruCDqduGqduHqduFqduEqduEqdqJseRKX3w5Z5tAdrQ/dLBAdLBDerknRGZYf62Hrd+FqdqGqdqDqdqKsONQZIGBqN19o9h+pNh8o9h4o9l8o9l+pNl+o9l5o9l6o9h+o9iBqeD0enAlAAAAGHRSTlMAAANJ
Sz0IyZb+1bq5r0F6e3x9fn+Bf0Lax4JAAAAAAWJLR0QZ7G61iAAAAAd0SU1FB+UGEAkUFRmmip8AAAEASURBVBjTY2BgYmYBAVY2Bghgl5AEAykOMJeRQVpGUlZOXkGRU0lZRVWNi4FBXUNSTk5TVktbUkdXT9+AgcHQSNJYU9PE1EzS3MLSypqBwcYQJCBnawc0x97B
kYHByVnSRM7F1UXRzd3D08ubgcHHV1LOzz8gMCg4JDQsPIKBITIqOiY2Lj4hMSk5OTkllZshLT0jMys7JzcvvyAvP7+wiKG4pLSsrLy8orKysqq6uqaWoa6+oaGxoam5BUg2tra1M3R0dgFBNxCCQE8vQ19/64SJE1pBxKQJrZOnMPBMnTZ9xsxZs2fPmTtv+vwFvAx8
/AKCQsIioqJiwkKCAvziAGE5SZlTQyIOAAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDIxLTA2LTE2VDA3OjIwOjIxKzAyOjAwORvQXQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMEhGaOEAAAAASUVORK5CYII=
"""
    properties_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAABFFBMVEUAAADX2dLU19DV2dHT18/l5uLV2dHk5+LW2NLP08vP08zLz8fM0MjHy8PIzMTDxsDE
x8HAwr3Bw729wLm8v7i6vbZtbW18fXmAgGCysq95eXRVVVXAwruztbD09PKurq7T18/////4+fj29vXR08739/bO0Mu6vbbY2tX5+fj6+vn7+/vKy8mWmJSeoJvd3tz8/Pysraq8vbrs7eyfoJzh4eD9/f3P0M6rramrrKnP0M3w8fCjpKCUlpKztLCnqKSho5+YmpaW
mJPb29jExcKen5vq6+rs7OyZmpbg4N+Qkozn5+Xo6Ob19fO4ubehop6XmZaNj4uQkY60tbK2t7T6+vqys6+UlpOwsa3z8/C3urOOkYsDQHnnAAAAIHRSTlMAt/qA/veF+Hz++f7+/v7+/v7+/v7+B8YIvXADtd5hLL2kwkcAAAABYktHRCHEbA0WAAAAB3RJTUUH5QYQ
CRQVGaaKnwAAAKtJREFUGNNFyGd7wWAYBtCXUlW0FLXHLVrjpWLv0WFLjYj5//8H15OE8/EwZoirjA9MZYIqYX7UQyBJWJ4orPggn6n0M4UNGQ3sFA5kNXiheAXnPJf/KnA4KVwQRbFYKleqeKNwo1ZvoNlqd+Cm8ADdXh8D/g2PHj+/f8PReMJvMZ3NhYX0v/Tqgepq
vZGl7fpdjytltZNkn/8eUPaHYyAYYiyc0pzOkWiMXQAwDB/Bk13zwQAAACV0RVh0ZGF0ZTpjcmVhdGUAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMDkb0F0AAAAldEVYdGRhdGU6bW9kaWZ5ADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDBIRmjhAAAAAElFTkSuQmCC
"""
    remove_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAllBMVEX///83Z6QzY6IrWJYrWZYwX50nUpAsWpgjTYoqV5QpVJIhSockT4oxYaAwYJ8vX50v
XpwuXZstW5osWpgrWZd5msN/n8d9ncV8m8V6msR4mcN2l8J0lsFylMBmirlojbw1ZqQ1ZqU3aKY5aqg7bKk9bao/b6xBca1AcKsnU5EmUo8lUY4kT40jTowiTYohTIkhS4j////kRTrLAAAADXRSTlMAgfv7gfv7+/uB+/uBIADwiwAAAAFiS0dEAIgFHUgAAAAHdElN
RQflBhAJFBUZpoqfAAAARElEQVQY02NgoBNgZOLl4xcQFBIWYWYBC7CKiolLSEpJy8jKsYEF2OUVFJWUVVTV1DU4wAKcXJpa2jq6evoG3Dz0ciYAU8wEmV+EGfYAAAAldEVYdGRhdGU6Y3JlYXRlADIwMjEtMDYtMTZUMDc6MjA6MjErMDI6MDA5G9BdAAAAJXRFWHRk
YXRlOm1vZGlmeQAyMDIxLTA2LTE2VDA3OjIwOjIxKzAyOjAwSEZo4QAAAABJRU5ErkJggg==
"""
    up_png = """iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAhFBMVEX///+Ii4WIioWJiYaTlZGRk4+IioWFhYGQko2OkIuDhoCFhYF/gXyJi4eAgHx/gX16
fHeFh4J5fHaOkIyLjYh6fHh3d3J1eHJ2d3N0d3R3d3N2d3N1d3Tj4+H09PP9/f35+fnv7+3f4N2cnZjf39ze3tv4+Pfa29jJysfV1tPT09D///8aLa7GAAAAHXRSTlMAVvhU+/uQR/v7VEvB+1TZy/tUgfTCOsLZS0fBy7E7NWcAAAABYktHRACIBR1IAAAAB3RJTUUH
5QYQCRQVGaaKnwAAAHpJREFUGNN9jdkOgjAUBQ/7JmihIgrUKxRF/f//s23CFhPmbeaetIDBsi2scdzWdTYu7mJVlNODlqK967u5GPd8bypBKEhGMeJIkggT4NDSkGbqkqXD83UETuOb5Sh4gZx9xjNQXqorwL8cuNVNOf2sF/v8Lcwbu4uFHxIdCKWNYfvMAAAAJXRF
WHRkYXRlOmNyZWF0ZQAyMDIxLTA2LTE2VDA3OjIwOjIxKzAyOjAwORvQXQAAACV0RVh0ZGF0ZTptb2RpZnkAMjAyMS0wNi0xNlQwNzoyMDoyMSswMjowMEhGaOEAAAAASUVORK5CYII=
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
        self.setWindowTitle('Help & About')
        self.setFixedSize(600, 600)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.icon_label = QLabel()
        #self.icon_label.setPixmap(jpIcon.jitenpai_pxm)
        self.tag_label = QLabel('%s %s\n'
                                'Copyright (c) 2021, Urban Wallasch\n'
                                'BSD 3-Clause License\n'
                                'Contributors: volpol'
                                % (_JITENPAI_NAME, _JITENPAI_VERSION))
        self.tag_label.setAlignment(Qt.AlignCenter)
        self.hdr_layout = QHBoxLayout()
        self.hdr_layout.addWidget(self.icon_label, 1)
        self.hdr_layout.addWidget(self.tag_label, 100)
        self.help_pane = QTextEdit()
        self.help_pane.setReadOnly(True)
        self.help_pane.setStyleSheet('QTextEdit {border: none;}')
        self.help_pane.setHtml(_JITENPAI_HELP)
        self.qt_button = QPushButton('About Qt')
        self.qt_button.clicked.connect(lambda: QMessageBox.aboutQt(self))
        self.ok_button = QPushButton('Ok')
        self.ok_button.setIcon(jpIcon.ok)
        self.ok_button.clicked.connect(self.accept)
        self.btn_layout = QHBoxLayout()
        self.btn_layout.addWidget(self.qt_button)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.ok_button)
        self.dlg_layout = QVBoxLayout(self)
        self.dlg_layout.addLayout(self.hdr_layout)
        self.dlg_layout.addWidget(self.help_pane)
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
        self.path_edit = QPushButton(os.path.basename(path))
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
        self.resize(600, 600)
        # fonts
        fonts_group = zQGroupBox('Fonts')
        self.nfont_button = QPushButton('Normal Font')
        self.nfont_button.setMinimumWidth(130)
        self.nfont_button.clicked.connect(lambda: self.font_select(self.nfont_edit))
        self.nfont_edit = QLineEdit(cfg['nfont'] + ', ' + str(cfg['nfont_sz']))
        self.nfont_edit.setMinimumWidth(300)
        self.nfont_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lfont_button = QPushButton('Large Font')
        self.lfont_button.setMinimumWidth(130)
        self.lfont_button.clicked.connect(lambda: self.font_select(self.lfont_edit))
        self.lfont_edit = QLineEdit(cfg['lfont'] + ', ' + str(cfg['lfont_sz']))
        self.lfont_edit.setMinimumWidth(300)
        self.lfont_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.color_button = QPushButton('Highlight Color')
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
        fonts_layout.addRow('Sample', self.font_sample)
        # search options
        search_group = zQGroupBox('Search Options')
        self.search_deinflect = QCheckBox('&Verb Deinflection (experimental)')
        self.search_deinflect.setChecked(cfg['deinflect'])
        self.search_deinflect.setEnabled(_vc_loaded)
        search_layout = zQVBoxLayout(search_group)
        search_layout.addWidget(self.search_deinflect)
        search_layout.addSpacing(10)
        # dicts
        dicts_group = zQGroupBox('Dictionaries')
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
    def __init__(self, *args, title='', **kwargs):
        super().__init__(*args, **kwargs)
        self.init_ui(title)

    def init_ui(self, title=''):
        jpIcon()
        self.setWindowTitle(title)
        #self.setWindowIcon(jpIcon.jitenpai)
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
        # TODO: Tools menu
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
        for h in cfg['history']:
            self.search_box.insertItem(self.search_box.count(), h)
        self.search_box.setCurrentIndex(-1)
        self.search_box.setEditable(True)
        self.search_box.setMinimumWidth(400)
        self.search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_box_edit_style = self.search_box.lineEdit().styleSheet()
        self.search_box_edit_valid = True
        self.search_box.lineEdit().textChanged.connect(lambda t: self.search_onedit(t))
        QShortcut('Return', self.search_box).activated.connect(self.search)
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
        self.result_pane = QTextEdit()
        self.result_pane.setReadOnly(True)
        self.result_pane.setText('')
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
        self.search_box.lineEdit().setText(self.clipboard.text())
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

    def search_onedit(self, text):
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
        self.search_box.lineEdit().setText("")

    TERM_END = r'(\(.*\))?(;|$)'
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

    def _search_deinflected(self, dics, term, mode, limit):
        inflist = _vc_deinflect(term)
        re_isnoun = re.compile(r'\(n\)')
        result = []
        for inf in inflist:
            s_term = r'(^|;)' + inf[0] + self.TERM_END
            # perform lookup
            for d in dics:
                res = dict_lookup(d, s_term, mode, limit)
                for r in list(res):
                    # drop nouns
                    if re_isnoun.search(r[2]):
                        continue
                    # keep the rest, append inflection info
                    r.append(inf)
                    result.append(r)
                    limit -= 1
                self._search_show_progress()
                if limit <= 0:
                    break
        return result

    def search(self):
        self.search_box.setFocus()
        # validate input
        term = self.search_box.lineEdit().text().strip()
        if len(term) < 1:
            return
        if not self.search_box_edit_valid:
            self.search_box.lineEdit().setStyleSheet('QLineEdit { background-color: #ffc8b8; }');
            return
        self.search_box.lineEdit().setText(term)
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
        limit = self.genopt_limit.value() if self.genopt_limit.isEnabled() else cfg['hardlimit']
        # search
        self.result_group.setTitle('Search results: ...')
        QApplication.processEvents()
        mode = ScanMode.JAP if contains_cjk(term) else ScanMode.ENG
        if self.genopt_dict.isChecked():
            dics = [self.genopt_dictsel.itemData(self.genopt_dictsel.currentIndex())]
        else:
            dics = [x[1] for x in cfg['dicts']]
        result = []
        # search deinflected verb
        if cfg['deinflect'] and mode == ScanMode.JAP and _vc_loaded:
            result = self._search_deinflected(dics, term, mode, limit)
            limit -= len(result)
        # normal search
        rlen = len(result)
        while len(result) == rlen and limit > 0:
            # apply search options
            s_term = self._search_apply_options(term, mode)
            # perform lookup
            for d in dics:
                r = dict_lookup(d, s_term, mode, limit)
                self._search_show_progress()
                result.extend(r)
                limit -= len(r)
                if limit <= 0:
                    break
            # relax search options
            if len(result) == rlen and self.genopt_auto.isChecked():
                if not self._search_relax(mode):
                    break;
            else:
                break
        # report results
        rlen = len(result)
        self.result_group.setTitle('Search results: %d%s' % (rlen, '+' if rlen>=limit else ''))
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
        def hl_repl(match, org=None):
            grp = match.group(0) if org is None else org[match.span()[0]:match.span()[1]]
            return '%s%s</span>' % (hlfmt, grp)
        for idx, res in enumerate(result):
            if len(res) > 3:
                verb_message = '<span style="color:#bc3031;">Possible inflected verb or adjective:</span> %s<br>' % res[3][1]
                re_inf = re.compile(res[3][0], re.IGNORECASE)
            # render edict2 priority markers in small font (headwords only)
            res[0] = re_mark.sub(r'<small>\1</small>', res[0])
            # line break edict2 multi-headword entries
            res[0] = res[0].replace(';', '<br>')
            # for now just drop the edict2 entry number part,
            # in future this could be used to e.g. link somewhere relevant
            res[2] = re_entity.sub('', res[2])
            # highlight matches
            if mode == ScanMode.JAP:
                if len(res) > 3:
                    res[0] = re_inf.sub(lambda m: hl_repl(m, res[0]), kata2hira(res[0]))
                    res[1] = re_inf.sub(hl_repl, res[1])
                else:
                    res[0] = re_term.sub(lambda m: hl_repl(m, res[0]), kata2hira(res[0]))
                    res[1] = re_term.sub(hl_repl, res[1])
            else:
                res[2] = re_term.sub(hl_repl, res[2])
            # construct display line
            html[idx+1] = '<p>%s%s%s</span>%s %s</p>\n' \
                % ((verb_message if len(res)>3 else ''), \
                   lfmt, res[0],\
                   (' (%s)'%res[1] if len(res[1]) > 0 else ''),\
                   res[2])
        html[rlen + 1] = '</div>'
        self.result_pane.setHtml(''.join(html))
        self.result_pane.setEnabled(True)


############################################################
# dictionary lookup
#
# edict example lines:
# 〆日 [しめび] /(n) time limit/closing day/settlement day (payment)/deadline/
# ハート /(n) heart/(P)/

def dict_lookup(dict_fname, pattern, mode, limit=0):
    result = []
    cnt = 0
    try:
        with open(dict_fname) as dict_file:
            re_pattern = re.compile(pattern, re.IGNORECASE)
            for line in dict_file:
                try:
                    # manually splitting the line is actually faster than regex
                    p1 = line.split('[', 1)
                    if len(p1) < 2:
                        p1 = line.split('/', 1)
                        p2 = ['', p1[1]]
                    else:
                        p2 = p1[1].split(']', 1)
                    term = p1[0].strip()
                    hira = p2[0].strip()
                    trans = ' ' + p2[1].lstrip('/ ').rstrip(' \t\r\n').replace('/', '; ')
                except:
                    eprint('lookup:', line, ':', str(e))
                    continue
                if (mode == ScanMode.JAP and (re_pattern.search(hira) or re_pattern.search(kata2hira(term)))) \
                or (mode == ScanMode.ENG and re_pattern.search(trans)):
                    result.append([term, hira, trans])
                    cnt += 1
                    if limit and cnt >= limit:
                        break
    except Exception as e:
        eprint('lookup:', dict_fname, str(e))
    return result


############################################################
# main function

def main():
    _load_cfg()
    _vc_load()
    # set up window
    os.environ['QT_LOGGING_RULES'] = 'qt5ct.debug=false'
    app = QApplication(sys.argv)
    app.setApplicationName(_JITENPAI_NAME)
    root = jpMainWindow(title=_JITENPAI_NAME + ' ' + _JITENPAI_VERSION)
    root.show()
    die(app.exec_())

# run application
if __name__== "__main__":
    main()

# EOF
