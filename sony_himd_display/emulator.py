from threading import Thread
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from dataclasses import dataclass, field
from copy import deepcopy
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'RH10 emulator running!')
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = b''
        while len(body) < content_length:
            body += self.rfile.read(content_length - len(body))
        self.send_response(200)
        self.end_headers()
        string = body.decode("utf-8")
        handle_event(json.loads(string))


def server_main():
    httpd = HTTPServer(('localhost', 36002), SimpleHTTPRequestHandler)
    httpd.serve_forever()

ht_thread = Thread(target=server_main)
ht_thread.start()

def create_screen_matrix():
    a = []
    for _ in range(6):
        a.append(['']*20)
    return a

@dataclass
class State:
    screen_matrix: list[list[str]] = field(default_factory=create_screen_matrix)
    

current_state = State()
states = []

def handle_event(event):
    global current_state, states
    _type = event["type"]
    if _type == "display":
        row, col, data = event["row"], event["col"], event["data"]
        current_state.screen_matrix[row][col:col+len(data)] = data
    if _type == "clear":
        current_state.screen_matrix = create_screen_matrix()
    
    states.append(deepcopy(current_state))

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        self.currentEvent = 0
        self.setWindowTitle("Emulator")

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.check_for_update)
        self.timer.start(100)

        self.label = QtWidgets.QLabel()
        self.label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.canvas = QtGui.QPixmap(128, 96)
        self.canvas.fill(Qt.black)
        self.label.setPixmap(self.canvas)
        
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setMaximum(100)
        self.slider.valueChanged.connect(self.update_slider)
        
        self.totalEvents = QtWidgets.QLabel()
        self.currentEvents = QtWidgets.QLabel()
        
        eventsBox = QtWidgets.QWidget()
        eventsLayout = QtWidgets.QHBoxLayout()
        eventsLayout.addWidget(self.currentEvents)
        eventsLayout.addStretch()
        eventsLayout.addWidget(self.totalEvents)
        eventsBox.setLayout(eventsLayout)
        
        reset_state = QtWidgets.QPushButton("Reset")
        def _reset():
            global current_state
            current_state = State()
        reset_state.clicked.connect(_reset)
        reset_all_state = QtWidgets.QPushButton("Full Reset")
        def _reset_f():
            global current_state, states
            states = []
            current_state = State()
        reset_all_state.clicked.connect(_reset_f)
        
        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        layout.addWidget(eventsBox)
        layout.addWidget(reset_state)
        layout.addWidget(reset_all_state)
        
        root.setLayout(layout)
        self.setCentralWidget(root)
        
        self.update_counters()

    def check_for_update(self):
        old_max = self.slider.maximum()
        lstat = len(states)
        if old_max != lstat:
            self.update_slider()
        
    def update_counters(self):
        lstat = len(states)
        is_max = self.slider.maximum() == self.slider.value()
        self.currentEvent = self.slider.value()
        self.currentEvents.setText(str(self.currentEvent))
        self.totalEvents.setText(str(lstat))
        self.slider.setMaximum(lstat)
        if is_max:
            self.slider.setValue(lstat)
    
    def update_slider(self):
        self.update_counters()
        sval = self.slider.value()
        if sval == 0:
            state = State()
        else:
            state = states[sval - 1]
        self.render_state(state)

    def render_state(self, state):
        self.canvas.fill(Qt.black)
        painter = QtGui.QPainter(self.label.pixmap())
        pen = QtGui.QPen()
        pen.setWidth(1)
        pen.setColor(QtGui.QColor(0, 101, 184))  # r, g, b
        painter.setPen(pen)
        painter.fillRect(0, 0, 128, 96, QtGui.QColor(0,0,0))

        # Is this line there permanently?
        painter.drawLine(0, 8, 128, 8)

        x, y = 0, 8
        font = QtGui.QFont()
        font.setFamily('monospace')
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)

        remaps = {
            # A terrible way to convert to zenkaku numbers:
            **dict((f"big {x}", chr(x+65296)) for x in range(10)),
            "big :": ":"
        }

        for row in range(6):
            for char in state.screen_matrix[row]:
                try:
                    painter.drawText(x, y, remaps.get(char, char))
                except Exception as e:
                    print(e) 
                x += 6
            y += 16
            x = 0
        painter.end()
        self.update()
        
if __name__ == "__main__":
    app = QtWidgets.QApplication( [] )
    window = MainWindow()
    window.show()
    app.exec_()
    
