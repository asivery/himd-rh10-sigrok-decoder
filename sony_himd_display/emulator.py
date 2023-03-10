from threading import Thread
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from dataclasses import dataclass, field
from copy import deepcopy
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List
import json

DEFAULT_COLOR = (0, 101, 184)

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
@dataclass
class Row:
    data: List[str] = field(default_factory=lambda: [''] * 20)
    inverted: bool = False

def create_screen_matrix():
    a = []
    for _ in range(6):
        a.append(Row())
    return a


@dataclass
class State:
    screen_matrix: List[Row] = field(default_factory=create_screen_matrix)
    message: str = "<unset>"
    

current_state = State()
states = []
events = []

def handle_event(event):
    global current_state, states, events
    events.append(event)
    current_state.message = "Unset"
    _type = event["type"]
    if _type == "display":
        row, col, data, clear_remain = event["row"], event["col"], event["data"], event["clearRemaining"]
        if clear_remain:
            # E0, E3
            current_state.screen_matrix[row].data[col:] = data
        else:
            current_state.screen_matrix[row].data[col:col+len(data)] = data
        current_state.message = f"Set {row=} to {data}"
    if _type == "clear":
        for row in event["rows"]:
            current_state.screen_matrix[row].data = [''] * 20
        current_state.message = f"Clear rows: {', '.join(str(x) for x in event['rows'])}"
    if _type == "init":
        current_state = State()
        current_state.message = "init"
        states = []
    if _type == "invert":
        rows = event["rows"]
        current_state.message = f'Invert rows: {rows}'
        #for row in range(6):
            #if row in rows:
                #current_state.screen_matrix[row].inverted = not current_state.screen_matrix[row].inverted
            #else:
                #current_state.screen_matrix[row].inverted = False
        for row in range(6):
            current_state.screen_matrix[row].inverted = row in rows
    
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
        def dump_events():
            with open("events", "w") as e:
                json.dump(events, e)
        def load_events():
            global events
            with open("events", "r") as e:
                events = json.load(e)
                for q in events:
                    handle_event(q)
        save_events_b = QtWidgets.QPushButton("Save Events")
        save_events_b.clicked.connect(dump_events)
        load_events_b = QtWidgets.QPushButton("Load Events")
        load_events_b.clicked.connect(load_events)
        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        layout.addWidget(eventsBox)
        layout.addWidget(reset_state)
        layout.addWidget(reset_all_state)
        layout.addWidget(save_events_b)
        layout.addWidget(load_events_b)
        
        root.setLayout(layout)
        self.setCentralWidget(root)
        
        self.statusBar().show()
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


    def set_painter_color(self, painter, color = DEFAULT_COLOR):
        pen = QtGui.QPen()
        pen.setWidth(1)
        pen.setColor(QtGui.QColor(*color))  # r, g, b
        painter.setPen(pen)


    def render_state(self, state):
        self.canvas.fill(Qt.black)
        painter = QtGui.QPainter(self.label.pixmap())
        painter.fillRect(0, 0, 128, 96, QtGui.QColor(0,0,0))
        self.set_painter_color(painter)

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
            "big :": ":",
            "volume icon": "????",
            "music note": "????",
            "folder": "????",
            "minidisc": "????",
        }

        for row in range(6):
            if state.screen_matrix[row].inverted:
                self.set_painter_color(painter, (0, 0, 0))
                painter.fillRect(x, y - 12, 128, 16, QtGui.QColor(*DEFAULT_COLOR))
            for char in state.screen_matrix[row].data:
                try:
                    painter.drawText(x, y, remaps.get(char, char))
                except Exception as e:
                    print(e) 
                x += 6
            self.set_painter_color(painter)
            y += 16
            x = 0
        painter.end()
        self.update()
        self.statusBar().showMessage(state.message, 2000)
        
if __name__ == "__main__":
    app = QtWidgets.QApplication( [] )
    window = MainWindow()
    window.show()
    app.exec_()
    
