#!/usr/bin/env python3

"""
jiten-pai.py

Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>

Contributors:
    volpol

Jiten-pai is distributed under the Modified ("3-clause") BSD License.
See `LICENSE` file for more information.
"""


_JITENPAI_VERSION = '0.0.3'
_JITENPAI_NAME = 'Jiten-pai'
_JITENPAI_CFG = 'jiten-pai.conf'

_JITENPAI_HELP = 'todo'

import sys

_PYTHON_VERSION = float("%d.%d" % (sys.version_info.major, sys.version_info.minor))
if _PYTHON_VERSION < 3.6:
    raise Exception ('Need Python version 3.6 or later, got version ' + str(sys.version))

import platform
import io
import os
import re
import argparse
import unicodedata
import enum
from configparser import RawConfigParser as ConfigParser
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


############################################################
# utility functions and classes

def die(rc=0):
    sys.exit(rc)

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
    'max_res': 100,
    'nfont': 'sans',
    'nfont_sz': 12,
    'lfont': 'IPAPMincho',
    'lfont_sz': 24,
    'hl_col': 'blue',
}


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


# widgets / layouts with custom styles
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
        #self.ok_button.setIcon(jpIcon.ok)
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
# 'Preferences' dialog

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
        fonts_group.setLayout(fonts_layout)
        # buttons
        self.cancel_button = QPushButton('Cancel')
        #self.cancel_button.setIcon(jpIcon.close)
        self.cancel_button.setToolTip('Close dialog without applying changes')
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button = QPushButton('Apply')
        #self.apply_button.setIcon(jpIcon.apply)
        self.apply_button.setToolTip('Apply current changes')
        self.apply_button.clicked.connect(self.apply)
        self.ok_button = QPushButton('Ok')
        #self.ok_button.setIcon(jpIcon.ok)
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
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        self.update_font_sample()

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
        font = QFont()
        font.fromString(self.nfont_edit.text())
        f = font.toString().split(',')
        cfg['nfont'] = f[0]
        cfg['nfont_sz'] = int(f[1])
        font.fromString(self.lfont_edit.text())
        f = font.toString().split(',')
        cfg['lfont'] = f[0]
        cfg['lfont_sz'] = int(f[1])
        cfg['hl_col'] = self.color_edit.text()
        self.update_font_sample()

    def accept(self):
        self.apply()
        super().accept()


############################################################
# main window class

class jpMainWindow(QMainWindow):
    def __init__(self, *args, title='', **kwargs):
        super().__init__(*args, **kwargs)
        self.init_ui(title)

    def init_ui(self, title=''):
        #jpIcon()
        self.setWindowTitle(title)
        #self.setWindowIcon(jpIcon.jitenpai)
        self.resize(800, 600)
        self.clipboard = QApplication.clipboard()
        # menu
        menubar = QMenuBar(self)
        file_menu = menubar.addMenu('&File')
        quit_action = QAction('&Quit', self)
        quit_action.setShortcut('Ctrl+Q')
        quit_action.triggered.connect(die)
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
        edit_menu.addAction(pref_action)
        tools_menu = menubar.addMenu('&Tools')
        # TODO: Tools menu
        help_menu = menubar.addMenu('&Help')
        about_action = QAction('&About', self)
        help_menu.addAction(about_action)
        about_action.triggered.connect(self.about_dlg)
        # search options
        japopt_group = zQGroupBox('Japanese Search Options')
        self.japopt_exact = QRadioButton('Exact Matches')
        self.japopt_exact.setChecked(True)
        self.japopt_start = QRadioButton('Start With Expression')
        self.japopt_end = QRadioButton('End With Expression')
        self.japopt_any = QRadioButton('Any Matches')
        japopt_layout = zQVBoxLayout()
        japopt_layout.addWidget(self.japopt_exact)
        japopt_layout.addWidget(self.japopt_start)
        japopt_layout.addWidget(self.japopt_end)
        japopt_layout.addWidget(self.japopt_any)
        japopt_layout.addStretch()
        japopt_group.setLayout(japopt_layout)
        self.engopt_group = zQGroupBox('English Search Options')
        self.engopt_expr = QRadioButton('Whole Expressions')
        self.engopt_word = QRadioButton('Whole Words')
        self.engopt_any = QRadioButton('Any Matches')
        self.engopt_any.setChecked(True)
        engopt_layout = zQVBoxLayout()
        engopt_layout.addWidget(self.engopt_expr)
        engopt_layout.addWidget(self.engopt_word)
        engopt_layout.addWidget(self.engopt_any)
        engopt_layout.addStretch()
        self.engopt_group.setLayout(engopt_layout)
        genopt_group = zQGroupBox('General Options')
        genopt_dict_layout = zQHBoxLayout()
        self.genopt_dictsel = QComboBox()
        for d in cfg['dicts']:
            self.genopt_dictsel.addItem(d[0], d[1])
        self.genopt_dict = QRadioButton('Search Dict: ')
        self.genopt_dict.toggled.connect(self.genopt_dictsel.setEnabled)
        self.genopt_dict.setChecked(True)
        genopt_dict_layout.addWidget(self.genopt_dict)
        genopt_dict_layout.addWidget(self.genopt_dictsel)
        self.genopt_alldict = QRadioButton('Search All Dictionaries')
        # TODO: add "auto adjust options"
        self.genopt_dolimit = QCheckBox('Limit Results: ')
        self.genopt_dolimit.setTristate(False)
        self.genopt_dolimit.setChecked(True)
        self.genopt_limit = QSpinBox()
        self.genopt_limit.setMinimum(1)
        self.genopt_limit.setMaximum(1000)
        self.genopt_limit.setValue(cfg['max_res'])
        self.genopt_dolimit.toggled.connect(self.genopt_limit.setEnabled)
        genopt_limit_layout = zQHBoxLayout()
        genopt_limit_layout.addWidget(self.genopt_dolimit)
        genopt_limit_layout.addWidget(self.genopt_limit)
        genopt_layout = zQVBoxLayout()
        genopt_layout.addLayout(genopt_dict_layout)
        genopt_layout.addWidget(self.genopt_alldict)
        genopt_layout.addLayout(genopt_limit_layout)
        genopt_layout.addStretch()
        genopt_group.setLayout(genopt_layout)
        opt_layout = zQHBoxLayout()
        opt_layout.addWidget(japopt_group)
        opt_layout.addWidget(self.engopt_group)
        opt_layout.addWidget(genopt_group)
        opt_layout.addStretch()
        # search area
        search_group = zQGroupBox('Enter expression')
        self.search_box = QComboBox()
        self.search_box.setEditable(True)
        self.search_box.setMinimumWidth(400)
        self.search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        QShortcut('Return', self.search_box).activated.connect(self.search)
        search_button = QPushButton('Search')
        search_button.setDefault(True)
        search_button.clicked.connect(self.search)
        clear_button = QPushButton('Clear')
        clear_button.clicked.connect(lambda: self.search_box.lineEdit().setText(""))
        self.search_romaji = QCheckBox('Romaji')
        self.search_romaji.toggled.connect(self.engopt_group.setDisabled)
        search_layout = zQHBoxLayout()
        search_layout.addWidget(self.search_box, 100)
        search_layout.addWidget(search_button, 5)
        search_layout.addWidget(clear_button, 1)
        search_layout.addWidget(self.search_romaji)
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

    def pref_dlg(self):
        dlg = prefDialog(self)
        res = dlg.exec_()
        if res == QDialog.Accepted:
            self.search()

    def about_dlg(self):
        dlg = aboutDialog(self)
        dlg.exec_()

    def search(self):
        term = self.search_box.lineEdit().text().strip()
        self.search_box.lineEdit().setText(term)
        if len(term) < 1:
            return
        self.result_pane.setEnabled(False)
        # apply search options
        if self.search_romaji.isChecked():
            term = alphabet2kana(term)
            self.search_box.lineEdit().setText(term)
        mode = ScanMode.JAP if contains_cjk(term) else ScanMode.ENG
        if mode == ScanMode.JAP:
            term = kata2hira(term)
            if self.japopt_exact.isChecked():
                if term[0] != '^':
                    term = '^' + term
                if term[-1] != '$':
                    term = term + '$'
            elif self.japopt_start.isChecked():
                if term[0] != '^':
                    term = '^' + term
                if term[-1] == '$':
                    term = term[:-1]
            elif self.japopt_end.isChecked():
                if term[0] == '^':
                    term = term[1:]
                if term[-1] != '$':
                    term = term + '$'
            elif self.japopt_any.isChecked():
                if term[0] == '^':
                    term = term[1:]
                if term[-1] == '$':
                    term = term[:-1]
        else:
            if self.engopt_expr.isChecked():
                term = '\W( to)? ' + term + '(\s+\(.*\))?;'
            elif self.engopt_word.isChecked():
                term = '\W' + term + '\W'
        # result limiting
        max_res = self.genopt_limit.value() if self.genopt_limit.isEnabled() else 0
        # perform lookup
        QApplication.processEvents()
        result = []
        if self.genopt_dict.isChecked():
            dic = self.genopt_dictsel.itemData(self.genopt_dictsel.currentIndex())
            result = dict_lookup(dic, term, mode, max_res)
        else:
            for d in cfg['dicts']:
                r = dict_lookup(d[1], term, mode, max_res)
                result.extend(r)
                max_res -= len(r)
                if max_res == 0:
                    max_res = -1
        # format result
        term = self.search_box.lineEdit().text()
        re_term = re.compile(kata2hira(term), re.IGNORECASE)
        nfmt = '<div style="font-family: %s; font-size: %dpt">' % (cfg['nfont'], cfg['nfont_sz'])
        lfmt = '<span style="font-family: %s; font-size: %dpt;">' % (cfg['lfont'], cfg['lfont_sz'])
        hlfmt = '<span style="color: %s;">' % cfg['hl_col']
        html = [nfmt]
        def hl_repl(match, org=None):
            grp = match.group(0) if org is None else org[match.span()[0]:match.span()[1]]
            return '%s%s</span>' % (hlfmt, grp)
        for res in result:
            # highlight matches
            if mode == ScanMode.JAP:
                res[0] = re_term.sub(lambda m: hl_repl(m, res[0]), kata2hira(res[0]))
                res[1] = re_term.sub(hl_repl, res[1])
            else:
                res[2] = re_term.sub(hl_repl, res[2])
            # construct display line
            html.append('%s%s</span>' % (lfmt, res[0]))
            if len(res[1]) > 0:
                html.append(' (%s)' % res[1])
            html.append(' %s<br>\n' % res[2])
        html.append('</div>')
        self.result_pane.setHtml(''.join(html))
        self.result_group.setTitle('Search results: %d' % len(result))
        self.result_pane.setEnabled(True)

    def kbd_copy(self):
        self.clipboard.setText(self.result_pane.textCursor().selectedText())

    def kbd_paste(self):
        self.search_box.lineEdit().setText(self.clipboard.text())
        self.search_box.setFocus()


############################################################
# dictionary lookup
#
# edict example lines:
# 〆日 [しめび] /(n) time limit/closing day/settlement day (payment)/deadline/
# ハート /(n) heart/(P)/

def dict_lookup(dict_fname, pattern, mode, max_res=0):
    result = []
    cnt = 0
    with open(dict_fname) as dict_file:
        re_pattern = re.compile(pattern, re.IGNORECASE)
        for line in dict_file:
            if max_res and cnt >= max_res:
                break
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
                continue
            if (mode == ScanMode.JAP and (re_pattern.search(kata2hira(term)) or re_pattern.search(hira))) \
            or (mode == ScanMode.ENG and re_pattern.search(trans)):
                result.append([term, hira, trans])
                cnt += 1
    return result


############################################################
# main function

def main():
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
