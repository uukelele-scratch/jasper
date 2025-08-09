from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from panda3d.core import DirectionalLight, AmbientLight, loadPrcFileData, TextNode
from direct.gui.DirectGui import DirectEntry, DirectButton, DirectLabel

import threading
import queue

from actions import Jasper, client


loadPrcFileData("", "load-file-type gltf panda3d_gltf.core:GltfLoader")
loadPrcFileData("", "model-cache-dir /dev/null")

class MyApp(ShowBase):
    def __init__(self):
        super().__init__()
        
        self.setBackgroundColor(0.5, 0.5, 0.5)
        self.disableMouse()

        model_path = "models/animations/eric-rigged-001-rigged-3d-business-man.glb"
        
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
            "searching":           "models/animations/Rummaging.glb"
        }

        
        self.actor = Actor(model_path, animations_to_load)
        self.actor.reparent_to(self.render)
        self.actor.setPos(0, 0, 0)

        self.floor = self.loader.loadModel("models/environment")
        self.floor.reparentTo(self.render)        
        self.floor.setScale(100, 100, 1)
        self.floor.setPos(0, 0, 0)

        self.camera.setPos(0, -4, 1)
        self.camera.setHpr(0, 0, 0)


        self.jasper_queue = queue.Queue()
        self.jasper = Jasper(client, callback=self.jasper_callback)
        self.taskMgr.add(self.check_jasper_queue, "checkJasperQueueTask")

        self.input_field = DirectEntry(
            text="",
            scale=0.05,
            pos=(-0.8, 0, -0.9), # Position on screen
            width=25,
            initialText="Type your message...",
            numLines=1,
            focus=1, # Start with the cursor active here
            command=self.send_from_gui # Function to call on Enter key
        )
        
        # Create a "Send" button
        self.send_button = DirectButton(
            text="Send",
            scale=0.05,
            pos=(0.6, 0, -0.9),
            command=self.send_from_gui # Function to call on click
        )
        
        # Create a label to display Jasper's output messages
        self.output_label = DirectLabel(
            text="Jasper is waiting.",
            scale=0.06,
            pos=(0, 0, 0.8),
            text_align=TextNode.ACenter,
            frameColor=(0, 0, 0, 0.2), # Semi-transparent background
            text_wordwrap=25
        )
        
        self.actor.loop("idle")

    def send_from_gui(self, text_to_send=None):
        # The text_to_send argument is automatically passed when Enter is pressed.
        # We get it directly from the widget if the button was pressed.
        if text_to_send is None:
            text_to_send = self.input_field.get()
            
        if text_to_send.strip() != "":
            # Call our existing, non-blocking function!
            self.send_message_in_thread(text_to_send)
            # Clear the input field for the next message
            self.input_field.set("")
            self.input_field['initialText'] = ''

    def jasper_callback(self, info: dict):
        self.jasper_queue.put(info)

    def check_jasper_queue(self, task):
        # Process all messages currently in the queue.
        while not self.jasper_queue.empty():
            try:
                info = self.jasper_queue.get_nowait()
                # Now that we are in the main thread, it is SAFE to handle the data.
                self.handle_jasper_info(info)
            except queue.Empty:
                # This can happen in rare cases, just ignore it.
                break
        
        return task.cont # Continue this task every frame
    
    def handle_jasper_info(self, info: dict):
        if info.get("message"):
            print(f"Jasper Message: {info['message']}")
            self.output_label['text'] = info['message']
        
        if info.get("state"):
            print(f"Changing state to: {info['state']}")
            self.actor.loop(info["state"])

    def send_message_in_thread(self, message: str):
        print(f"Starting worker thread to send message: '{message}'")
        self.output_label['text'] = "..." # Show user we are thinking
        thread = threading.Thread(target=self.jasper.send_message, args=(message,))
        thread.start()


app = MyApp()
app.run()