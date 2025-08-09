from direct.showbase.ShowBase import ShowBase

from direct.task import Task
import math

class MyApp(ShowBase):
    def __init__(self):
        super().__init__()

        self.model = self.loader.loadModel("models/eric-rigged-001-rigged-3d-business-man/source/rp_eric_rigged_001_yup_a.fbx")
        tex = self.loader.loadTexture("models/eric-rigged-001-rigged-3d-business-man/textures/rp_eric_rigged_001_dif.jpeg")
        self.model.setTexture(tex)
        self.model.reparentTo(self.render)

        joint = self.model.find("**/upperleg_l")
        if joint.isEmpty():
            print("Joint not found!")
        else:
            joint.setHpr(30, 0, 0)



        self.model.ls()



app = MyApp()
app.run()
