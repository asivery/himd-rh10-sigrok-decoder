from threading import Thread
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from dataclasses import dataclass, field
from copy import deepcopy
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Union
import json

DEFAULT_COLOR = (0, 101, 184)
SCROLL_BAR_WIDTH = 6
TOP_RESERVED_PX = 15
TRACK_BAR_WIDTH = 65
TRACK_BAR_HMARGIN = 5
TRACK_BAR_STARTX = 60 #?

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
    start: int = 0x00
    end: int = 0x19

def create_screen_matrix():
    a = []
    for _ in range(6):
        a.append(Row())
    return a

@dataclass
class ScrollBar:
    enabled: bool = False
    from_px: int = 0
    to_px: int = 0

@dataclass
class TrackBar:
    enabled: bool = False
    from_px: int = 0
    to_px: int = 0
    row: int = 0
    
@dataclass
class Battery:
    outline: bool
    enabled: bool
    charging: bool
    segments: int

@dataclass
class State:
    screen_matrix: List[Row] = field(default_factory=create_screen_matrix)
    message: str = "<unset>"
    scroll_bar_state: ScrollBar = field(default_factory=ScrollBar)
    track_bar_state: TrackBar = field(default_factory=TrackBar)
    bar_enabled: bool = False
    groups_icon_enabled: bool = False
    is_hi_enabled: bool = False
    is_md_enabled: bool = False
    battery: Battery = Battery(False, False, False, 0)
    play_modes: list[str] = []
    current_playback_glyph: str = ""

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
        start = current_state.screen_matrix[row].start
        data = data[:current_state.screen_matrix[row].end - start]
        if clear_remain:
            # E0, E3
            current_state.screen_matrix[row].data[col+start:] = data
        else:
            current_state.screen_matrix[row].data[col+start:col+len(data)] = data
        current_state.message = f"Set {row=} to {data}"
    if _type == "clear":
        # HACK: Not sure if this is meant to work like this, or if there's a separate command to clear
        # the track progress bar.
        if current_state.track_bar_state.row in event['rows']:
            current_state.track_bar_state.enabled = False
        for row in event["rows"]:
            current_state.screen_matrix[row].data = [''] * 20
            current_state.screen_matrix[row].start = 0
            current_state.screen_matrix[row].end = 0x19
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
    if _type == "scrollbar":
        current_state.scroll_bar_state.from_px = event['from']
        current_state.scroll_bar_state.to_px = event['to']
        current_state.scroll_bar_state.enabled = event['enabled']
        current_state.message = f'Update scroll bar {current_state.scroll_bar_state.from_px} => {current_state.scroll_bar_state.to_px}, enabled = {current_state.scroll_bar_state.enabled}'
    if _type == "trackbar":
        current_state.track_bar_state.enabled = event['enabled']
        current_state.track_bar_state.to_px = event['to']
        current_state.track_bar_state.from_px = event['from']
        current_state.track_bar_state.row = event['rows']
        current_state.message = f'Update track bar {current_state.track_bar_state.from_px} => {current_state.track_bar_state.to_px}, enabled = {current_state.track_bar_state.enabled}'
    if _type == "bar":
        current_state.bar_enabled = event['enabled']
    if _type == "format":
        current_state.is_hi_enabled = event['hi']
        current_state.is_md_enabled = event['md']
    if _type == "groups":
        current_state.groups_icon_enabled = event['enabled']
    if _type == "glyph":
        current_state.current_playback_glyph = event['glyph']
    if _type == "playmode":
        current_state.play_modes = event['entries']
    if _type == "limit":
        for row in event['rows']:
            current_state.screen_matrix[row].start = event['start']
            current_state.screen_matrix[row].end = event['end']
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


    def render_state(self, state: State):
        self.canvas.fill(Qt.black)
        painter = QtGui.QPainter(self.label.pixmap())
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(0, 0, 128, 96, QtGui.QColor(0,0,0))
        self.set_painter_color(painter)

        # Is this line there permanently?
        # No
        if state.bar_enabled:
            painter.drawLine(0, TOP_RESERVED_PX, 128, TOP_RESERVED_PX)
        x, y = 0, TOP_RESERVED_PX
        font = QtGui.QFont()
        font.setFamily('monospace')
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)

        remaps = {
            # A terrible way to convert to zenkaku numbers:
            **dict((f"big {x}", chr(x+65296)) for x in range(10)),
            "big :": ":",
            "volume icon": "🔊",
            "music note": "🎵",
            "folder": "📁",
            "minidisc": "💽",
        }

        for row in range(6):
            if state.screen_matrix[row].inverted:
                self.set_painter_color(painter, (0, 0, 0))
                invert_box_width = (128 - SCROLL_BAR_WIDTH - 1) if state.scroll_bar_state.enabled else 128
                painter.fillRect(x, y - 12, invert_box_width, 16, QtGui.QColor(*DEFAULT_COLOR))
            for char in state.screen_matrix[row].data:
                try:
                    painter.drawText(x, y, remaps.get(char, char))
                except Exception as e:
                    print(e) 
                x += 6
            self.set_painter_color(painter)
            y += 16
            x = 0
            
        if state.track_bar_state.enabled:
            self.set_painter_color(painter)
            painter.drawRoundedRect(
                TRACK_BAR_STARTX,
                16 * state.track_bar_state.row + TRACK_BAR_HMARGIN,
                TRACK_BAR_WIDTH,
                16 - TRACK_BAR_HMARGIN,
                TRACK_BAR_HMARGIN, TRACK_BAR_HMARGIN
            )
            path = QtGui.QPainterPath()
            path.addRoundedRect(
                TRACK_BAR_STARTX,
                16 * state.track_bar_state.row + TRACK_BAR_HMARGIN + state.track_bar_state.from_px - 1,
                state.track_bar_state.to_px - state.track_bar_state.from_px + 1,
                16 - TRACK_BAR_HMARGIN,
                TRACK_BAR_HMARGIN, TRACK_BAR_HMARGIN
            )
            painter.fillPath(path, QtGui.QColor(*DEFAULT_COLOR))

        if state.scroll_bar_state.enabled:
            painter.fillRect(128 - SCROLL_BAR_WIDTH, TOP_RESERVED_PX, 1, 96 - TOP_RESERVED_PX, QtGui.QColor(*DEFAULT_COLOR))
            painter.fillRect(128 - SCROLL_BAR_WIDTH, state.scroll_bar_state.from_px + TOP_RESERVED_PX, SCROLL_BAR_WIDTH, state.scroll_bar_state.to_px - state.scroll_bar_state.from_px, QtGui.QColor(*DEFAULT_COLOR))
        painter.end()
        self.update()
        self.statusBar().showMessage(state.message, 2000)
        
if __name__ == "__main__":
    app = QtWidgets.QApplication( [] )
    window = MainWindow()
    window.show()
    app.exec_()
    
