from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QCheckBox, QHBoxLayout, QVBoxLayout,\
        QHBoxLayout, QWidget, QFrame, QPushButton, QLineEdit, QFileDialog, QTableWidget,\
        QMainWindow, QMenu, QApplication, QLayout, QGridLayout
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtGui import QAction, QIcon

Key_Up = QtCore.Qt.Key.Key_Up
Key_Down = QtCore.Qt.Key.Key_Down
Key_Enter = QtCore.Qt.Key.Key_Enter

TableNoEdit = QtWidgets.QTableWidget.EditTrigger.NoEditTriggers
# PySide6 has this named differently it seems
QtCore.pyqtSignal = QtCore.Signal

# from PyQt5.QtCore import Qt
# from PyQt5.QtWidgets import QComboBox, QLabel, QCheckBox, QHBoxLayout, QVBoxLayout,\
#         QHBoxLayout, QWidget, QFrame, QPushButton, QLineEdit, QFileDialog, QTableWidget,\
#         QMainWindow, QMenu, QAction, QApplication, QLayout, QGridLayout
# from PyQt5 import QtCore, QtWidgets, QtGui
# from PyQt5.QtGui import QIcon

# Key_Up = QtCore.Qt.Key_Up
# Key_Down = QtCore.Qt.Key_Down
# Key_Enter = QtCore.Qt.Key_Enter

# TableNoEdit = QtWidgets.QTableWidget.NoEditTriggers