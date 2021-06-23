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
from argparse import ArgumentParser, RawTextHelpFormatter
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


_KANJIDIC_VERSION = '0.0.10'
_KANJIDIC_NAME = 'KanjiDic'
_KANJIDIC_DIR = 'jiten-pai'
_KANJIDIC_RADK = 'radkfile.utf8'
_KANJIDIC_KRAD = 'kradfile.utf8'

_JITENPAI_CFG = 'jiten-pai.conf'


############################################################
# utility functions and classes

def die(rc=0):
    sys.exit(rc)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def is_kanji(s):
    return True if re.match("^[\u4e00-\u9FFF]$", s) else False

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

def _rad_load():
    res = True
    radk_name = _KANJIDIC_RADK
    if not os.access(radk_name, os.R_OK):
        radk_name = _get_dfile_path(os.path.join(_KANJIDIC_DIR, _KANJIDIC_RADK), mode=os.R_OK)
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
                    stroke = int(m.group(2))
                    _radk[radical] = [stroke, '']
                    _srad[stroke] += m.group(1)
    except Exception as e:
        eprint('_rad_load:', radk_name, str(e))
        res = False
    krad_name = _KANJIDIC_KRAD
    if not os.access(krad_name, os.R_OK):
        krad_name = _get_dfile_path(os.path.join(_KANJIDIC_DIR, _KANJIDIC_KRAD), mode=os.R_OK)
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
# kanjidic example lines:
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

def _kanjidic_load(dict_fname):
    ktable = [
        ['F', 'freq'],
        ['G', 'grade'],
        ['S', 'strokes'],
        ['W', 'r_korean'],
        ['Y', 'r_pinyin'],
    ]
    re_braces = re.compile(r'\{.*\}.*$')
    re_tags = re.compile(r'[BCFGJHNVDPSUIQMEKLOWYXZ]\S+')
    try:
        with open(dict_fname) as dict_file:
            for line in dict_file:
                if line[0] in '# ':
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
                m = re_braces.search(line).group(0)
                info['meaning'] = m.replace('{', '').replace('}', ';').strip()
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
        print('_kanjidic_load:', dict_fname, str(e))
        return False
    return True

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
        print('_kanjidic_full_text_search:', dict_fname, str(e))
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
        old_tcur = self.textCursor()
        tcur = self.cursorForPosition(pos)
        self.setTextCursor(tcur)
        tcur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor);
        char = tcur.selectedText()
        scr = self.verticalScrollBar().value()
        self.setTextCursor(old_tcur)
        self.verticalScrollBar().setValue(scr)
        if is_kanji(char):
            self.kanji = char
            self._override_cursor()
        else:
            self.kanji = ''
            self._restore_cursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.kanji and len(self.textCursor().selectedText()) < 1:
            self.kanji_click.emit(self.kanji)

    def leaveEvent(self, event):
        self.kanji = ''
        self._restore_cursor()

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCheckable(True)
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
            sep = zRadicalButton(str(stroke))
            sep.setEnabled(False)
            sep.setStyleSheet('background-color: %s; color: #ffffff; border: none;' % cfg['hl_col'])
            sep.is_sep = True
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

    def update(self, rads):
        for btn in self.btns:
            btn.toggle_action = None
            btn.setChecked(False)
            for r in rads:
                if btn.text() == r:
                    btn.setChecked(True)
                    break
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
        # load radkfile, kradfile, kanjidic
        if not _rad_load():
            self.show_error('Error loading radkfile/kradfile!')
            self.dic_ok = False
        if not _kanjidic_load(cfg['kanjidic']):
            self.show_error('Error loading kanjidic!')
            self.dic_ok = False
        # evaluate command line arguments
        if cl_args is not None:
            if cl_args.kanji_lookup:
                self.show_info(cl_args.kanji_lookup)
            elif cl_args.clip_kanji:
                self.show_info(self.clipboard.text())

    def init_cfg(self):
        _load_cfg()

    def init_ui(self, title=''):
        #jpIcon()
        self.setWindowTitle(title)
        #self.setWindowIcon(jpIcon.jitenpai)
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
        self.rad_search_box.setCurrentIndex(-1)
        self.rad_search_box.setEditable(True)
        self.rad_search_box.lineEdit().textChanged.connect(self.on_search_edit)
        self.rad_search_box.lineEdit().textEdited.connect(self.update_search)
        self.rad_search_box.lineEdit().returnPressed.connect(self.update_search)
        self.rad_search_box.activated.connect(self.update_search)
        self.rad_search_clearbtn = QPushButton('&Clear')
        self.rad_search_clearbtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rad_search_clearbtn.clicked.connect(self.on_search_clear)
        self.rad_search_clearbtn.setDefault(False)
        self.rad_search_clearbtn.setAutoDefault(False)
        self.rad_search_listbtn = QPushButton('&Radical List')
        self.rad_search_listbtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rad_search_listbtn.clicked.connect(self.show_radlist)
        self.rad_search_listbtn.setDefault(False)
        self.rad_search_listbtn.setAutoDefault(False)
        rad_search_layout = zQHBoxLayout()
        rad_search_layout.addWidget(self.rad_search_box, 10)
        rad_search_layout.addWidget(self.rad_search_clearbtn, 1)
        rad_search_layout.addWidget(self.rad_search_listbtn, 1)
        # full text search
        text_search_layout = zQHBoxLayout()
        self.text_search_check = QCheckBox('Full Text Search:')
        self.text_search_check.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.text_search_box = QComboBox()
        self.text_search_box.setMinimumWidth(200)
        self.text_search_box.setMaximumWidth(340)
        self.text_search_box.setCurrentIndex(-1)
        self.text_search_box.setEditable(True)
        self.text_search_box.lineEdit().textChanged.connect(self.on_search_edit)
        self.text_search_box.lineEdit().returnPressed.connect(self.update_search)
        self.text_search_box.activated.connect(self.update_search)
        self.text_search_clearbtn = QPushButton('&Clear')
        self.text_search_clearbtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.text_search_clearbtn.clicked.connect(lambda: self.text_search_box.lineEdit().setText(''))
        self.text_search_clearbtn.setDefault(False)
        self.text_search_clearbtn.setAutoDefault(False)
        text_search_layout = zQHBoxLayout()
        text_search_layout.addWidget(self.text_search_box, 10)
        text_search_layout.addWidget(self.text_search_clearbtn, 1)
        # search option layout
        opt_layout = zQFormLayout()
        opt_layout.addRow(self.stroke_search_check, stroke_search_layout )
        opt_layout.addRow(self.rad_search_check, rad_search_layout )
        opt_layout.addRow(self.text_search_check, text_search_layout )
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
        main_layout = zQVBoxLayout(self)
        main_layout.addWidget(self.opt_group, 1)
        main_layout.addWidget(self.result_group, 20)
        main_layout.addSpacing(10)
        main_layout.addWidget(self.info_group, 40)
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

    def reject(self):
        if self.radlist:
            self.radlist.close()
        super().reject()

    def keyPressEvent(self, event):
        if event.key() != Qt.Key_Escape or self._parent:
            super().keyPressEvent(event)

    def kbd_copy(self):
        self.clipboard.setText(self.info_pane.textCursor().selectedText())

    def kbd_paste(self):
        if self.rad_search_check.isChecked():
            self.rad_search_box.lineEdit().setText(self.clipboard.text())
            self.rad_search_box.setFocus()
            self.update_search()

    def show_error(self, msg=''):
        msg = '<span style="color:red;">%s</span>\n' % msg
        self.info_pane.setHtml(self.info_pane.toHtml() + msg)

    def show_radlist(self):
        if not self.radlist:
            x, y, w, h = self.geometry().getRect()
            fw = self.frameGeometry().width()
            geo = QRect(x + fw, y, min(w, 600), max(h, 600))
            self.radlist = kdRadicalList(toggle_action=self.on_radical_toggled, geo=geo)
            self.on_search_edit()
            self.update_search()
        self.radlist.show()
        self.radlist.activateWindow()

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
        self.update_search()

    def text_search_toggle(self):
        en = self.text_search_check.isChecked()
        self.text_search_box.setEnabled(en)
        self.text_search_clearbtn.setEnabled(en)
        self.update_search()

    def on_search_clear(self):
        self.rad_search_box.lineEdit().setText('')
        if self.radlist:
            self.radlist.set_avail(None)

    def on_search_edit(self):
        if self.radlist:
            rads = self.rad_search_box.lineEdit().text()
            self.radlist.update(rads)

    def on_radical_toggled(self, btn):
        rads = self.rad_search_box.lineEdit().text()
        r = btn.text()[0]
        if btn.isChecked() and not r in rads:
            rads += r
        else:
            rads = rads.replace(r, '')
        self.rad_search_box.lineEdit().setText(rads)
        self.update_search()

    def on_kanji_btn_clicked(self, btn):
        self.show_info(btn.text())

    def update_search(self):
        sets = []
        # add kanji set based on stroke count
        if self.stroke_search_check.isChecked():
            strokes = self.stroke_search_num.value()
            tolerance = self.stroke_search_tol.value()
            sets.append(set(_s2kanji(strokes - tolerance, strokes + tolerance)))
        # add kanji set for each radical
        rads = ''
        if self.rad_search_check.isChecked():
            rads = self.rad_search_box.lineEdit().text().strip()
            if len(rads):
                # save to history
                self.rad_search_box.lineEdit().setText(rads)
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
            text = self.text_search_box.lineEdit().text().strip()
            if len(text):
                # save to history
                for i in range(self.text_search_box.count()):
                    if self.text_search_box.itemText(i) == text:
                        self.text_search_box.removeItem(i)
                        break
                text = text.lower()
                self.text_search_box.insertItem(0, text)
                self.text_search_box.setCurrentIndex(0)
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
        if len(res) == 1:
            self.show_info(list(res)[0])
        # update list of possible radicals
        if self.radlist:
            self.radlist.set_avail(set(av_rads) if rads or av_rads else None)

    def show_info(self, kanji=''):
        if not self.dic_ok:
            return
        if kanji:
            # insert into history
            btn = zKanjiButton(kanji)
            btn.click_action = self.on_kanji_btn_clicked
            self.info_hist.insert_top_uniq(btn)
            self.info_hist.verticalScrollBar().setValue(0)
            # limit history length
            while self.info_hist.widget().layout().takeAt(10):
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
