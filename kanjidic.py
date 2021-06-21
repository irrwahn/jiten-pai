#!/usr/bin/env python3

import io
import sys
import os
import re
import json
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


_KANJIDIC_VERSION = '0.0.9'
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
    'kanjidic': '/usr/share/gjiten/dics/kanjidic',
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
                        if t[:len(k[0])] == k[0]:
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

def _s2kanji(strokes, tolerance=0):
    min_strok = strokes - tolerance
    max_strok = strokes + tolerance
    res = ''
    for k, v in _kanjidic.items():
        try:
            s = int(v['strokes'])
        except:
            continue
        if min_strok <= s <= max_strok:
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
class zFlowLayout(QLayout):
    def __init__(self, parent: QWidget=None, margin: int=-1, hSpacing: int=-1, vSpacing: int=-1):
        super().__init__(parent)
        self.itemList = list()
        self.m_hSpace = hSpacing
        self.m_vSpace = vSpacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self.itemList.append(item)

    def rotate_right(self, n):
        l = len(self.itemList)
        if l > n:
            self.itemList = self.itemList[-n:] + self.itemList[:-n]

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

    def horizontalSpacing(self):
        if self.m_hSpace >= 0:
            return self.m_hSpace
        else:
            return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self.m_vSpace >= 0:
            return self.m_vSpace
        else:
            return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def smartSpacing(self, pm):
        parent = self.parent()
        if not parent:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, testOnly):
        left, top, right, bottom = self.getContentsMargins()
        effectiveRect = rect.adjusted(+left, +top, -right, -bottom)
        x = effectiveRect.x()
        y = effectiveRect.y()
        lineHeight = 0
        for item in self.itemList:
            wid = item.widget()
            spaceX = self.horizontalSpacing()
            if spaceX == -1:
                spaceX = wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = self.verticalSpacing()
            if spaceY == -1:
                spaceY = wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > effectiveRect.right() and lineHeight > 0:
                x = effectiveRect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y() + bottom

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
        layout = zFlowLayout(self.widget(), 0, 0, 0)
        for tl in tiles:
            layout.addWidget(tl)
        self.setUpdatesEnabled(True)

    def insert(self, w):
        self.setUpdatesEnabled(False)
        if not self.widget():
            pane = QWidget()
            self.setWidget(pane)
            layout = zFlowLayout(self.widget(), 0, 0, 0)
        self.widget().layout().addWidget(w)
        self.widget().layout().rotate_right(1)
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

    def _click(self):
        if self.click_action:
            self.click_action(self)

    def sizeHint(self):
        return QSize(64, 64)

    def resizeEvent(self, event):
        sz = min(self.rect().height(), self.rect().width()) - 8
        font = self.font()
        font.setPixelSize(sz)
        self.setFont(font)

class zRadicalButton(zKanjiButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCheckable(True)
        self.setStyleSheet(None)
        self.setContentsMargins(QMargins(0,0,0,0))
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

    def __init__(self, *args, toggle_action=None, title=_KANJIDIC_NAME + ' ' + _KANJIDIC_VERSION, **kwargs):
        super().__init__(*args, **kwargs)
        self.toggle_action = toggle_action
        self._init_ui()

    def _init_ui(self):
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
            sep.setFlat(True)
            self._add_widget(sep)
            for rad in _srad[stroke]:
                self._add_widget(zRadicalButton(rad))
        self.resize(600, 600)
        QShortcut('Ctrl+Q', self).activated.connect(lambda: self.closeEvent(None))
        QShortcut('Ctrl+W', self).activated.connect(lambda: self.closeEvent(None))

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
                if not btn.isFlat():
                    btn.setEnabled(True)
        else:
            for btn in self.btns:
                if not btn.isChecked() and not btn.isFlat():
                    btn.setEnabled(btn.text() in avail)


############################################################
# main window class

class kdMainWindow(QDialog):
    kanji_click = pyqtSignal(str)
    dic_ok = True

    def __init__(self, *args, title=_KANJIDIC_NAME + ' ' + _KANJIDIC_VERSION, **kwargs):
        super().__init__(*args, **kwargs)
        self.setModal(False)
        self.setParent(None, self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.init_cfg()
        self.init_ui(title)
        QApplication.processEvents()
        # load radkfile, kradfile, kanjidic
        if not _rad_load():
            self.show_error('Error loading radkfile/kradfile!')
            self.dic_ok = False
        if not _kanjidic_load(cfg['kanjidic']):
            self.show_error('Error loading kanjidic!')
            self.dic_ok = False
        self.radlist = None
        # initialize search options
        self.stroke_search_check.toggled.connect(self.stroke_search_toggle)
        self.stroke_search_num.valueChanged.connect(self.update_search)
        self.stroke_search_tol.valueChanged.connect(self.update_search)
        self.stroke_search_check.setChecked(True)
        self.stroke_search_check.setChecked(False)
        self.rad_search_check.toggled.connect(self.rad_search_toggle)
        self.rad_search_check.setChecked(True)
        self.rad_search_check.setChecked(False)
        QShortcut('Ctrl+Q', self).activated.connect(lambda: self.closeEvent(None))
        QShortcut('Ctrl+W', self).activated.connect(lambda: self.closeEvent(None))

    def init_cfg(self):
        _load_cfg()

    def search_clear(self):
        self.rad_search_box.lineEdit().setText('')
        self.radlist.set_avail(None)

    def init_ui(self, title=''):
        #jpIcon()
        self.setWindowTitle(title)
        #self.setWindowIcon(jpIcon.jitenpai)
        self.resize(800, 600)
        self.clipboard = QApplication.clipboard()
        # search options
        self.opt_group = zQGroupBox('Kanji Search Options:')
        # stroke search
        stroke_search_layout = zQHBoxLayout()
        self.stroke_search_check = QCheckBox('Search By Strokes:')
        self.stroke_search_num = QSpinBox()
        self.stroke_search_num.setRange(1,42)
        self.stroke_search_tol_label = QLabel('+/-')
        self.stroke_search_tol_label.setAlignment(Qt.AlignRight)
        self.stroke_search_tol = QSpinBox()
        stroke_search_layout.addWidget(self.stroke_search_check, 1)
        stroke_search_layout.addWidget(self.stroke_search_num, 1)
        stroke_search_layout.addWidget(self.stroke_search_tol_label, 1)
        stroke_search_layout.addWidget(self.stroke_search_tol, 1)
        stroke_search_layout.addStretch(10)
        # radical search
        rad_search_layout = zQHBoxLayout()
        self.rad_search_check = QCheckBox('Search By Radical:')
        self.rad_search_box = QComboBox()
        self.rad_search_box.setCurrentIndex(-1)
        self.rad_search_box.setEditable(True)
        self.rad_search_box.lineEdit().textChanged.connect(self.on_search_edit)
        self.rad_search_box.lineEdit().editingFinished.connect(self.update_search)
        self.rad_search_clearbtn = QPushButton('Clear')
        self.rad_search_clearbtn.clicked.connect(self.search_clear)
        self.rad_search_listbtn = QPushButton('Radical List')
        self.rad_search_listbtn.clicked.connect(self.show_radlist)
        rad_search_layout.addWidget(self.rad_search_check, 1)
        rad_search_layout.addWidget(self.rad_search_box, 20)
        rad_search_layout.addWidget(self.rad_search_clearbtn, 2)
        rad_search_layout.addWidget(self.rad_search_listbtn, 2)
        opt_layout = zQVBoxLayout()
        opt_layout.addLayout(stroke_search_layout)
        opt_layout.addLayout(rad_search_layout)
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
        self.info_pane = zQTextEdit()
        self.info_pane.kanji_click.connect(self.kanji_click)
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

    def show_error(self, msg=''):
        msg = '<span style="color:red;">%s</span>\n' % msg
        self.info_pane.setHtml(self.info_pane.toHtml() + msg)

    def show_radlist(self):
        if not self.radlist:
            self.radlist = kdRadicalList(toggle_action=self.on_radical_toggled)
        self.radlist.show()
        self.radlist.activateWindow()

    def closeEvent(self, event=None):
        if self.radlist:
            self.radlist.destroy()
        super().closeEvent(event)
        die()

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

    def on_result_clicked(self, btn):
        self.show_info(btn.text())
        btn = zKanjiButton(btn.text())
        btn.click_action = self.on_hist_clicked
        self.info_hist.insert(btn)

    def on_hist_clicked(self, btn):
        self.show_info(btn.text())

    def update_search(self):
        sets = []
        # add kanji set based on stroke count
        if self.stroke_search_check.isChecked():
            strokes = self.stroke_search_num.value()
            tolerance = self.stroke_search_tol.value()
            sets.append(set(_s2kanji(strokes, tolerance)))
        # add kanji set for each radical
        if self.rad_search_check.isChecked():
            for rad in self.rad_search_box.lineEdit().text():
                sets.append(set(_rad2k(rad)[1]))
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
        rads = ''
        tiles = []
        for r in res:
            btn = zKanjiButton(r)
            btn.click_action = self.on_result_clicked
            tiles.append(btn)
            if self.radlist:
                rads += _k2rad(r)
        self.result_area.fill(tiles)
        # update list of possible radicals
        if self.radlist:
            self.radlist.set_avail(set(rads) if rads else None)

    def show_info(self, kanji=''):
        if not self.dic_ok:
            return
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

def _main():
    kanji = sys.argv[1] if len(sys.argv) > 1 else ''
    os.environ['QT_LOGGING_RULES'] = 'qt5ct.debug=false'
    app = QApplication(sys.argv)
    app.setApplicationName(_KANJIDIC_NAME)
    root = kdMainWindow()
    root.show()
    root.show_info(kanji)
    sys.exit(app.exec_())

if __name__== "__main__":
    _main()
