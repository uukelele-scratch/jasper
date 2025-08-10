import sys
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

from QPanda3D.Panda3DWorld import Panda3DWorld
from QPanda3D.QPanda3DWidget import QPanda3DWidget, QPanda3DSynchronizer

from direct.actor.Actor import Actor
from panda3d.core import loadPrcFileData

from jinja2 import Template

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

animations_to_load = {
    "idle":                "models/animations/idle.glb",
    "jump":                "models/animations/jump.glb",
    "left_strafe":         "models/animations/left strafe.glb",
    "left_strafe_walking": "models/animations/left strafe walking.glb",
    "left_turn_90":        "models/animations/left turn 90.glb",
    "left_turn":           "models/animations/left turn.glb",
    "right_strafe":        "models/animations/right strafe.glb",
    "right_strafe_walking":"models/animations/right strafe walking.glb",
    "right_turn_90":       "models/animations/right turn 90.glb",
    "right_turn":          "models/animations/right turn.glb",
    "run":                 "models/animations/running.glb",
    "walk":                "models/animations/walking.glb",
    "thinking":            "models/animations/Thinking.glb",
    "executing":           "models/animations/Searching Files High.glb",
    "searching":           "models/animations/Rummaging.glb",
    "analysing":           "models/animations/Searching Files High.glb",
}

class JasperPandaWorld(Panda3DWorld):
    def __init__(self):
        Panda3DWorld.__init__(self)

        self.setBackgroundColor(0.5, 0.5, 0.5)

        model_path = "models/animations/eric-rigged-001-rigged-3d-business-man.glb"
        
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
    animation_request_signal = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jasper Assistant")
        self.setGeometry(100, 100, 800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        self.world = JasperPandaWorld()
        
        self.panda_widget = QPanda3DWidget(self.world)
        layout.addWidget(self.panda_widget, 1)

        io_layout = QVBoxLayout()

        controls_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message...")
        self.input_field.returnPressed.connect(self.send_from_gui)
        controls_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_from_gui)
        controls_layout.addWidget(self.send_button)
        
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setAcceptRichText(True)
        self.output_text_edit.setStyleSheet("font-size: 14px; padding: 5px;")
        io_layout.addWidget(self.output_text_edit)
        io_layout.addLayout(controls_layout)

        layout.addLayout(io_layout)

        animation_prompt = open("animation_prompt.md").read()
        animations_to_ignore = ["idle", "thinking", "executing", "searching"]
        animations = [animation for animation in animations_to_load.keys() if animation not in animations_to_ignore]
        animation_prompt = Template(animation_prompt).render(
            animations = '\n- '.join(animations)
        )

        self.jasper = Jasper(client, overrides={"sys_prompt": animation_prompt, "execute": {"animation": self.handle_animation}}) 
        self.jasper_worker = None

        self.is_custom_animation_active = False
        self.custom_animation_timer = QTimer(self)
        self.custom_animation_timer.setSingleShot(True)
        self.custom_animation_timer.timeout.connect(self.return_to_idle)

        self.animation_request_signal.connect(self._perform_animation_in_gui_thread)

    def handle_jasper_info(self, info: dict):
        if message := info.get("message"):
            self.output_text_edit.append(message)
        if state := info.get("state"):
            if hasattr(self.world, 'actor') and self.world.actor:
                if not self.is_custom_animation_active:
                    current_animation = self.world.actor.getCurrentAnim()
                    if current_animation != state:
                        self.world.actor.loop(state)
                map = {
                    "idle": None,
                    "thinking": "Thinking...",
                    "executing": "Executing code...",
                    "searching": "Searching the web...",
                    "analysing": "Analysing files...",
                }
                text = map.get(info["state"])
                self.output_text_edit.append(text)

    def _perform_animation_in_gui_thread(self, animation: str, delay_ms: int):
        try:
            if hasattr(self.world, 'actor') and self.world.actor:
                if self.custom_animation_timer.isActive():
                    self.custom_animation_timer.stop()

                self.world.actor.stop()
                self.is_custom_animation_active = True
                self.world.actor.play(animation)
                
                self.custom_animation_timer.start(delay_ms)
                return "Animation initiated successfully."
            return "Warning: Actor not yet initialized (GUI thread)."
        except Exception as e:
            self.is_custom_animation_active = False
            if self.custom_animation_timer.isActive():
                self.custom_animation_timer.stop()
            return f"Error playing animation in GUI thread: {e}"


    def handle_animation(self, animation):
        try:
            if not (hasattr(self.world, 'actor') and self.world.actor):
                return "Warning: Actor not yet initialized."

            anim_length = 0
            try:
                duration_val = self.world.actor.getDuration(animation)
                if duration_val is not None:
                    anim_length = duration_val
                else:
                    print(f"Warning: getDuration returned None for {animation.strip()}. Defaulting to 0.")
            except Exception as e:
                print(f"Warning: Could not get animation length for {animation.strip()}: {e}")
            
            effective_anim_length = float(anim_length) if anim_length is not None else 0.0
            delay_ms = max(2000, int(effective_anim_length * 1000)) if effective_anim_length > 0 else 2000

            self.animation_request_signal.emit(animation, delay_ms)
            
            return "Animation Successful."
        except Exception as e:
            return f"Error preparing animation: {e}"
        
    def return_to_idle(self):
        if hasattr(self.world, 'actor') and self.world.actor:
            if self.is_custom_animation_active:
                self.world.actor.loop('idle')
        self.is_custom_animation_active = False

    def send_from_gui(self):
        text_to_send = self.input_field.text()
        if text_to_send.strip() != "" and (self.jasper_worker is None or not self.jasper_worker.isRunning()):
            self.output_text_edit.append(f">> {text_to_send}")
            self.jasper_worker = JasperWorker(text_to_send, self.jasper)
            self.jasper_worker.info_received.connect(self.handle_jasper_info)
            self.jasper_worker.start()
            self.input_field.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())