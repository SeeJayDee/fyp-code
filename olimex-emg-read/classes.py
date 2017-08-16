"""A library for the various object classes used in olimex-emg-read.py.

blah.
"""

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
from scipy import signal
from collections import deque
import pyqtgraph as pg
from threading import Thread
import time

app = QtGui.QApplication([])


class DisplayWindow(object):
    """A generic wrapper for our QtGui window.

    Will contain all the functions for the plotting and data output.
    """
    def __init__(self, cfg):
        """Constructor."""
        self.mainwin = QtGui.QMainWindow()
        self.mainwin.setWindowTitle(cfg['title'])
        self.mainwin.resize(cfg['width'], cfg['height'])
        self.central_widget = QtGui.QWidget()
        self.mainwin.setCentralWidget(self.central_widget)
        self.top_layout = QtGui.QHBoxLayout()
        self.side_layouts = {'left' : QtGui.QVBoxLayout(),
                             'right': QtGui.QVBoxLayout()}
        self.top_layout.addLayout(self.side_layouts['left'])
        self.top_layout.addLayout(self.side_layouts['right'])
        self.central_widget.setLayout(self.top_layout)

        self.plot_timer = QtCore.QTimer()
        plot_names = ['L_AS', 'L_AP', 'R_AS', 'R_AP']
        self.plot_names = plot_names
        plot_colours = {'L_AS' : (255, 111, 055),
                        'L_AP' : (255, 99, 111),
                        'R_AS' : (055, 111, 255),
                        'R_AP' : (111, 99, 255)}

        self.plotwidgets = {}
        self.plots = {}
        self.datalen = 3 * cfg['sampfreq']
        self.data = {}

        for plt in plot_names:
            self.plotwidgets[plt] = pg.PlotWidget(name=plt)
            self.plots[plt] = self.plotwidgets[plt].plot()
            self.plots[plt].setPen(plot_colours[plt])
            if plt.startswith('L'):
                self.side_layouts['left'].addWidget(self.plotwidgets[plt])
            elif plt.startswith('R'):
                self.side_layouts['right'].addWidget(self.plotwidgets[plt])
            self.data[plt] = deque([0.0]*self.datalen, self.datalen)

        for i in xrange(0, self.datalen):
            for plt in plot_names:
                self.data[plt].appendleft(np.sin(i/10.))
                if i == self.datalen - 1:
                    self.plots[plt].setData(self.data[plt])

        self.mainwin.show()
