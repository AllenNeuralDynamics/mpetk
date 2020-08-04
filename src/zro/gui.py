"""
gui.py
"""
import traceback

from PyQt4 import QtGui, QtCore
from .proxy import Proxy


class ProxyWidget(QtGui.QWidget):
    """
    A widget created from a DeviceProxy.  Populates attribute and command tabs
        by asking the proxy what is available.
    """
    def __init__(self, proxy, *args, **kwargs):

        self.attribute_list = kwargs.get("attribute_list", None)
        self.command_list = kwargs.get("command_list", None)

        super(ProxyWidget, self).__init__()
        self._proxy = proxy

        self.init_ui()

        self.populate()

    @property
    def proxy(self):
        return self._proxy

    def init_ui(self):
        self.main_layout = QtGui.QGridLayout(self)
        self.tabwidget = QtGui.QTabWidget()
        self.main_layout.addWidget(self.tabwidget)

        self.attr_widget = QtGui.QWidget()
        self.command_widget = QtGui.QWidget()
        self.attr_layout = QtGui.QGridLayout(self.attr_widget)
        self.command_layout = QtGui.QGridLayout(self.command_widget)

        self.command_scroll_area = QtGui.QScrollArea()
        self.command_scroll_area.setWidgetResizable(True)
        self.attr_scroll_area = QtGui.QScrollArea()
        self.attr_scroll_area.setWidgetResizable(True)
        
        self.command_scroll_area.setWidget(self.command_widget)
        self.attr_scroll_area.setWidget(self.attr_widget)
        #self.main_layout.addWidget(self.scroll_area)

        self.tabwidget.addTab(self.command_scroll_area, "commands")
        self.tabwidget.addTab(self.attr_scroll_area, "attributes")

    def populate(self):
        """
        populates the tabs with attributes and commands.  If a custom attribute 
            or command list is passed in, it will use it.  Otherwise gets the
            list from the object.
        """

        if not self.command_list:
            command_list = self.proxy.get_command_list()
            commands_to_ignore = [
                "close",
                "get_command_list",
                "get_attribute_list",
                "get_uptime",
                "register_async_callback",
                "unregister_async_callback",
                #"get_async_result",
                #"async_result_waiting",
                #"call_async",
                "set_publish_ip",
                "set_reply_ip",
                "flush",
            ]

            self.command_list = command_list = [x for x in command_list if x 
                                                not in commands_to_ignore]
        else:
            command_list = self.command_list

        if not self.attribute_list:
            self.attribute_list = attribute_list = self.proxy.get_attribute_list()
        else:
            attribute_list = self.attribute_list

        self.commands = {}
        self.attributes = {}
        if self.proxy:
            for i, command in enumerate(command_list):
                cw = Command(command, self.proxy, parent=self.command_scroll_area)
                self.commands[command] = cw
                self.command_layout.addWidget(cw, i, 0)

            for i, attribute in enumerate(attribute_list):
                aw = Attribute(attribute, self.proxy, parent=self.attr_scroll_area)
                self.attributes[attribute] = aw
                self.attr_layout.addWidget(aw, i, 0)


class Command(QtGui.QWidget):
    """A widget for controlling a single command."""
    def __init__(self, command_name, proxy, parent=None):
        super(Command, self).__init__(parent=parent)
        self.command_name = command_name
        self.proxy = proxy

        self.init_ui()
        self.init_slots()

        self._feedback_timer = QtCore.QTimer()
        self._feedback_timer.timeout.connect(self._response_feedback)

    def init_ui(self):
        self.layout = QtGui.QGridLayout(self)
        
        self.label = QtGui.QLabel(self.command_name)
        self.label.setFixedWidth(150)
        self.layout.addWidget(self.label, 0, 0)

        self.arg_edit = QtGui.QLineEdit()
        self.layout.addWidget(self.arg_edit, 0, 1)

        self.send_button = QtGui.QPushButton("-->")
        self.layout.addWidget(self.send_button, 0, 2)

        self.return_edit = QtGui.QLineEdit()
        self.layout.addWidget(self.return_edit, 0, 3)

    def init_slots(self):
        self.send_button.clicked.connect(self._send)

    def _send(self):
        args = str(self.arg_edit.text())
        if args:
            command_str = "self.proxy.{}({})".format(self.command_name, args)
        else:
            command_str = "self.proxy.{}()".format(self.command_name)
        try:
            ret = eval(command_str)
            #raise ret
        except Exception as e:
            self.arg_edit.setStyleSheet("background-color: red")
            self.return_edit.setStyleSheet("background-color: red")
            exc = traceback.format_exc()
            QtGui.QMessageBox.warning(self, "Call to '{}' failed!".format(
                self.command_name), exc)
            self._feedback_timer.start(200)
        else:
            self.return_edit.setText(str(ret))
            self.arg_edit.setStyleSheet("background-color: green")
            self.return_edit.setStyleSheet("background-color: green")
            self._feedback_timer.start(200)

    def _response_feedback(self):
        self._feedback_timer.stop()
        self.arg_edit.setStyleSheet("")
        self.return_edit.setStyleSheet("")


class Attribute(QtGui.QWidget):
    """A widget for controlling a single attribute."""
    def __init__(self, attribute_name, proxy, parent=None):
        super(Attribute, self).__init__(parent=parent)
        self.attribute_name = attribute_name
        self.proxy = proxy

        self.init_ui()
        self.init_slots()

        self.current_value = None

        self._feedback_timer = QtCore.QTimer()
        self._feedback_timer.timeout.connect(self._response_feedback)

        try:
            self._get()
        except Exception as e:
            self.setEnabled(False)

        self._polling_rate_ms = 1000
        self._polling = False
        self._polling_timer = QtCore.QTimer()
        self._polling_timer.timeout.connect(self._get)

        self._response_feedback()  #clear colors

    @property
    def polling_rate_ms(self):
        return self._polling_rate_ms
    
    @polling_rate_ms.setter
    def polling_rate_ms(self, value):
        self._polling_rate_ms = 1000
        if self._polling:
            self._polling_timer.start(self._polling_rate_ms)

    def _toggle_poll(self):
        if self._polling:
            self._polling_timer.stop()
            self.poll_button.setStyleSheet("")
            self._polling = False
        else:
            self._polling_timer.start(self.polling_rate_ms)
            self.poll_button.setStyleSheet("background-color: green")
            self._polling = True

    def _response_feedback(self):
        self._feedback_timer.stop()
        self.val_edit.setStyleSheet("")

    def init_ui(self):
        self.layout = QtGui.QGridLayout(self)
        
        self.label = QtGui.QLabel(self.attribute_name)
        self.label.setFixedWidth(150)
        self.layout.addWidget(self.label, 0, 0)

        self.poll_button = QtGui.QPushButton("Poll")
        self.layout.addWidget(self.poll_button, 0, 1)

        self.set_button = QtGui.QPushButton("-->")
        self.layout.addWidget(self.set_button, 0, 2)

        self.val_edit = QtGui.QLineEdit()
        self.layout.addWidget(self.val_edit, 0, 3)

        self.get_button = QtGui.QPushButton("<--")
        self.layout.addWidget(self.get_button, 0, 4)

        self.type_label = QtGui.QLabel()
        self.type_label.setFixedWidth(100)
        self.layout.addWidget(self.type_label, 0, 5)


    def init_slots(self):
        self.set_button.clicked.connect(self._set)
        self.get_button.clicked.connect(self._get)
        self.poll_button.clicked.connect(self._toggle_poll)

    def _set(self):
        value = eval(str(self.val_edit.text()))
        try:
            setattr(self.proxy, self.attribute_name, value)
        except Exception as e:
            self.val_edit.setStyleSheet("background-color: red")
        else:
            self.val_edit.setStyleSheet("background-color: green")
        finally:
            self._feedback_timer.start(200)

    def _get(self):
        try:
            self.current_value = getattr(self.proxy, self.attribute_name)
        except Exception as e:
            # popup should happen here
            self.val_edit.setStyleSheet("background-color: red")
        else:
            self.val_edit.setStyleSheet("background-color: green")
            if isinstance(self.current_value, str):
                self.val_edit.setText('"{}"'.format(self.current_value))
            else:
                self.val_edit.setText(str(self.current_value))
            self.type_label.setText(str(type(self.current_value)))
        finally:
            self._feedback_timer.start(200)


if __name__ == '__main__':

    proxy = Proxy("localhost:6000")

    app = QtGui.QApplication([])
    p = ProxyWidget(proxy=proxy)
    p.show()
    app.exec_()
