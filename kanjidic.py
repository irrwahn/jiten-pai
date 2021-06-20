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
    krad_name = _KANJIDIC_KRAD
    if not os.access(krad_name, os.R_OK):
        krad_name = _get_dfile_path(os.path.join(_KANJIDIC_DIR, _KANJIDIC_KRAD), mode=os.R_OK)
    try:
        with open(krad_name) as krad_file:
            re_krad = re.compile(r'^([^#\s]) : (.+)$')
            for line in krad_file:
                m = re_krad.search(line)
                if m:
                    _krad[m.group(1)] = m.group(2)
    except Exception as e:
        eprint('_rad_load:', krad_name, str(e))

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


############################################################
# main window class

class kdMainWindow(QDialog):
    kanji_click = pyqtSignal(str)

    def __init__(self, *args, title=_KANJIDIC_NAME + ' ' + _KANJIDIC_VERSION, **kwargs):
        super().__init__(*args, **kwargs)
        self.setModal(False)
        self.setParent(None, self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.init_cfg()
        # load radkfile & kradfile
        _rad_load()
        self.init_ui(title)

    def init_cfg(self):
        _load_cfg()

    def init_ui(self, title=''):
        #jpIcon()
        self.setWindowTitle(title)
        #self.setWindowIcon(jpIcon.jitenpai)
        self.resize(800, 600)
        self.clipboard = QApplication.clipboard()
        # search options
        self.opt_group = zQGroupBox('Kanji Search Options:')
        opt_layout = QGridLayout()
        self.opt_group.setLayout(opt_layout)
        # search results
        self.result_group = zQGroupBox('Search Results:')
        self.result_pane = QWidget()
        result_layout = QGridLayout()
        result_layout.addWidget(self.result_pane)
        self.result_group.setLayout(result_layout)
        # info area
        self.info_group = zQGroupBox('Kanji Info:')
        self.info_pane = zQTextEdit()
        self.info_pane.kanji_click.connect(self.kanji_click)
        self.info_pane.setReadOnly(True)
        self.info_pane.setText('')
        info_layout = zQVBoxLayout()
        info_layout.addWidget(self.info_pane)
        self.info_group.setLayout(info_layout)
        # set up main window layout
        main_layout = zQVBoxLayout(self)
        #main_layout.addWidget(menubar)
        main_layout.addWidget(self.opt_group, 1)
        main_layout.addWidget(self.result_group, 1)
        main_layout.addWidget(self.info_group, 1000)
        QShortcut('Ctrl+Q', self).activated.connect(lambda: self.closeEvent(None))
        QShortcut('Ctrl+W', self).activated.connect(lambda: self.closeEvent(None))

    def show_info(self, kanji=''):
        info = ['']
        r = kanji_lookup(cfg['kanjidic'], kanji[0] if kanji else '')
        nfmt = '<div style="font-family:%s;font-size:%.1fpt">' % (cfg['nfont'], cfg['nfont_sz'])
        lfmt = '<span style="font-family:%s;font-size:%.1fpt;">' % (cfg['lfont'], cfg['lfont_sz'])
        hlfmt = '<span style="color:%s;">' % cfg['hl_col']
        info.append(nfmt)
        for k, v in r.items():
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


# Kanjidic lookup
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

def kanji_lookup(dict_fname, kanji):
    res = {
        'kanji': '',
        'radicals': '',
        'strokes': '',
        'readings': '',
        'r_korean': '',
        'r_pinyin': '',
        'meaning': '',
        'freq': '',
        'grade': '',
    }
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
                if line[0] != kanji:
                    continue
                # save kanji
                res['kanji'] = line[0]
                line = line[2:]
                # skip JIS
                line = line[4:]
                # save meaning
                m = re_braces.search(line).group(0)
                res['meaning'] = m.replace('{', '').replace('}', ';').strip()
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
                            res[k[1]] = t[len(k[0]):]
                            break
                # get readings (i.e. all that's left)
                res['readings'] = line.strip().replace(' ', ', ').replace('T2,', 'T2').replace('T1,', 'T1')
                break
        res['radicals'] = _k2rad(kanji)
    except Exception as e:
        print('klookup:', dict_fname, str(e))
    return res


############################################################
# main function

def _main():
    kanji = sys.argv[1] if len(sys.argv) > 1 else ''
    os.environ['QT_LOGGING_RULES'] = 'qt5ct.debug=false'
    app = QApplication(sys.argv)
    app.setApplicationName(_KANJIDIC_NAME)
    root = kdMainWindow()
    root.show_info(kanji)
    root.show()
    sys.exit(app.exec_())

if __name__== "__main__":
    _main()
