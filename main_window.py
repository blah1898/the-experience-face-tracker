import sys
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from typing import List, Tuple, Optional
from open_see_data import parse_open_see_data
import select
import socket
import pythonosc.udp_client
import subprocess
import os
import re
import signal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENSEEFACE_DIR = os.path.join(SCRIPT_DIR, "OpenSeeface-v1.20.4")
FACETRACKER_BINARY = os.path.join(OPENSEEFACE_DIR, "Binary", "facetracker.exe")
PACKET_SIZE = 1785

MODELS_WITH_DESCRIPTION: List[Tuple[int, str]] = [
    (-1, "-1 - Very very fast and very low accuracy"),
    (0, "0 - Very fast, low accuracy model"),
    (1, "1 - Slightly slower model with better accuracy"),
    (2, "2 - Slower model with good accuracy"),
    (3, "3 - Slowest, highest accuracy model")
]
"""The models that the OpenSeeFace face tracker provides"""

class GetCamerasSignals(QObject):
    """The signals that may be emitted by the GetCamerasWorker runnable."""

    error = pyqtSignal(str, name='error')
    """Emitted when there's an error obtaining the data with an error
    message."""

    result = pyqtSignal(list, name="result")
    """Emitted upon successfully obtaining cameras, returns a list of
    tuples in (id, name) format"""

class GetCamerasWorker(QRunnable):
    """Runs the face tracker script and parse's it's output to get the
    available cameras."""

    signals = GetCamerasSignals()

    @pyqtSlot()
    def run(self):
        completed_process = subprocess.run([FACETRACKER_BINARY, "-l", "1"],
            capture_output=True, encoding=sys.stdout.encoding)

        if completed_process.returncode != 0:
            self.signals.error.emit(f"Error running process (returncode {completed_process.returncode})")
            return
        
        camera_regexp = re.compile("^(\d+): (.+)$")
        cameras = list()

        # Skip over the first line, since it's the "Available cameras:"
        for line in completed_process.stdout.strip().splitlines()[1:]:
            matches = camera_regexp.match(line)
            if matches is not None:
                # Try to parse the ID and the matches
                try:
                    cameras.append((int(matches.group(1)), matches.group(2)))
                except:
                    pass
        
        self.signals.result.emit(cameras)

class FaceTrackingSignals(QObject):
    """QObject containing every signal that FaceTrackingThead might emit"""

    error = pyqtSignal(str)
    """Emitted whenever an error ocurrs during face tracking, emits a
    message with the error"""

    tracking = pyqtSignal(tuple)
    """Emitted when new face tracking information is available, emits a tuple
    with the (pitch, yaw, roll) format"""

    stopped = pyqtSignal()
    """Emitted when the process is stopped, either manually or by the
    facetracker process terminating"""


class FaceTrackingThread(QThread):
    signals = FaceTrackingSignals()
    model = 1
    camera_id = 0
    visualize = False
    port = 7600
    pitch_offset = 0.0
    yaw_offset = 0.0
    roll_offset = 0.0

    _face_tracking_process: subprocess.Popen
    _should_run = True

    def run(self):
        # Prepare to receive facetracking data
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(0)
        sock.bind(("127.0.0.1", 0))
        face_tracker_port = sock.getsockname()[1]

        # Start the process
        self._should_run = True
        face_tracking_process_args = [FACETRACKER_BINARY,
            "-c", str(self.camera_id),
            "-m", str(self.model),
            "-p", str(face_tracker_port)]

        if (self.visualize):
            face_tracking_process_args.append("-v")
            face_tracking_process_args.append("1")

        face_tracking_process: subprocess.Popen = subprocess.Popen(face_tracking_process_args)
        osc_client = pythonosc.udp_client.SimpleUDPClient("127.0.0.1", self.port)
        while(self._should_run):
            ready = select.select([sock], [], [], 5.0)
            buf = b''
            if (ready[0]):
                while(len(buf) < PACKET_SIZE):
                    newdata, addr = sock.recvfrom(PACKET_SIZE)
                    if (len(newdata) == 0):
                        # Data packet was not complete, discard
                        break
                    buf += newdata
            else:
                continue

            if (len(buf) < PACKET_SIZE):
                # Incomplete packet, discard
                continue

            parsed = parse_open_see_data(buf)
            self.signals.tracking.emit(parsed.rotation)
            osc_client.send_message("/SceneRotator/pitch", parsed.rotation.x + self.pitch_offset)
            osc_client.send_message("/SceneRotator/yaw", parsed.rotation.y + self.yaw_offset)
            osc_client.send_message("/SceneRotator/roll", parsed.rotation.z + self.roll_offset)

        face_tracking_process.terminate()
        self._should_run = False
        self.signals.stopped.emit()

    @pyqtSlot()
    def stop(self):
        self._should_run = False

    @pyqtSlot(float)
    def set_pitch_offset(self, pitch_offset: float):
        self.pitch_offset = pitch_offset

    @pyqtSlot(float)
    def set_yaw_offset(self, yaw_offset: float):
        self.yaw_offset = yaw_offset

    @pyqtSlot(float)
    def set_roll_offset(self, roll_offset: float):
        self.roll_offset = roll_offset


class MainWindow(QMainWindow):
    layout: QVBoxLayout

    thread_pool: QThreadPool
    """A thread pool for running everything in the background"""
    camera_selector: QComboBox
    """The combo box that selects which camera to use"""
    cameras: List[Tuple[int, str]]
    """A list of available cameras"""
    model_selector: QComboBox
    """The combo box to select the model to use"""
    port_text_box: QLineEdit
    """The text box to put the port in"""
    visualize_checkbox: QCheckBox
    """The checkbox to use visualization"""
    pitch_offset_dial: QDial
    """The dial that represents the pitch offset"""
    yaw_offset_dial: QDial
    """The dial that represents the yaw offset"""
    roll_offset_dial: QDial
    """The dial that represents the roll offset"""
    set_current_as_center_button: QPushButton
    """The button to capture the current rotation as a neutral rotation"""

    current_pitch_dial: QDial
    """The dial which shows the current pitch"""
    current_pitch_label: QLabel
    """The label which shows the current pitch"""

    current_yaw_dial: QDial
    """The dial which shows the current yaw"""
    current_yaw_label: QLabel
    """The label which shows the current yaw"""

    current_roll_dial: QDial
    """The dial which shows the current roll"""
    current_roll_label: QLabel
    """The label which shows the current roll"""

    start_stop_tracking_button: QPushButton
    """The button to launch or stop the face tracker."""
    use_current_rotation_as_zero: QPushButton
    """The button that sets the current rotation as zero."""

    face_tracking_thread: Optional[FaceTrackingThread] = None
    """The thread in charge of face tracking."""
    last_detected_rotation: Optional[Tuple[float, float, float]] = None
    """The last detected roation. None if there hasn't been any detection
    performed."""



    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.layout = QVBoxLayout()
        self.thread_pool = QThreadPool()
        get_cameras = GetCamerasWorker()
        get_cameras.signals.result.connect(self.on_cameras_received)
        self.thread_pool.start(get_cameras)

        # Row 1
        row1 = QHBoxLayout()

        # Camera selector
        camera_selector_label = QLabel("Camera: ")
        camera_selector_label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred))
        self.camera_selector = QComboBox()
        row1.addWidget(camera_selector_label)
        row1.addWidget(self.camera_selector)

        # Model selector
        model_selector_label = QLabel("Model: ")
        model_selector_label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred))
        self.model_selector = QComboBox()
        self.model_selector.addItems([desc for _, desc in MODELS_WITH_DESCRIPTION])
        row1.addWidget(model_selector_label)
        row1.addWidget(self.model_selector)

        self.layout.addLayout(row1)

        # Row 2
        row2 = QHBoxLayout()

        port_label = QLabel("Port: ")
        port_label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred))
        row2.addWidget(port_label)

        self.port_text_box = QLineEdit()
        self.port_text_box.setText("7600")
        self.port_text_box.setInputMask("90000")
        row2.addWidget(self.port_text_box)

        self.visualize_checkbox = QCheckBox("Visualize")
        row2.addWidget(self.visualize_checkbox)

        self.layout.addLayout(row2)

        # Row 3
        row3 = QHBoxLayout()

        self.start_stop_tracking_button = QPushButton("Start")
        self.start_stop_tracking_button.clicked.connect(self.on_start_stop_tracking_clicked)

        row3.addWidget(self.start_stop_tracking_button)

        self.layout.addLayout(row3)

        self.layout.addWidget(QLabel("Current Rotation (no offset):"))

        # Row 4
        row4 = QHBoxLayout()

        # For angles, we'll be using 10ths of a degres
        current_pitch_group = QVBoxLayout()

        self.current_pitch_dial = QDial()
        self.current_pitch_dial.setMinimum(-900)
        self.current_pitch_dial.setMaximum(900)
        self.current_pitch_dial.setEnabled(False)
        self.current_pitch_label = QLabel("Pitch: 0.00")
        current_pitch_group.addWidget(self.current_pitch_dial)
        current_pitch_group.addWidget(self.current_pitch_label)
        row4.addLayout(current_pitch_group)

        current_yaw_group = QVBoxLayout()

        self.current_yaw_dial = QDial()
        self.current_yaw_dial.setMinimum(-900)
        self.current_yaw_dial.setMaximum(900)
        self.current_yaw_dial.setEnabled(False)
        self.current_yaw_label = QLabel("Yaw: 0.00")
        current_yaw_group.addWidget(self.current_yaw_dial)
        current_yaw_group.addWidget(self.current_yaw_label)
        row4.addLayout(current_yaw_group)

        current_roll_group = QVBoxLayout()

        self.current_roll_dial = QDial()
        self.current_roll_dial.setMinimum(-900)
        self.current_roll_dial.setMaximum(900)
        self.current_roll_dial.setEnabled(False)
        self.current_roll_label = QLabel("Roll: 0.00")
        current_roll_group.addWidget(self.current_roll_dial)
        current_roll_group.addWidget(self.current_roll_label)
        row4.addLayout(current_roll_group)

        self.layout.addLayout(row4)

        self.layout.addWidget(QLabel("Offset:"))

        # Row 5
        row5 = QHBoxLayout()

        # For angles, we'll be using 10ths of a degres
        offset_pitch_group = QVBoxLayout()

        self.offset_pitch_dial = QDial()
        self.offset_pitch_dial.setMinimum(-900)
        self.offset_pitch_dial.setMaximum(900)
        self.offset_pitch_dial.valueChanged.connect(self.on_offset_pitch_changed)
        self.offset_pitch_label = QLabel("Pitch: 0.00")
        offset_pitch_group.addWidget(self.offset_pitch_dial)
        offset_pitch_group.addWidget(self.offset_pitch_label)
        row5.addLayout(offset_pitch_group)

        offset_yaw_group = QVBoxLayout()

        self.offset_yaw_dial = QDial()
        self.offset_yaw_dial.setMinimum(-900)
        self.offset_yaw_dial.setMaximum(900)
        self.offset_yaw_dial.valueChanged.connect(self.on_offset_yaw_changed)
        self.offset_yaw_label = QLabel("Yaw: 0.00")
        offset_yaw_group.addWidget(self.offset_yaw_dial)
        offset_yaw_group.addWidget(self.offset_yaw_label)
        row5.addLayout(offset_yaw_group)

        offset_roll_group = QVBoxLayout()

        self.offset_roll_dial = QDial()
        self.offset_roll_dial.setMinimum(-900)
        self.offset_roll_dial.setMaximum(900)
        self.offset_roll_dial.valueChanged.connect(self.on_offset_roll_changed)
        self.offset_roll_label = QLabel("Roll: 0.00")
        offset_roll_group.addWidget(self.offset_roll_dial)
        offset_roll_group.addWidget(self.offset_roll_label)
        row5.addLayout(offset_roll_group)

        self.layout.addLayout(row5)

        # Row 6
        row6 = QHBoxLayout()
        self.use_current_rotation_as_zero = QPushButton("Use current rotation as zero")
        self.use_current_rotation_as_zero.setEnabled(False)
        self.use_current_rotation_as_zero.clicked.connect(self.on_use_current_rotation_as_zero_clicked)
        row6.addWidget(self.use_current_rotation_as_zero)

        self.layout.addLayout(row6)

        # Set central widget
        widget = QWidget()
        widget.setLayout(self.layout)
        self.setCentralWidget(widget)
    
    @pyqtSlot()
    def on_use_current_rotation_as_zero_clicked(self):
        if (self.last_detected_rotation is not None):
            self.offset_pitch_dial.setValue(-int(self.last_detected_rotation[0] * 10))
            self.offset_yaw_dial.setValue(-int(self.last_detected_rotation[1] * 10))
            self.offset_roll_dial.setValue(-int(self.last_detected_rotation[2] * 10))

    @pyqtSlot()
    def on_start_stop_tracking_clicked(self):
        if self.face_tracking_thread is None or not self.face_tracking_thread.isRunning():
            self.set_enabled_on_tracking_related_params(False)
            self.face_tracking_thread = FaceTrackingThread()
            self.start_stop_tracking_button.setText("Stop")

            selected_camera = self.cameras[self.camera_selector.currentIndex()][0]
            self.face_tracking_thread.camera_id = selected_camera

            selected_model = MODELS_WITH_DESCRIPTION[self.model_selector.currentIndex()][0]
            self.face_tracking_thread.model = selected_model

            self.face_tracking_thread.visualize = self.visualize_checkbox.isChecked()
            self.face_tracking_thread.signals.stopped.connect(self.on_face_tracking_thread_stopped)
            self.face_tracking_thread.signals.tracking.connect(self.on_tracking_rotation_received)
            self.face_tracking_thread.start()
        else:
            self.start_stop_tracking_button.setEnabled(False)
            self.face_tracking_thread.stop()

    def set_enabled_on_tracking_related_params(self, enabled: bool):
        self.camera_selector.setEnabled(enabled)
        self.model_selector.setEnabled(enabled)
        self.port_text_box.setEnabled(enabled)
        self.visualize_checkbox.setEnabled(enabled)
        self.use_current_rotation_as_zero.setEnabled(not enabled)

    @pyqtSlot(int)
    def on_offset_pitch_changed(self, new_value: int):
        converted = float(new_value) / 10
        self.offset_pitch_label.setText(f"Pitch: {converted:.2f}")
        if (self.face_tracking_thread is not None):
            self.face_tracking_thread.set_pitch_offset(converted)

    @pyqtSlot(int)
    def on_offset_yaw_changed(self, new_value: int):
        converted = float(new_value) / 10
        self.offset_yaw_label.setText(f"Yaw: {converted:.2f}")
        if (self.face_tracking_thread is not None):
            self.face_tracking_thread.set_yaw_offset(converted)

    @pyqtSlot(int)
    def on_offset_roll_changed(self, new_value: int):
        converted = float(new_value) / 10
        self.offset_roll_label.setText(f"Roll: {converted:.2f}")
        if (self.face_tracking_thread is not None):
            self.face_tracking_thread.set_roll_offset(converted)
    
    @pyqtSlot()
    def on_face_tracking_thread_stopped(self):
        self.set_enabled_on_tracking_related_params(True)
        self.start_stop_tracking_button.setText("Start")
        self.start_stop_tracking_button.setEnabled(True)

    @pyqtSlot(list)
    def on_cameras_received(self, cameras: List[Tuple[int, str]]):
        self.camera_selector.clear()
        self.cameras = cameras
        self.camera_selector.addItems([desc for _, desc in cameras])

    @pyqtSlot(tuple)
    def on_tracking_rotation_received(self, rotation: Tuple[float, float, float]):
        self.last_detected_rotation = rotation
        self.current_pitch_dial.setValue(int(rotation[0] * 10))
        self.current_pitch_label.setText(f"Pitch: {rotation[0]:.2f}")
        self.current_yaw_dial.setValue(int(rotation[1] * 10))
        self.current_yaw_label.setText(f"Yaw: {rotation[1]:.2f}")
        self.current_roll_dial.setValue(int(rotation[2] * 10))
        self.current_roll_label.setText(f"Roll: {rotation[2]:.2f}")

