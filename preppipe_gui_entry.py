import os
import preppipe_gui
import preppipe_gui.main

if __name__ == '__main__':
  preppipe_gui.main.gui_main(settings_path=os.path.dirname(__file__))
