# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import sys
import os
import PIL
import PIL.Image
import PIL.ImageTk
import preppipe
import preppipe.pipeline_cmd
import preppipe.pipeline
from preppipe.language import *
from .executewindow import *
from .settings import SettingsDict
from .framedecl import *

TR_gui_main = TranslationDomain("gui_main")

tr_output = TR_gui_main.tr("output",
  en="Output",
  zh_cn="输出",
  zh_hk="輸出",
)
tr_test_output = TR_gui_main.tr("test_output",
  en="Test Output",
  zh_cn="测试输出",
  zh_hk="測試輸出",
)

# 用于检测是否已经有一个实例在运行了

_lock_file_path = os.path.join(os.path.expanduser("~"), ".preppipe_gui.lock")

def check_single_instance():
  if sys.platform == 'win32':
    import msvcrt
    try:
      fp = open(_lock_file_path, 'w')
      msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
      return fp
    except IOError:
      return None
  else:
    import fcntl
    try:
      fp = open(_lock_file_path, 'w')
      fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
      return fp
    except IOError:
      return None

def release_lock(fp):
  if sys.platform == 'win32':
    import msvcrt
    msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
  else:
    import fcntl
    fcntl.flock(fp, fcntl.LOCK_UN)
  fp.close()
  os.remove(_lock_file_path)

def get_icon(name : str) -> PIL.Image.Image | None:
  # 获取用于地址栏的方形小图标，如果没有则返回 None （比如如果没有内嵌）
  return None

def get_description_image(name : str) -> PIL.Image.Image | None:
  # 获取用于描述的方形大图标，如果没有则返回 None
  # 这些大图标会显示在 Frame 的中心偏上处，按钮的名称和描述会显示在它的下方
  return None

def to_tk_image(image : PIL.Image.Image | None) -> PIL.ImageTk.PhotoImage | None:
  if image:
    return PIL.ImageTk.PhotoImage(image)
  return None

def open_docs():
  # 打开文档
  print("TODO Opening documentation...")

# 用于 GUI 的配置
# 由于在构建时无法获取图标、无法构建子部件，我们填这些信息时使用 lambda 函数，等到实际运行时再获取
main_window_panels = {
  "main": {
    "icon": lambda : to_tk_image(get_icon("main")),
    "name": TR_gui_executewindow.tr("panel_main_name",
      en="Main Window",
      zh_cn="主界面",
      zh_hk="主界面",
    ),
    "type": "grid",
    "grid_size": (2, 3),
    "content": {
      (0, 0): {
        "id": "frame_docs",
        "image": lambda : to_tk_image(get_description_image("docs")),
        "name": TR_gui_executewindow.tr("cell_docs_name",
          en="Tutorials and Documentations",
          zh_cn="教程、文档",
          zh_hk="教程、文檔",
        ),
        "description": TR_gui_executewindow.tr("cell_docs_description",
          en="Have questions or do not know how to get started?",
          zh_cn="有疑问或是不知怎么上手？",
          zh_hk="有疑問或是不知怎麼上手？",
        ),
        "action": open_docs,
      },
      (0, 1): {
        "id": "frame_pipeline",
        "image": lambda : to_tk_image(get_description_image("pipeline")),
        "name": TR_gui_executewindow.tr("cell_pipeline_name",
          en="Main pipeline",
          zh_cn="主管线",
          zh_hk="主管線",
        ),
        "description": TR_gui_executewindow.tr("cell_pipeline_description",
          en="Story scripts Ready? Convert them here.",
          zh_cn="有剧本吗？要导出工程请点这里。",
          zh_hk="有劇本嗎？要導出工程請點這裡。",
        ),
        "action": MainPipelineFrame,
      },
      (0, 2): {
        "id": "frame_tools",
        "image": lambda : to_tk_image(get_description_image("tools")),
        "name": TR_gui_executewindow.tr("cell_tools_name",
          en="Tools",
          zh_cn="工具",
          zh_hk="工具",
        ),
        "description": TR_gui_executewindow.tr("cell_tools_description",
          en="Here if you want to use sub-tools without the script pipeline.",
          zh_cn="如果只想使用子工具而不是整个剧本处理管线。",
          zh_hk="如果只想使用子工具而不是整個劇本處理管線。",
        ),
        "action": "tools",
      },
      (1, 0): {
        "id": "frame_settings",
        "image": lambda : to_tk_image(get_description_image("settings")),
        "name": TR_gui_executewindow.tr("cell_settings_name",
          en="Settings",
          zh_cn="设置",
          zh_hk="設置",
        ),
        "description": TR_gui_executewindow.tr("cell_settings_description",
          en="Saved in files with the executable.",
          zh_cn="保存在程序所在的文件夹中。",
          zh_hk="保存在程序所在的文件夾中。",
        ),
        "action": SettingsFrame,
      },
      (1, 1): {
        "id": "frame_assets",
        "image": lambda : to_tk_image(get_description_image("assets")),
        "name": TR_gui_executewindow.tr("cell_assets_name",
          en="Assets",
          zh_cn="资源",
          zh_hk="資源",
        ),
        "description": TR_gui_executewindow.tr("cell_assets_description",
          en="Inspect embedded and imported assets here.",
          zh_cn="在此查看内嵌和导入的资源。",
          zh_hk="在此查看內嵌和導入的資源。",
        ),
        "action": None, # TODO
      }
    }
  },
  "tools": {
    "icon": lambda : to_tk_image(get_icon("tools")),
    "name": TR_gui_executewindow.tr("panel_tools_name",
      en="Tools",
      zh_cn="工具",
      zh_hk="工具",
    ),
    "type": "grid",
    "grid_size": (0, 0), # 目前还没做
    "content": {} # 留白
  }
}


# Classes for the main application
class MainApplication(tk.Frame):
  def __init__(self, root):
    super().__init__(root)
    self.root = root
    self.pack(fill='both', expand=True)
    # Initialize the stack of panels
    self.panel_stack: list[dict[str, typing.Any]] = []
    # Initialize panels dictionary
    self.panels: dict[str, dict[str, typing.Any]] = {}
    # Create the address bar
    self.address_bar = tk.Frame(self)
    self.address_bar.pack(side='top', fill='x')
    # Create the main area
    self.main_area = tk.Frame(self)
    self.main_area.pack(side='top', fill='both', expand=True)
    # Start with the main panel
    self.navigate_to_panel('main')

  def navigate_to_panel(self, panel_id: str):
    # Hide current panel
    if len(self.panel_stack) > 0:
      current_panel = self.panel_stack[-1]['frame']
      current_panel.pack_forget()

    # Check if panel is already created
    if panel_id in self.panels:
      panel_info = self.panels[panel_id]
    else:
      panel_data = main_window_panels.get(panel_id)
      if not panel_data:
        return
      panel_type = panel_data.get('type')
      if panel_type == 'grid':
        panel_frame = GridPanel(self.main_area, panel_id, panel_data, self)
      else:
        panel_frame = tk.Frame(self.main_area)  # Placeholder
      # Load icon
      icon_image = None
      if 'icon' in panel_data:
        icon_image = panel_data['icon']()
      panel_info = {
        'panel_id': panel_id,
        'frame': panel_frame,
        'name': panel_data['name'],
        'icon': icon_image
      }
      self.panels[panel_id] = panel_info

    # Add to panel stack
    self.panel_stack.append(panel_info)
    # Update address bar
    self.update_address_bar()
    # Show the panel
    panel_info['frame'].pack(fill='both', expand=True)

  def navigate_to_frame(self, frame: tk.Frame, name: Translatable, icon=None):
    # Hide current panel
    if len(self.panel_stack) > 0:
      current_panel = self.panel_stack[-1]['frame']
      current_panel.pack_forget()
    # Create panel info
    panel_info = {
      'panel_id': None,
      'frame': frame,
      'name': name,
      'icon': icon
    }
    # Add to panel stack
    self.panel_stack.append(panel_info)
    # Update address bar
    self.update_address_bar()
    # Show the frame
    frame.pack(fill='both', expand=True)

  def navigate_back_to(self, index: int):
    # Hide current panel
    if len(self.panel_stack) > 0:
      current_panel = self.panel_stack[-1]['frame']
      current_panel.pack_forget()
    # Remove panels from stack until we reach the desired index
    self.panel_stack = self.panel_stack[:index+1]
    # Show the panel
    current_panel = self.panel_stack[-1]['frame']
    current_panel.pack(fill='both', expand=True)
    # Update address bar
    self.update_address_bar()

  def update_address_bar(self):
    # Clear the address bar
    for widget in self.address_bar.winfo_children():
      widget.destroy()
    for i, panel_info in enumerate(self.panel_stack):
      if i > 0:
        separator = tk.Label(self.address_bar, text='>')
        separator.pack(side='left')
      name_tr = panel_info['name']
      name_var = get_string_var(name_tr)
      if panel_info['icon']:
        icon_image = panel_info['icon']
        button = tk.Button(self.address_bar, textvariable=name_var, image=icon_image, compound='left',
                           command=lambda idx=i: self.navigate_back_to(idx))
        button.image = icon_image  # Keep reference
      else:
        button = tk.Button(self.address_bar, textvariable=name_var, command=lambda idx=i: self.navigate_back_to(idx))
      button.pack(side='left')

class GridPanel(tk.Frame):
  def __init__(self, parent, panel_id, panel_data, app):
    super().__init__(parent)
    self.panel_id = panel_id
    self.panel_data = panel_data
    self.app = app  # Reference to MainApplication
    self.grid_size = panel_data.get('grid_size', (0, 0))
    self.content = panel_data.get('content', {})
    self.cells = {}
    # Build the grid
    for (row, col), cell_data in self.content.items():
      cell = ClickableFrameCell(self, cell_data, self.app)
      cell.grid(row=row, column=col, padx=5, pady=5)
      self.cells[(row, col)] = cell

class ClickableFrameCell(tk.Frame):
  def __init__(self, parent, cell_data, app):
    super().__init__(parent, bd=1, relief='raised')
    self.cell_data = cell_data
    self.app = app
    self.frame = None

    # Set up the UI elements
    image_func = cell_data.get('image')
    image = None
    if image_func:
      image = image_func()
      if image:
        self.image_label = tk.Label(self, image=image)
        self.image_label.image = image  # Keep a reference
        self.image_label.pack()

    name_tr = cell_data.get('name')
    if name_tr:
      name_var = get_string_var(name_tr)
      self.name_label = tk.Label(self, textvariable=name_var, font=('Arial', 14, 'bold'))
      self.name_label.pack()

    description_tr = cell_data.get('description')
    if description_tr:
      description_var = get_string_var(description_tr)
      self.description_label = tk.Label(self, textvariable=description_var, wraplength=200)
      self.description_label.pack()

    # Bind click event
    self.bind("<Button-1>", self.on_click)
    for widget in self.winfo_children():
      widget.bind("<Button-1>", self.on_click)

  def on_click(self, event):
    action = self.cell_data.get('action')
    if action is None:
      return
    elif callable(action):
      if isinstance(action, type) and issubclass(action, tk.Frame):
        # It's a Frame class
        if self.frame is None:
          self.frame = action(self.app.main_area)
        name_tr = self.cell_data.get('name')
        icon = None  # Could load icon if needed
        self.app.navigate_to_frame(self.frame, name_tr, icon)
      else:
        # It's a function
        action()
    elif isinstance(action, str):
      # If action is a string, navigate to that panel
      self.app.navigate_to_panel(action)
    else:
      pass

def _build_gui_root():
  root = tk.Tk()
  app = MainApplication(root)
  return root

def gui_main():
  # 判断是使用 GUI 还是其他工具、管线
  is_gui_specified = False
  is_other_tool_specified = False
  if toolname := os.environ.get("PREPPIPE_TOOL"):
    if len(toolname) > 0:
      if toolname == "gui":
        is_gui_specified = True
      else:
        is_other_tool_specified = True
  if is_gui_specified or is_other_tool_specified:
    is_gui = is_gui_specified
  else:
    is_gui = len(sys.argv) == 1

  if not is_gui:
    preppipe.pipeline.pipeline_main()
    return

  lock_fp = check_single_instance()
  if lock_fp is None:
    # 已经有另一个实例在运行了
    sys.exit(0)
  try:
    root = _build_gui_root()
    root.mainloop()
  finally:
    release_lock(lock_fp)
    SettingsDict.finalize()

if __name__ == '__main__':
  gui_main()
