import sys
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

from QPanda3D.Panda3DWorld import Panda3DWorld
from QPanda3D.QPanda3DWidget import QPanda3DWidget, QPanda3DSynchronizer

from direct.actor.Actor import Actor
from panda3d.core import loadPrcFileData

from actions import Jasper, client

def patched_synchronizer_init(self, qPanda3DWidget, FPS=60):
    QTimer.__init__(self)
    self.qPanda3DWidget = qPanda3DWidget
    dt = 1000. / FPS
    self.setInterval(int(dt))
    self.timeout.connect(self.tick)

QPanda3DSynchronizer.__init__ = patched_synchronizer_init

loadPrcFileData("", "load-file-type gltf panda3d_gltf.core:GltfLoader")
loadPrcFileData("", "model-cache-dir /dev/null")


class JasperPandaWorld(Panda3DWorld):
    def __init__(self):
        Panda3DWorld.__init__(self)

        self.setBackgroundColor(0.5, 0.5, 0.5)

        model_path = "models/animations/eric-rigged-001-rigged-3d-business-man.glb"
        animations_to_load = {
            "idle": "models/animations/idle.glb", "jump": "models/animations/jump.glb",
            "left_strafe": "models/animations/left strafe.glb", "left_strafe_walking": "models/animations/left strafe walking.glb",
            "left_turn_90": "models/animations/left turn 90.glb", "left_turn": "models/animations/left turn.glb",
            "right_strafe": "models/animations/right strafe.glb", "right_strafe_walking": "models/animations/right strafe walking.glb",
            "right_turn_90": "models/animations/right turn 90.glb", "right_turn": "models/animations/right turn.glb",
            "run": "models/animations/running.glb", "walk": "models/animations/walking.glb",
            "thinking": "models/animations/Thinking.glb", "executing": "models/animations/Searching Files High.glb",
            "searching": "models/animations/Rummaging.glb"
        }
        
        try:
            self.actor = Actor(model_path, animations_to_load)
            self.actor.reparent_to(self.render)
            self.actor.setPos(0, 0, 0)
            self.actor.loop("idle")

            self.floor = self.loader.loadModel("models/environment")
            self.floor.reparentTo(self.render)
            self.floor.setScale(100, 100, 1)
            self.floor.setPos(0, 0, 0)
            
            self.cam.setPos(0, -4, 1)
            self.cam.setHpr(0, 0, 0)
            
        except Exception as e:
            print(f"FATAL: Could not load models/animations. Error: {e}")
            raise e


class JasperWorker(QThread):
    info_received = pyqtSignal(dict)
    def __init__(self, message, jasper_instance):
        super().__init__()
        self.message = message
        self.jasper = jasper_instance
        self.jasper.callback = self.callback

    def run(self):
        self.jasper.send_message(self.message)

    def callback(self, info):
        self.info_received.emit(info)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jasper Assistant")
        self.setGeometry(100, 100, 800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        self.world = JasperPandaWorld()
        
        self.panda_widget = QPanda3DWidget(self.world)
        layout.addWidget(self.panda_widget, 1)

        controls_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message...")
        self.input_field.returnPressed.connect(self.send_from_gui)
        controls_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_from_gui)
        controls_layout.addWidget(self.send_button)
        layout.addLayout(controls_layout)
        
        self.output_label = QLabel("Welcome.")
        self.output_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.output_label)

        self.jasper = Jasper(client) 
        self.jasper_worker = None

    def handle_jasper_info(self, info: dict):
        if message := info.get("message"):
            self.output_label.setText(message)
        if state := info.get("state"):
            if hasattr(self.world, 'actor') and self.world.actor:
                self.world.actor.loop(state)

    def send_from_gui(self):
        text_to_send = self.input_field.text()
        if text_to_send.strip() != "" and (self.jasper_worker is None or not self.jasper_worker.isRunning()):
            self.jasper_worker = JasperWorker(text_to_send, self.jasper)
            self.jasper_worker.info_received.connect(self.handle_jasper_info)
            self.jasper_worker.start()
            self.input_field.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())