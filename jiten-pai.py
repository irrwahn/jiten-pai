#!/usr/bin/env python3

"""
jiten-pai

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
from configparser import RawConfigParser as ConfigParser
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *


############################################################
# utility functions

def die(rc=0):
    sys.exit(rc)


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
        copy_action.triggered.connect(lambda: self.clipboard.setText(self.result_pane.textCursor().selectedText()))
        paste_action = QAction('&Paste', self)
        paste_action.setShortcut('Ctrl+V')
        paste_action.triggered.connect(lambda: self.search_box.lineEdit().setText(self.clipboard.text()))
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
        # search area
        search_group = QGroupBox('Enter expression:')
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
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(search_button)
        search_layout.addWidget(clear_button)
        search_group.setLayout(search_layout)
        # result area
        result_group = QGroupBox('Search results:')
        self.matches_label = QLabel('Matches found:')
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
        main_layout.addWidget(search_group)
        main_layout.addWidget(result_group)
        self.setCentralWidget(main_frame)

    def search(self):
        term = self.search_box.lineEdit().text()
        if len(term) < 1:
            return
        result = dict_lookup(cfg['dict'], term, cfg['max_res'])
        # result formatting
        re_term = re.compile(term)
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
            html.append('%s%s</span> (%s) %s<br>' % (lfmt, res[0], res[1], res[2]))
        html.append('</div>')
        self.result_pane.setHtml(''.join(html))
        self.matches_label.setText("Matches found: %d" % len(result))


############################################################
# dictionary lookup
#
# edict example line:
# 〆日 [しめび] /(n) time limit/closing day/settlement day (payment)/deadline/

def dict_lookup(dict_fname, term, max_res = 0):
    result = []
    cnt = 0;
    with open(dict_fname) as dict_file:
        re_term = re.compile(term)
        for line in dict_file:
            if max_res and cnt >= max_res:
                break
            try:
                # manually splitting the line is actually faster than regex
                p1 = line.split('[', 1)
                p2 = p1[1].split(']', 1)
                kanji = p1[0].strip()
                kana = p2[0].strip()
                trans = p2[1].strip('/ \t\r\n')
            except:
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
