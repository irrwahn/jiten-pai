#!/usr/bin/env python3

"""
kanjidic.py

This file is part of Jiten-pai.

Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>

Contributors:
    volpol

Jiten-pai is distributed under the Modified ("3-clause") BSD License.
See `LICENSE` file for more information.
"""


import io
import sys
import os
import re
import json
import base64
from argparse import ArgumentParser, RawTextHelpFormatter
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


_KANJIDIC_VERSION = '0.0.11'
_KANJIDIC_NAME = 'KanjiDic'
_KANJIDIC_DIR = 'jiten-pai'
_KANJIDIC_RADK = ['radkfile.utf8', 'radkfile2.utf8']
_KANJIDIC_KRAD = ['kradfile.utf8', 'kradfile2.utf8']

_JITENPAI_CFG = 'jiten-pai.conf'


############################################################
# utility functions and classes

def die(rc=0):
    sys.exit(rc)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Note: we only test for common CJK ideographs
_u_CJK_Uni = r'\u4e00-\u9FFF'

_re_kanji = re.compile('^[' + _u_CJK_Uni + ']$')

# test, if a single character /might/ be a kanji
def _is_kanji(s):
    return _re_kanji.match(s)

# try to locate a data file in some common prefixes:
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


############################################################
# configuration

cfg = {
    'kanjidic': '/usr/local/share/jiten-pai/kanjidic',
    'nfont': 'sans',
    'nfont_sz': 12.0,
    'lfont': 'IPAPMincho',
    'lfont_sz': 24.0,
    'hl_col': 'blue',
    'max_hist': 12,
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
# kanji <--> radical cross-reference

_srad = [''] * 20   # format: [ stroke_cnt -> 'radical_list' ]
_radk = dict()      # format: { 'radical': [stroke_cnt, 'kanji_list'], ... }
_krad = dict()      # format: { 'kanji': 'radical_list', ... }

def _rad_load(version):
    for x in range(len(_srad)):
        _srad[x] = ''
    _radk.clear()
    _krad.clear()
    res = True
    for v in range(version):
        radk_name = _KANJIDIC_RADK[v]
        if not os.access(radk_name, os.R_OK):
            radk_name = _get_dfile_path(os.path.join(_KANJIDIC_DIR, radk_name), mode=os.R_OK)
        try:
            with open(radk_name) as radk_file:
                re_radic = re.compile(r'^\$\s+(.)\s+(\d+)')
                re_kanji = re.compile(r'^([^#$]\S*)')
                radical = '?'
                for line in radk_file:
                    m = re_kanji.search(line)
                    if m:
                        _radk[radical][1] += m.group(1)
                        continue
                    m = re_radic.search(line)
                    if m:
                        radical = m.group(1)
                        if radical not in _radk:
                            stroke = int(m.group(2))
                            _radk[radical] = [stroke, '']
                            _srad[stroke] += radical
        except Exception as e:
            eprint('_rad_load:', radk_name, str(e))
            res = False
    for v in range(version):
        krad_name = _KANJIDIC_KRAD[v]
        if not os.access(krad_name, os.R_OK):
            krad_name = _get_dfile_path(os.path.join(_KANJIDIC_DIR, krad_name), mode=os.R_OK)
        try:
            with open(krad_name) as krad_file:
                re_krad = re.compile(r'^([^#\s]) : (.+)$')
                for line in krad_file:
                    m = re_krad.search(line)
                    if m:
                        _krad[m.group(1)] = m.group(2).replace(' ', '')
        except Exception as e:
            eprint('_rad_load:', krad_name, str(e))
            res = False
    return res

def _rad2k(rad):
    try:
        return _radk[rad]
    except:
        return ['', '']

def _k2rad(kanji):
    try:
        return _krad[kanji]
    except:
        return ''

# load kanjidic
# See: http://www.edrdg.org/kanjidic/kanjidic_doc_legacy.html#IREF02
#
# kanjidic1 example lines:
#
# 心 3F34 U5fc3 B61 G2 S4 XJ13D38 F157 J3 N1645 V1780 H11 DP11 DK4 DL4 L595
# DN639 K139 O49 DO80 MN10295 MP4.0937 E147 IN97 DA97 DS95 DF172 DH164 DT96
# DC64 DJ172 DB2.14 DG766 DM602 P1-1-3 I4k0.1 Q3300.0 DR358 ZPP4-4-4 Yxin1
# Wsim シン こころ -ごころ T2 りっしんべん {heart} {mind} {spirit} {heart radical (no. 61)}
#
# 逢 3029 U9022 B162 G9 S10 S9 S11 F2116 N4694 V6054 DP4002 DL2774 L2417
# DN2497 O1516 MN38901X MP11.0075 P3-3-7 I2q7.15 Q3730.4 DR2555 ZRP3-4-7
# Yfeng2 Wbong ホウ あ.う むか.える T1 あい おう {meeting} {tryst} {date} {rendezvous}
#
# 挨 3027 U6328 B64 G8 S10 F2258 N1910 V2160 DP510 DL383 L2248 DN1310 MN12082
# MP5.0229 DA1101 P1-3-7 I3c7.12 Q5303.4 DR1363 Yai1 Yai2 Wae アイ ひら.く
# {approach} {draw near} {push open}

_kanjidic = dict()     # format: { 'kanji': {info}, ...}

def _kanjidic1_load(dict_fname):
    ktable = [
        ['F', 'freq'],
        ['G', 'grade'],
        ['S', 'strokes'],
        ['W', 'r_korean'],
        ['Y', 'r_pinyin'],
    ]
    re_braces = re.compile(r'\{.*\}.*$')
    re_tags = re.compile(r'[BCFGJHNVDPSUIQMEKLOWYXZ]\S+')
    krad_set = 1
    try:
        with open(dict_fname) as dict_file:
            for line in dict_file:
                if line[0] in '# ':
                    if 'KANJD212' in line:
                        krad_set = 2
                    continue
                info = {
                    'strokes': '',
                    'readings': '',
                    'r_korean': '',
                    'r_pinyin': '',
                    'meaning': '',
                    'freq': '',
                    'grade': '',
                }
                kanji = line[0]
                # skip kanji and JIS code
                line = line[6:]
                # save meaning
                m = re_braces.search(line)
                if m:
                    info['meaning'] = m.group(0).replace('{', '').replace('}', ';').strip()
                    line = re_braces.sub('', line)
                # get tags
                tlist = []
                while True:
                    m = re_tags.search(line)
                    if m is None:
                        break;
                    tlist.append(m.group(0))
                    line = re_tags.sub('', line, 1)
                for t in tlist:
                    for k in ktable:
                        # if a tag appears more than once the first one wins,
                        # e.g. 'S<num>' (stroke count)
                        if t[:len(k[0])] == k[0] and not info[k[1]]:
                            info[k[1]] = t[len(k[0]):]
                            break
                # get readings (i.e. all that's left)
                info['readings'] = line.strip().replace(' ', ', ').replace('T2,', 'T2').replace('T1,', 'T1')
                _kanjidic[kanji] = info
    except Exception as e:
        eprint('_kanjidic1_load:', dict_fname, str(e))
        return False, 0, 0
    return True, 1, krad_set

# load kanjidic2.xml
# See: http://www.edrdg.org/wiki/index.php/KANJIDIC_Project#Content_.26_Format

import xml.etree.ElementTree as ET

def _kanjidic2_load(dict_fname):
    try:
        for char in ET.parse(dict_fname).iterfind('character'):
            kanji = char.find('literal').text
            info = {
                'strokes': '',
                'readings': '',
                'r_korean': '',
                'r_pinyin': '',
                'meaning': '',
                'freq': '',
                'grade': '',
            }
            misc = char.find('misc')
            for strokes in misc.findall('stroke_count'):
                info['strokes'] = strokes.text
                break
            for freq in misc.findall('freq'):
                info['freq'] = freq.text
                break
            for grade in misc.findall('grade'):
                info['grade'] = grade.text
                break
            rm = char.find('reading_meaning')
            if rm:
                rm_group = rm.find('rmgroup')
                for rd in rm_group.findall('reading'):
                    r_type = rd.attrib['r_type']
                    if r_type == 'korean_r':
                        info['r_korean'] = rd.text
                    elif r_type == 'pinyin':
                        info['r_pinyin'] = rd.text
                    elif r_type[:3] == 'ja_':
                        info['readings'] += '%s, ' % rd.text
                for m in rm_group.findall('meaning'):
                    if m.attrib.get('m_lang', 'en') == 'en':
                        info['meaning'] += '%s; ' % m.text
                nanori = ''
                for n in rm.findall('nanori'):
                    nanori += '%s, ' % n.text
                if nanori:
                    info['readings'] += 'T1 %s' % nanori
            rad_name = ''
            for n in misc.findall('rad_name'):
                rad_name +=  '%s, ' % n.text
            if rad_name:
                info['readings'] += 'T2 %s' % rad_name
            info['readings'] = info['readings'].rstrip(', ')
            _kanjidic[kanji] = info
    except Exception as e:
        eprint('_kanjidic2_load:', dict_fname, str(e))
        return False, 0, 0
    return True, 2, 2

def _kanjidic_load(dict_fname):
    _kanjidic.clear()
    tag_line = ''
    try:
        with open(dict_fname) as f:
            tag_line = f.readline()
        if '<?xml' in tag_line:
            return _kanjidic2_load(dict_fname)
        return _kanjidic1_load(dict_fname)
    except Exception as e:
        eprint('_kanjidic_load:', dict_fname, str(e))
    return False, 0, 0

def _kanjidic_lookup(kanji):
    try:
        kanji = kanji[0]
        res = {
            'kanji': kanji,
            'radicals': _k2rad(kanji),
        }
        res.update(_kanjidic[kanji])
    except:
        res = {}
    return res

def _kanjidic_full_text_search(dict_fname, text):
    kanji = ''
    try:
        with open(dict_fname) as dict_file:
            for line in dict_file:
                if line[0] in '# ':
                    continue
                if text in line.lower():
                    kanji += line[0]
    except Exception as e:
        eprint('_kanjidic_full_text_search:', dict_fname, str(e))
    return kanji

def _s2kanji(min_strokes, max_strokes=-1):
    if max_strokes < 0:
        max_strokes = min_strokes
    res = ''
    for k, v in _kanjidic.items():
        try:
            s = int(v['strokes'])
        except:
            continue
        if min_strokes <= s <= max_strokes:
            res += k
    return res


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
    jiten_pai_png = """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
"""
    def __new__(cls):
        if cls.initialized:
            return
        cls.initialized = True
        jpIcon.jiten_pai_pxm = sQPixmap(imgdata=jpIcon.jiten_pai_png)
        jpIcon.jiten_pai = QIcon(jpIcon.jiten_pai_pxm)


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

class zQFormLayout(QFormLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSpacing(0)
        self.setContentsMargins(0,0,0,0)
        self.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setFormAlignment(Qt.AlignLeft | Qt.AlignVCenter)

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
        pos = event.pos()
        pos.setX(pos.x() - 15)
        scr = self.verticalScrollBar().value()
        old_tcur = self.textCursor()
        tcur = self.cursorForPosition(pos)
        self.setTextCursor(tcur)
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

# adapted from Qt flow layout C++ example
# stripped down and optimized for speed in our special use case
class zFlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.itemList = list()

    def addItem(self, item):
        self.itemList.append(item)

    def insertWidgetTop(self, widget):
        self.addWidget(widget)
        if len(self.itemList) > 1:
            self.itemList = self.itemList[-1:] + self.itemList[:-1]

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        try:
            return self.itemList[index]
        except:
            return None

    def takeAt(self, index):
        try:
            return self.itemList.pop(index)
        except:
            return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        self.doLayout(rect, False)

    def sizeHint(self):
        return QSize()

    def doLayout(self, rect, testonly):
        if not self.count():
            return 0
        x = rect.x()
        y = rect.y()
        right = rect.right() + 1
        iszhint = self.itemList[0].widget().sizeHint()
        iwidth = iszhint.width()
        iheight = iszhint.height()
        for i in range(self.count()):
            nextX = x + iwidth
            if nextX > right:
                x = rect.x()
                y = y + iheight
                nextX = x + iwidth
            if not testonly:
                self.itemList[i].setGeometry(QRect(QPoint(x, y), iszhint))
            x = nextX
        return y + iheight - rect.y()

    def sort(self, sort_fnc):
        srt = iter(sorted([x.widget().text() for x in self.itemList], key=sort_fnc))
        for item in self.itemList:
            item.widget().setText(next(srt))

class zFlowScrollArea(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clear(self):
        if self.widget():
            self.takeWidget().deleteLater()

    def fill(self, tiles):
        self.setUpdatesEnabled(False)
        self.clear()
        pane = QWidget()
        self.setWidget(pane)
        layout = zFlowLayout(pane)
        layout.setEnabled(False)
        for tl in tiles:
            layout.addWidget(tl)
        layout.setEnabled(True)
        self.setUpdatesEnabled(True)

    def insert_top_uniq(self, w):
        self.setUpdatesEnabled(False)
        if self.widget():
            layout = self.widget().layout()
        else:
            pane = QWidget()
            self.setWidget(pane)
            layout = zFlowLayout(pane)
        for idx in range(layout.count()):
            if layout.itemAt(idx).widget().text() == w.text():
                layout.takeAt(idx)
                break
        layout.insertWidgetTop(w)
        self.setUpdatesEnabled(True)

    def sort(self, sort_fnc):
        self.widget().layout().sort(sort_fnc)

class zKanjiButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setContentsMargins(QMargins(0,0,0,0))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(None)
        self.setContentsMargins(QMargins(0,0,0,0))
        self.click_action = None
        self.clicked.connect(self._click)
        self.setFont(QFont(cfg['lfont']))

    def _click(self):
        if self.click_action:
            self.click_action(self)

    def sizeHint(self):
        return QSize(58, 58)

    def resizeEvent(self, event):
        sz = min(self.rect().height(), self.rect().width()) - 6
        font = self.font()
        font.setPixelSize(sz)
        self.setFont(font)

class zRadicalButton(zKanjiButton):
    def __init__(self, *args, is_sep=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_sep = is_sep
        self.setCheckable(not self.is_sep)
        self.toggle_action = None
        self.toggled.connect(self._toggle)

    def _toggle(self):
        self.setStyleSheet("background-color: lightyellow" if self.isChecked() else None)
        if self.toggle_action:
            self.toggle_action(self)

    def sizeHint(self):
        return QSize(24, 24)

class kdRadicalList(QDialog):
    btns = []
    vis_changed = pyqtSignal(bool)

    def __init__(self, *args, toggle_action=None, geo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.toggle_action = toggle_action
        self._init_ui(geo)

    def _init_ui(self, geo):
        self.setWindowTitle('Radical List')
        self.layout = QGridLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(QMargins(5,5,5,5))
        self.row = 0
        self.col = 0
        for stroke in range(len(_srad)):
            if not len(_srad[stroke]):
                continue
            sep = zRadicalButton(str(stroke), is_sep=True)
            sep.setEnabled(False)
            sep.setStyleSheet('background-color: %s; color: #ffffff; border: none;' % cfg['hl_col'])
            self._add_widget(sep)
            for rad in _srad[stroke]:
                btn = zRadicalButton(rad)
                btn.is_sep = False
                self._add_widget(btn)
        if geo is not None:
            self.setGeometry(geo)
        else:
            self.resize(600, 600)
        QShortcut('Ctrl+Q', self).activated.connect(self.close)
        QShortcut('Ctrl+W', self).activated.connect(self.close)

    def _add_widget(self, w):
        w.toggle_action = self.toggle_action
        self.btns.append(w)
        self.layout.addWidget(w, self.row, self.col)
        self.col += 1
        if self.col >= 18:
            self.col = 0
            self.row += 1

    def show(self):
        self.vis_changed.emit(True)
        self.update_btns(None)
        super().show()

    def reject(self):
        self.vis_changed.emit(False)
        super().reject()

    def update_btns(self, rads):
        for btn in self.btns:
            if btn.is_sep:
                btn.setStyleSheet('background-color: %s; color: #ffffff; border: none;' % cfg['hl_col'])
                continue
            if rads is not None:
                btn.toggle_action = None
                btn.setChecked(btn.text() in rads)
                btn.toggle_action = self.toggle_action

    def set_avail(self, avail):
        if avail is None:
            for btn in self.btns:
                if not btn.is_sep:
                    btn.setEnabled(True)
        else:
            for btn in self.btns:
                if not btn.isChecked() and not btn.is_sep:
                    btn.setEnabled(btn.text() in avail)


############################################################
# main window class

class kdMainWindow(QDialog):
    kanji_click = pyqtSignal(str)
    dic_ok = True
    radlist = None

    def __init__(self, *args, parent=None, title=_KANJIDIC_NAME + ' ' + _KANJIDIC_VERSION, cl_args=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent = parent
        if parent:
            global _standalone
            _standalone = False
        self.setModal(False)
        self.setParent(None, self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.init_cfg()
        self.clipboard = QApplication.clipboard()
        self.init_ui(title)
        QShortcut('Ctrl+Q', self).activated.connect(lambda: self.close())
        QShortcut('Ctrl+W', self).activated.connect(lambda: self.close())
        QShortcut('Ctrl+C', self).activated.connect(self.kbd_copy)
        QShortcut('Ctrl+V', self).activated.connect(self.kbd_paste)
        QApplication.processEvents()
        # load dic files
        self.init_dic()
        # evaluate command line arguments
        if cl_args is not None:
            if cl_args.kanji_lookup:
                self.show_info(cl_args.kanji_lookup)
            elif cl_args.clip_kanji:
                self.show_info(self.clipboard.text())

    def init_dic(self):
        # load radkfile, kradfile, kanjidic
        self.dic_ok, version, krad_set = _kanjidic_load(cfg['kanjidic'])
        if not self.dic_ok:
            self.show_error('Error loading kanjidic!')
            return
        # disable full text search for the XML version
        self.text_search_check.setVisible(version < 2)
        self.text_search_box.setVisible(version < 2)
        self.text_search_clearbtn.setVisible(version < 2)
        if not _rad_load(krad_set):
            self.show_error('Error loading radkfile/kradfile!')
            self.dic_ok = False

    def init_cfg(self):
        _load_cfg()

    def init_ui(self, title=''):
        jpIcon()
        self.setWindowTitle(title)
        self.setWindowIcon(jpIcon.jiten_pai)
        self.resize(730, 600)
        self.clipboard = QApplication.clipboard()
        # search options
        self.opt_group = zQGroupBox('Kanji Search Options:')
        # stroke search
        self.stroke_search_check = QCheckBox('Search By &Strokes:')
        self.stroke_search_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.stroke_search_num = QSpinBox()
        self.stroke_search_num.setRange(1, 30)
        self.stroke_search_tol_label = QLabel('+/-')
        self.stroke_search_tol_label.setAlignment(Qt.AlignRight)
        self.stroke_search_tol = QSpinBox()
        stroke_search_layout = zQHBoxLayout()
        stroke_search_layout.addWidget(self.stroke_search_num, 1)
        stroke_search_layout.addWidget(self.stroke_search_tol_label, 1)
        stroke_search_layout.addWidget(self.stroke_search_tol, 1)
        stroke_search_layout.addStretch(999)
        # radical search
        self.rad_search_check = QCheckBox('Search By R&adical:')
        self.rad_search_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.rad_search_box = QComboBox()
        self.rad_search_box.setMinimumWidth(200)
        self.rad_search_box.setMaximumWidth(340)
        self.rad_search_box.setMaxCount(int(cfg['max_hist']))
        self.rad_search_box.setCurrentIndex(-1)
        self.rad_search_box.setEditable(True)
        self.rad_search_box.lineEdit().textChanged.connect(self.on_rad_search_edit)
        self.rad_search_box.lineEdit().textEdited.connect(lambda: self.update_search())
        self.rad_search_box.lineEdit().returnPressed.connect(lambda: self.update_search(save_rad_hist=True))
        self.rad_search_box.activated.connect(lambda: self.update_search())
        self.rad_search_clearbtn = QPushButton('&Clear')
        self.rad_search_clearbtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rad_search_clearbtn.clicked.connect(self.on_rad_search_clear)
        self.rad_search_clearbtn.setDefault(False)
        self.rad_search_clearbtn.setAutoDefault(False)
        self.rad_search_listbtn = QPushButton('&Radical List')
        self.rad_search_listbtn.setToolTip('Toggle interactive radical list.')
        self.rad_search_listbtn.setCheckable(True)
        self.rad_search_listbtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rad_search_listbtn.clicked.connect(lambda: self.show_radlist(self.rad_search_listbtn.isChecked()))
        self.rad_search_listbtn.setDefault(False)
        self.rad_search_listbtn.setAutoDefault(False)
        rad_search_layout = zQHBoxLayout()
        rad_search_layout.addWidget(self.rad_search_box, 10)
        rad_search_layout.addWidget(self.rad_search_clearbtn, 1)
        rad_search_layout.addWidget(self.rad_search_listbtn, 1)
        # full text search
        self.text_search_check = QCheckBox('Full Text Search:')
        self.text_search_check.setToolTip('Perform a case insensitive full text search in raw kanjidic file.')
        self.text_search_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.text_search_box = QComboBox()
        self.text_search_box.setMinimumWidth(200)
        self.text_search_box.setMaximumWidth(340)
        self.text_search_box.setMaxCount(int(cfg['max_hist']))
        self.text_search_box.setCurrentIndex(-1)
        self.text_search_box.setEditable(True)
        self.text_search_box.lineEdit().returnPressed.connect(lambda: self.update_search(save_text_hist=True))
        self.text_search_box.activated.connect(lambda: self.update_search())
        self.text_search_clearbtn = QPushButton('&Clear')
        self.text_search_clearbtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.text_search_clearbtn.clicked.connect(self.text_search_box.clearEditText)
        self.text_search_clearbtn.setDefault(False)
        self.text_search_clearbtn.setAutoDefault(False)
        text_search_layout = zQHBoxLayout()
        text_search_layout.addWidget(self.text_search_box, 10)
        text_search_layout.addWidget(self.text_search_clearbtn, 1)
        # result sorting
        self.sort_check = QCheckBox('S&ort Results by:')
        self.sort_stroke = QRadioButton('Strokes')
        self.sort_radic = QRadioButton('Radicals')
        self.sort_codep = QRadioButton('Codepoint')
        self.sort_stroke.setChecked(True)
        sort_layout = zQHBoxLayout()
        sort_layout.addWidget(self.sort_stroke, 1)
        sort_layout.addSpacing(10)
        sort_layout.addWidget(self.sort_radic, 1)
        sort_layout.addSpacing(10)
        sort_layout.addWidget(self.sort_codep, 1)
        sort_layout.addStretch(999)
        # search option layout
        opt_layout = zQFormLayout()
        opt_layout.addRow(self.stroke_search_check, stroke_search_layout )
        opt_layout.addRow(self.rad_search_check, rad_search_layout )
        opt_layout.addRow(self.text_search_check, text_search_layout )
        opt_layout.addRow(self.sort_check, sort_layout )
        self.opt_group.setLayout(opt_layout)
        # search results
        self.result_group = zQGroupBox('Search Results:')
        self.result_area = zFlowScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        result_layout = zQVBoxLayout()
        result_layout.addWidget(self.result_area)
        self.result_group.setLayout(result_layout)
        # info area
        self.info_group = zQGroupBox('Kanji Info:')
        global _standalone
        if not _standalone:
            self.info_pane = zQTextEdit()
            self.info_pane.kanji_click.connect(self.kanji_click)
        else:
            self.info_pane = QTextEdit()
        self.info_pane.setReadOnly(True)
        self.info_pane.setText('')
        self.info_hist = zFlowScrollArea()
        self.info_hist.setWidgetResizable(True)
        self.info_hist.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.info_hist.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        info_layout = zQHBoxLayout()
        info_layout.addWidget(self.info_pane, 7)
        info_layout.addWidget(self.info_hist, 1)
        self.info_group.setLayout(info_layout)
        # set up main window layout
        splitter = QSplitter()
        splitter.setOrientation(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.addWidget(self.result_group)
        splitter.addWidget(self.info_group)
        main_layout = zQVBoxLayout(self)
        main_layout.addWidget(self.opt_group, 1)
        main_layout.addSpacing(5)
        main_layout.addWidget(splitter, 999)
        # initialize search options
        self.stroke_search_check.toggled.connect(self.stroke_search_toggle)
        self.stroke_search_num.valueChanged.connect(self.update_search)
        self.stroke_search_tol.valueChanged.connect(self.update_search)
        self.stroke_search_check.setChecked(True)
        self.stroke_search_check.setChecked(False)
        self.rad_search_check.toggled.connect(self.rad_search_toggle)
        self.rad_search_check.setChecked(True)
        self.rad_search_check.setChecked(False)
        self.text_search_check.toggled.connect(self.text_search_toggle)
        self.text_search_check.setChecked(True)
        self.text_search_check.setChecked(False)
        self.sort_check.toggled.connect(self.sort_toggle)
        self.sort_stroke.toggled.connect(self.sort_toggle)
        self.sort_radic.toggled.connect(self.sort_toggle)
        self.sort_codep.toggled.connect(self.sort_toggle)
        self.sort_check.setChecked(True)
        self.sort_check.setChecked(False)

    def reject(self):
        if self.radlist:
            self.radlist.close()
        super().reject()

    def keyPressEvent(self, event):
        if event.key() != Qt.Key_Escape or self._parent:
            super().keyPressEvent(event)

    def show(self):
        _load_cfg()
        if self.radlist:
            self.radlist.update_btns(None)
            self.radlist.update()
        super().show()

    def kbd_copy(self):
        self.clipboard.setText(self.info_pane.textCursor().selectedText())

    def kbd_paste(self):
        if self.rad_search_check.isChecked():
            self.rad_search_box.setCurrentText(self.clipboard.text())
            self.rad_search_box.setFocus()
            self.update_search()

    def show_error(self, msg=''):
        msg = '<span style="color:red;">%s</span>\n' % msg
        self.info_pane.setHtml(self.info_pane.toHtml() + msg)

    def show_radlist(self, show=True):
        if show:
            if not self.radlist:
                x, y, w, h = self.geometry().getRect()
                fw = self.frameGeometry().width()
                geo = QRect(x + fw, y, min(w, 600), max(h, 600))
                self.radlist = kdRadicalList(toggle_action=self.on_radical_toggled, geo=geo)
                self.radlist.vis_changed.connect(self.radlist_vis_changed)
                self.on_rad_search_edit()
                self.update_search()
            self.radlist.update_btns(None)
            self.radlist.show()
            self.radlist.activateWindow()
        elif self.radlist:
            self.radlist.hide()

    def radlist_vis_changed(self, visible):
        self.rad_search_listbtn.setChecked(visible)

    def stroke_search_toggle(self):
        en = self.stroke_search_check.isChecked()
        self.stroke_search_num.setEnabled(en)
        self.stroke_search_tol_label.setEnabled(en)
        self.stroke_search_tol.setEnabled(en)
        self.update_search()

    def rad_search_toggle(self):
        en = self.rad_search_check.isChecked()
        self.rad_search_box.setEnabled(en)
        self.rad_search_clearbtn.setEnabled(en)
        self.rad_search_listbtn.setEnabled(en)
        if self.radlist and self.rad_search_listbtn.isChecked():
            self.radlist.setVisible(en)
        self.update_search()

    def text_search_toggle(self):
        en = self.text_search_check.isChecked()
        self.text_search_box.setEnabled(en)
        self.text_search_clearbtn.setEnabled(en)
        self.update_search()

    def sort_toggle(self, checked):
        en = self.sort_check.isChecked()
        self.sort_stroke.setEnabled(en)
        self.sort_radic.setEnabled(en)
        self.sort_codep.setEnabled(en)
        if checked:
            self.sort_results()

    def on_rad_search_clear(self):
        self.rad_search_box.clearEditText()
        if self.radlist:
            self.radlist.set_avail(None)

    def on_rad_search_edit(self):
        if self.radlist:
            rads = self.rad_search_box.currentText()
            self.radlist.update_btns(rads)

    def on_radical_toggled(self, btn):
        rads = self.rad_search_box.currentText()
        r = btn.text()[0]
        if btn.isChecked() and not r in rads:
            rads += r
        else:
            rads = rads.replace(r, '')
        self.rad_search_box.setCurrentText(rads)
        self.update_search()

    def on_kanji_btn_clicked(self, btn):
        self.show_info(btn.text())

    def update_search(self, save_rad_hist=False, save_text_hist=False):
        sets = []
        # add kanji set based on stroke count
        if self.stroke_search_check.isChecked():
            strokes = self.stroke_search_num.value()
            tolerance = self.stroke_search_tol.value()
            sets.append(set(_s2kanji(strokes - tolerance, strokes + tolerance)))
        # add kanji set for each radical
        rads = ''
        if self.rad_search_check.isChecked():
            rads = self.rad_search_box.currentText().strip()
            if len(rads):
                # save to history
                if save_rad_hist:
                    self.rad_search_box.setCurrentText(rads)
                    for i in range(self.rad_search_box.count()):
                        if self.rad_search_box.itemText(i) == rads:
                            self.rad_search_box.removeItem(i)
                            break
                    self.rad_search_box.insertItem(0, rads)
                    self.rad_search_box.setCurrentIndex(0)
                # add sets
                for rad in rads:
                    sets.append(set(_rad2k(rad)[1]))
        # add kanji set based on full text search
        if self.text_search_check.isChecked():
            text = self.text_search_box.currentText().strip()
            if len(text):
                # save to history
                text = text.lower()
                if save_text_hist:
                    for i in range(self.text_search_box.count()):
                        if self.text_search_box.itemText(i).lower() == text:
                            self.text_search_box.removeItem(i)
                            break
                    self.text_search_box.insertItem(0, text)
                    self.text_search_box.setCurrentIndex(0)
                else:
                    self.text_search_box.setCurrentText(text)
                # add set
                sets.append(set(_kanjidic_full_text_search(cfg['kanjidic'], text)))
        # get intersection of all kanji sets
        res = {}
        if len(sets) > 0:
            res = sets[0]
            for s in sets[1:]:
                res = res.intersection(s)
        # update search results pane
        self.result_group.setTitle('Search Results: %d' % len(res))
        self.result_area.clear()
        QApplication.processEvents()
        av_rads = ''
        tiles = []
        for r in res:
            btn = zKanjiButton(r)
            btn.click_action = self.on_kanji_btn_clicked
            tiles.append(btn)
            if self.radlist:
                av_rads += _k2rad(r)
        self.result_area.fill(tiles)
        self.sort_results()
        if len(res) == 1:
            self.show_info(list(res)[0])
        # update list of possible radicals
        if self.radlist:
            self.radlist.set_avail(set(av_rads) if rads or av_rads else None)

    def sort_results(self):
        if self.sort_check.isChecked():
            if self.sort_stroke.isChecked():
                key = lambda k: int(_kanjidic_lookup(k)['strokes'])
            elif self.sort_radic.isChecked():
                key = lambda k: _kanjidic_lookup(k)['radicals']
            else: # self.sort_codep
                key = lambda k: ord(k)
            self.result_area.sort(key)

    def show_info(self, kanji=''):
        if not self.dic_ok:
            return
        self.show()
        if kanji:
            # insert into history
            btn = zKanjiButton(kanji)
            btn.click_action = self.on_kanji_btn_clicked
            self.info_hist.insert_top_uniq(btn)
            self.info_hist.verticalScrollBar().setValue(0)
            # limit history length
            while self.info_hist.widget().layout().takeAt(int(cfg['max_hist'])):
                pass
        info = ['']
        res = _kanjidic_lookup(kanji)
        nfmt = '<div style="font-family:%s;font-size:%.1fpt">' % (cfg['nfont'], cfg['nfont_sz'])
        lfmt = '<span style="font-family:%s;font-size:%.1fpt;">' % (cfg['lfont'], cfg['lfont_sz'])
        hlfmt = '<span style="color:%s;">' % cfg['hl_col']
        info.append(nfmt)
        for k, v in res.items():
            line = hlfmt
            if k == 'kanji':
                line += 'Kanji:</span> %s%s</span><br>\n' % (lfmt, v)
            elif k == 'radicals':
                line += 'Radicals:</span> %s<br>\n' % v
            elif k == 'strokes':
                line += 'Stroke count:</span> %s<br>\n' % v
            elif k == 'readings':
                line += 'Readings:</span> %s<br>\n' % v.replace('T2', 'Radical Name:').replace('T1', 'Name Readings:')
            elif k == 'r_korean':
                line += 'Romanized Korean reading:</span> %s<br>\n' % v
            elif k == 'r_pinyin':
                line += 'Romanized Pinyin reading:</span> %s<br>\n' % v
            elif k == 'meaning':
                line += 'English meaning:</span> %s<br>\n' % v
            elif k == 'freq':
                line += 'Frequency number:</span> %s<br>\n' % v
            elif k == 'grade':
                line += 'Jouyou grade level:</span> %s<br>\n' % v
            else:
                line += '%s:</span> %s<br>\n' % (k, v)
            info.append(line)
        info.append('</div>')
        self.info_pane.setHtml(''.join(info))


############################################################
# main function

def _parse_cmdline():
    parser = ArgumentParser(
        formatter_class=lambda prog: RawTextHelpFormatter(prog, max_help_position=40),
        description='Jiten-pai kanji dictionary',
        epilog='Only one of these options should be used at a time.\n'
    )
    parser.add_argument('-c', '--clip-kanji', action='count', help='look up kanji from clipboard')
    parser.add_argument('-l', '--kanji-lookup', metavar='KANJI', help='look up KANJI in kanji dictionary')
    return parser.parse_args()

def _main():
    global _standalone
    _standalone = True
    cl_args = _parse_cmdline()
    os.environ['QT_LOGGING_RULES'] = 'qt5ct.debug=false'
    app = QApplication(sys.argv)
    app.setApplicationName(_KANJIDIC_NAME)
    root = kdMainWindow(cl_args=cl_args)
    root.show()
    sys.exit(app.exec_())

if __name__== "__main__":
    _main()
