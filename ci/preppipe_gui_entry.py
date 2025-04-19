import os
import preppipe_gui_pyside6
import preppipe_gui_pyside6.main

if __name__ == '__main__':
  preppipe_gui_pyside6.main.gui_main(settings_path=os.path.dirname(__file__))
