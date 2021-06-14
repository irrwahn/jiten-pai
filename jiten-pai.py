#!/usr/bin/env python3

"""
jiten-pai.py

Copyright (c) 2021 Urban Wallasch <irrwahn35@freenet.de>

Jiten-pai is distributed under the Modified ("3-clause") BSD License.
See `LICENSE` file for more information.
"""


_JITENPAI_VERSION = '0.0.1'
_JITENPAI_NAME = 'Jiten-pai'
_JITENPAI_CFG = 'jiten-pai.conf'


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
from configparser import RawConfigParser as ConfigParser
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


############################################################
# utility functions

def die(rc=0):
    sys.exit(rc)

def contains_cjk(s):
    for c in s:
        if "Lo" == unicodedata.category(c):
            return True
    return False


############################################################
# configuration

cfg = {
    'dict': '/usr/share/gjiten/dics/edict',
    'max_res': 100,
    'font': 'sans',
    'font_sz': 12,
    'lfont': 'IPAPMincho',
    'lfont_sz': 24,
    'hl_col': 'blue',
}


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
        # TODO: preferences dialog
        #pref_action.triggered.connect()
        edit_menu.addAction(copy_action)
        edit_menu.addAction(paste_action)
        edit_menu.addAction(pref_action)
        tools_menu = menubar.addMenu('&Tools')
        # TODO: Tools menu
        help_menu = menubar.addMenu('&Help')
        about_action = QAction('&About', self)
        help_menu.addAction(about_action)
        # options
        japopt_group = QGroupBox('Japanese Search Options')
        self.japopt_exact = QRadioButton('Exact Matches')
        self.japopt_exact.setChecked(True)
        self.japopt_start = QRadioButton('Start With Expression')
        self.japopt_end = QRadioButton('End With Expression')
        self.japopt_any = QRadioButton('Any Matches')
        japopt_layout = QVBoxLayout()
        japopt_layout.addWidget(self.japopt_exact)
        japopt_layout.addWidget(self.japopt_start)
        japopt_layout.addWidget(self.japopt_end)
        japopt_layout.addWidget(self.japopt_any)
        japopt_layout.addStretch()
        japopt_group.setLayout(japopt_layout)
        engopt_group = QGroupBox('English Search Options')
        self.engopt_expr = QRadioButton('Whole Expressions')
        self.engopt_word = QRadioButton('Whole Words')
        self.engopt_any = QRadioButton('Any Matches')
        self.engopt_any.setChecked(True)
        engopt_layout = QVBoxLayout()
        engopt_layout.addWidget(self.engopt_expr)
        engopt_layout.addWidget(self.engopt_word)
        engopt_layout.addWidget(self.engopt_any)
        engopt_layout.addStretch()
        engopt_group.setLayout(engopt_layout)
        genopt_group = QGroupBox('General Options')
        # TODO: add remaining general options
        self.genopt_dolimit = QCheckBox('Limit Results:')
        self.genopt_dolimit.setTristate(False)
        self.genopt_dolimit.setChecked(True)
        self.genopt_limit = QSpinBox()
        self.genopt_limit.setMinimum(1)
        self.genopt_limit.setMaximum(1000)
        self.genopt_limit.setValue(cfg['max_res'])
        self.genopt_dolimit.toggled.connect(self.genopt_limit.setEnabled)
        genopt_limit_layout = QHBoxLayout()
        genopt_limit_layout.addWidget(self.genopt_dolimit)
        genopt_limit_layout.addWidget(self.genopt_limit)
        genopt_layout = QVBoxLayout()
        genopt_layout.addLayout(genopt_limit_layout)
        genopt_layout.addStretch()
        genopt_group.setLayout(genopt_layout)
        opt_layout = QHBoxLayout()
        opt_layout.addWidget(japopt_group)
        opt_layout.addWidget(engopt_group)
        opt_layout.addWidget(genopt_group)
        # search area
        search_group = QGroupBox('Enter expression')
        self.search_box = QComboBox()
        self.search_box.setEditable(True)
        self.search_box.setMinimumWidth(400);
        self.search_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        QShortcut('Return', self.search_box).activated.connect(self.search)
        search_button = QPushButton('Search')
        search_button.setDefault(True)
        search_button.clicked.connect(self.search)
        clear_button = QPushButton('Clear')
        clear_button.clicked.connect(lambda: self.search_box.lineEdit().setText(""))
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_box, 100)
        search_layout.addWidget(search_button, 5)
        search_layout.addWidget(clear_button, 1)
        search_group.setLayout(search_layout)
        # result area
        result_group = QGroupBox('Search results')
        self.matches_label = QLabel(' ')
        self.result_pane = QTextEdit()
        self.result_pane.setReadOnly(True)
        self.result_pane.setText('')
        result_layout = QVBoxLayout()
        result_layout.addWidget(self.result_pane)
        result_layout.addWidget(self.matches_label)
        result_group.setLayout(result_layout)
        # set up main window layout
        main_frame = QWidget()
        main_layout = QVBoxLayout(main_frame)
        main_layout.addWidget(menubar)
        main_layout.addLayout(opt_layout, 1)
        main_layout.addWidget(search_group, 20)
        main_layout.addWidget(result_group, 100)
        self.setCentralWidget(main_frame)
        self.search_box.setFocus()

    def search(self):
        term = self.search_box.lineEdit().text().strip()
        self.search_box.lineEdit().setText(term)
        if len(term) < 1:
            return
        # apply search options
        if contains_cjk(term):
            print('apply japopt')
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
            print('apply engopt')
            if self.engopt_expr.isChecked():
                term = '\W ' + term
                if term[-1] != ';':
                    term = term + ';'
            if self.engopt_word.isChecked():
                term = '\W' + term + '\W'
            if self.engopt_any.isChecked():
                if term[-1] == ';':
                    term = term[:-1]
        # result limiting
        max_res = self.genopt_limit.value() if self.genopt_limit.isEnabled() else 0
        # perform lookup
        result = dict_lookup(cfg['dict'], term, max_res)
        if len(result) < 1:
            self.matches_label.setText("No match found!")
            self.result_pane.setHtml('')
            return
        # format result
        re_term = re.compile(self.search_box.lineEdit().text(), re.IGNORECASE)
        nfmt = '<div style="font-family: %s; font-size: %dpt">' % (cfg['font'], cfg['font_sz'])
        lfmt = '<span style="font-family: %s; font-size: %dpt;">' % (cfg['lfont'], cfg['lfont_sz'])
        hl = '<span style="color: %s;">' % cfg['hl_col']
        html = [nfmt]
        for res in result:
            # highlight matches
            for i in range(len(res)):
                match = re_term.search(res[i])
                if match:
                    res[i] = res[i][:match.start()] + hl \
                           + res[i][match.start():match.end()] \
                           + '</span>' + res[i][match.end():]
            # construct display line
            html.append('%s%s</span>' % (lfmt, res[0]))
            if len(res[1]) > 0:
                html.append(' (%s)' % res[1])
            html.append(' %s<br>' % res[2])
        html.append('</div>')
        self.result_pane.setHtml(''.join(html))
        self.matches_label.setText("Matches found: %d" % len(result))

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

def dict_lookup(dict_fname, term, max_res = 0):
    result = []
    cnt = 0;
    with open(dict_fname) as dict_file:
        re_term = re.compile(term, re.IGNORECASE)
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
                kanji = p1[0].strip()
                kana = p2[0].strip()
                trans = ' ' + p2[1].lstrip('/ ').rstrip(' \t\r\n').replace('/', '; ')
            except:
                print("ouch!")
                continue
            # for now promiscuously try to match anything anywhere
            if re_term.search(kanji) is not None \
            or re_term.search(kana) is not None \
            or re_term.search(trans) is not None:
                result.append([kanji, kana, trans])
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
