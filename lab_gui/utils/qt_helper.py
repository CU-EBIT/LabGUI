from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QLabel, QCheckBox, QHBoxLayout, QVBoxLayout,\
        QHBoxLayout, QWidget, QFrame, QPushButton, QLineEdit, QFileDialog, QTableWidget,\
        QMainWindow, QMenu, QApplication, QLayout, QGridLayout
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtGui import QAction, QIcon

Key_Up = QtCore.Qt.Key.Key_Up
Key_Down = QtCore.Qt.Key.Key_Down
Key_Enter = QtCore.Qt.Key.Key_Enter

TableNoEdit = QtWidgets.QTableWidget.EditTrigger.NoEditTriggers

# Some QT5/QT6 float to int conversions for allowing calling with floats if tested in PySide6.
def __replace_size_func(Class, Name, two_args=True):
    __old__ = getattr(Class, Name)
    # Dumb way to add a move function for now
    def __new__(self, *args):
        args = [int(a) if isinstance(a, float) else a for a in args]
        __old__(self, *args)
    setattr(Class, Name, __new__)

__replace_size_func(QWidget, "move")
__replace_size_func(QWidget, "resize")
__replace_size_func(QWidget, "setFixedSize")
__replace_size_func(QWidget, "setFixedWidth")
__replace_size_func(QTableWidget, "setRowHeight")
__replace_size_func(QTableWidget, "setColumnWidth")
