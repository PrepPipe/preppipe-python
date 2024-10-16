# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk
from preppipe.language import *
from .fileselection import *
from .languageupdate import *

class CheckableLabelFrame(ttk.LabelFrame):
  def __init__(self, master=None, **kwargs):
    # Extract the 'checkable' keyword argument, defaulting to True
    self._checkable = kwargs.pop('checkable', True)
    # Save the original label text if provided
    self._label_text = kwargs.get('text', '')
    self._label_text_var = kwargs.pop('textvariable', None)
    # Initialize the parent class
    super().__init__(master, **kwargs)

    # Variable to track the checkbutton state
    self._checked_var = tk.BooleanVar(value=True)
    self._checkbutton = None
    self._label = None

    # Create label widget based on 'checkable' property
    if self._checkable:
      self._create_checkbutton_label()
    else:
      self._create_label()

    # Enable or disable child widgets based on the checkbutton state
    self._update_child_state()

  def _prepare_label_args(self):
    result = {}
    if self._label_text_var is not None:
      result["textvariable"] = self._label_text_var
    else:
      result["text"] = self._label_text
    return result

  def _create_checkbutton_label(self):
    # Create a Checkbutton to act as the label
    self._checkbutton = ttk.Checkbutton(
      self, variable=self._checked_var,
      command=self._on_checkbutton_toggle,
      **self._prepare_label_args())
    # Set the labelwidget to the checkbutton
    self['labelwidget'] = self._checkbutton

  def _create_label(self):
    # Create a Label to act as the label
    self._label = ttk.Label(self, **self._prepare_label_args())
    # Set the labelwidget to the label
    self['labelwidget'] = self._label

  def _on_checkbutton_toggle(self):
    # Update the state of child widgets when the checkbutton is toggled
    self._update_child_state()

  def _update_child_state(self):
    # Enable or disable all child widgets based on the checkbutton state
    state = 'normal' if self._checked_var.get() else 'disabled'
    for child in self.winfo_children():
      if child not in (self._checkbutton, self._label):
        try:
          child.configure(state=state)
        except (tk.TclError, AttributeError):
          pass  # Some widgets may not support 'state' option

  @property
  def checkable(self):
    return self._checkable

  @checkable.setter
  def checkable(self, value):
    if self._checkable != value:
      self._checkable = value
      # Remove existing labelwidget
      if 'labelwidget' in self.keys():
        self['labelwidget'] = None
      # Create the appropriate label widget
      if self._checkable:
        self._create_checkbutton_label()
      else:
        self._create_label()

  def get_checked(self):
    return self._checked_var.get()

  def set_checked(self, value):
    self._checked_var.set(value)
    self._update_child_state()

TR_gui_framedecl = TranslationDomain("gui_framedecl")

class _DeclFrameBase(tk.Frame):
  _tr_launch = TR_gui_framedecl.tr("launch",
    en="Launch",
    zh_cn="执行",
    zh_hk="執行",
  )
  data: dict[str, typing.Any]  # Data for member functions in subclasses
  data_watchers: dict[str, list[typing.Callable]]
  _decl_dict: typing.ClassVar[typing.Optional[dict[str, dict[str, typing.Any]]]] = None  # Declaration dict

  def __init__(self, parent):
    super().__init__(parent)
    self.data = {}
    self.data_watchers = {}
    self.widget_dict = {}    # Keep references to widgets
    self.variable_dict = {}  # Keep references to variables (e.g., StringVar, IntVar, etc.)
    self._data_to_label = {}  # For combobox options (data to label mapping)
    self._data_to_tr = {}     # For combobox options (data to Translatable mapping)
    self.setup()

  def data_updated(self, key : str):
    if key in self.data_watchers:
      for cb in self.data_watchers[key]:
        cb()

  def add_data_watcher(self, key : str, cb : typing.Callable):
    if key not in self.data_watchers:
      self.data_watchers[key] = [cb]
    else:
      self.data_watchers[key].append(cb)

  @classmethod
  def get_decl(cls) -> dict[str, dict[str, typing.Any]]:
    raise NotImplementedError()

  def setup(self) -> None:
    if self._decl_dict is None:
      self._decl_dict = self.get_decl()
    self._build_widgets(self._decl_dict, self)

  def _build_widgets(self, decl, parent_widget):
    for key, node in decl.items():
      self._build_widget(key, node, parent_widget)

  def _build_widget(self, key, node, parent_widget, pack_opts=None):
    node_type = node.get('type')
    if node_type == 'combobox':
      self._build_combobox(key, node, parent_widget, pack_opts)
    elif node_type == 'checkbox':
      self._build_checkbox(key, node, parent_widget, pack_opts)
    elif node_type == 'int':
      self._build_int_entry(key, node, parent_widget, pack_opts)
    elif node_type == 'float':
      self._build_float_entry(key, node, parent_widget, pack_opts)
    elif node_type == 'string':
      self._build_string_entry(key, node, parent_widget, pack_opts)
    elif node_type == 'file' or node_type == 'directory':
      self._build_file_widget(key, node, parent_widget, pack_opts)
    elif node_type == 'group':
      self._build_group(key, node, parent_widget, pack_opts)
    elif node_type == 'stack':
      self._build_stack(key, node, parent_widget, pack_opts)
    elif node_type == 'hbox' or node_type == 'buttonbox':
      self._build_box(key, node, parent_widget, horizontal=True, pack_opts=pack_opts)
    elif node_type == 'vbox':
      self._build_box(key, node, parent_widget, horizontal=False, pack_opts=pack_opts)
    elif node_type == 'button':
      self._build_button(key, node, parent_widget, pack_opts)
    else:
      raise ValueError(f"Unknown type '{node_type}' in decl for key '{key}'")

  def _build_combobox(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    options = node.get('options', [])
    default = node.get('default')
    update_callback = node.get('update_callback')
    # Create a Label
    label_var = get_string_var(label_tr)
    label_widget = ttk.Label(parent_widget, textvariable=label_var)
    label_widget.pack(anchor='w')
    # Create a StringVar
    var = tk.StringVar()
    # Map options to display labels
    values = []
    data_to_label = {}
    data_to_tr = {}
    default_index = 0
    for option in options:
      data = option.get('data')
      label_option_tr = option.get('label')
      label_option_var = label_option_tr.get() if isinstance(label_option_tr, Translatable) else label_option_tr
      # Initial values
      if len(values) == 0:
        var.set(label_option_var)
        self.data[key] = data
      if default is not None:
        if default == data:
          default_index = len(values)-1
          var.set(label_option_var)
          self.data[key] = data
      values.append(label_option_var)
      data_to_label[data] = label_option_var
      data_to_tr[data] = label_option_tr if isinstance(label_option_tr, Translatable) else None
    # Create Combobox
    combobox = ttk.Combobox(parent_widget, values=tuple(values), textvariable=var, state='readonly') #
    if pack_opts:
      combobox.pack(**pack_opts)
    else:
      combobox.pack(fill='x', padx=5, pady=2)
    # Define callback function
    def on_combobox_change(*args):
      selected_label = var.get()
      # Find the data corresponding to the selected label
      is_label_found = False
      for data, label in data_to_label.items():
        if label == selected_label:
          self.data[key] = data
          if update_callback:
            update_callback(self, data)
          self.data_updated(key)
          is_label_found = True
          break
      if not is_label_found:
        raise RuntimeError()
    var.trace_add("write", on_combobox_change)
    combobox.current(default_index)
    # Store variable and widget
    self.variable_dict[key] = var
    self.widget_dict[key] = combobox
    # Store data mappings for language updates
    self._data_to_label[key] = data_to_label
    self._data_to_tr[key] = data_to_tr

  def _build_checkbox(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    default = node.get('default', False)
    update_callback = node.get('update_callback')
    var = tk.BooleanVar(value=default)
    checkbox = ttk.Checkbutton(parent_widget, variable=var)
    if label_tr:
      label_var = get_string_var(label_tr)
      checkbox.config(textvariable=label_var)
    if pack_opts:
      checkbox.pack(**pack_opts)
    else:
      checkbox.pack(anchor='w', padx=5, pady=2)
    # Define callback
    def on_checkbox_toggle(*args):
      self.data[key] = var.get()
      if update_callback:
        update_callback(self, var.get())
      self.data_updated(key)
    var.trace_add('write', on_checkbox_toggle)
    # Store variable and widget
    self.variable_dict[key] = var
    self.widget_dict[key] = checkbox
    # Initialize data
    self.data[key] = var.get()

  def _build_int_entry(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    default = node.get('default', 0)
    update_callback = node.get('update_callback')
    # Create a Label
    label_var = get_string_var(label_tr)
    label_widget = ttk.Label(parent_widget, textvariable=label_var)
    label_widget.pack(anchor='w')
    # Create IntVar
    var = tk.IntVar(value=default)
    entry = ttk.Entry(parent_widget, textvariable=var)
    if pack_opts:
      entry.pack(**pack_opts)
    else:
      entry.pack(fill='x', padx=5, pady=2)
    # Define callback
    def on_var_change(*args):
      try:
        value = var.get()
        self.data[key] = value
        if update_callback:
          update_callback(self, value)
        self.data_updated(key)
      except tk.TclError:
        pass  # Invalid int, ignore for now
    var.trace_add('write', on_var_change)
    # Store variable and widget
    self.variable_dict[key] = var
    self.widget_dict[key] = entry
    # Initialize data
    self.data[key] = var.get()

  def _build_float_entry(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    default = node.get('default', 0.0)
    update_callback = node.get('update_callback')
    # Create a Label
    label_var = get_string_var(label_tr)
    label_widget = ttk.Label(parent_widget, textvariable=label_var)
    label_widget.pack(anchor='w')
    # Create DoubleVar
    var = tk.DoubleVar(value=default)
    entry = ttk.Entry(parent_widget, textvariable=var)
    if pack_opts:
      entry.pack(**pack_opts)
    else:
      entry.pack(fill='x', padx=5, pady=2)
    # Define callback
    def on_var_change(*args):
      try:
        value = var.get()
        self.data[key] = value
        if update_callback:
          update_callback(self, value)
        self.data_updated(key)
      except tk.TclError:
        pass  # Invalid float, ignore for now
    var.trace_add('write', on_var_change)
    # Store variable and widget
    self.variable_dict[key] = var
    self.widget_dict[key] = entry
    # Initialize data
    self.data[key] = var.get()

  def _build_string_entry(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    default = node.get('default', '')
    update_callback = node.get('update_callback')
    # Create a Label
    label_var = get_string_var(label_tr)
    label_widget = ttk.Label(parent_widget, textvariable=label_var)
    label_widget.pack(anchor='w')
    # Create StringVar
    var = tk.StringVar(value=default)
    entry = ttk.Entry(parent_widget, textvariable=var)
    if pack_opts:
      entry.pack(**pack_opts)
    else:
      entry.pack(fill='x', padx=5, pady=2)
    # Define callback
    def on_var_change(*args):
      value = var.get()
      self.data[key] = value
      if update_callback:
        update_callback(self, value)
      self.data_updated(key)
    var.trace_add('write', on_var_change)
    # Store variable and widget
    self.variable_dict[key] = var
    self.widget_dict[key] = entry
    # Initialize data
    self.data[key] = var.get()

  def _build_file_widget(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    default = node.get('default', '')
    direction = node.get('direction', 'input')  # 'input' or 'output'
    multiple = node.get('multiple', False)
    isDirectoryMode = node.get('type') == 'directory'
    update_callback = node.get('update_callback')
    # Create a Label
    label_var = get_string_var(label_tr)
    label_widget = ttk.Label(parent_widget, textvariable=label_var)
    label_widget.pack(anchor='w')
    # Create the appropriate widget
    if multiple:
      widget = FileListInputWidget(parent_widget)
      widget.setFieldName(label_tr)
      widget.setDirectoryMode(isDirectoryMode)
      # Add event binding
      def on_list_changed(event):
        value = widget.getCurrentList()
        self.data[key] = value
        if update_callback:
          update_callback(self, value)
        self.data_updated(key)
      widget.bind('<<ListChanged>>', on_list_changed)
      # Initialize data
      self.data[key] = widget.getCurrentList()
    else:
      widget = FileSelectionWidget(parent_widget)
      widget.setFieldName(label_tr)
      widget.setDirectoryMode(isDirectoryMode)
      widget.setIsOutputInsteadofInput(direction == 'output')
      if isinstance(default, Translatable):
        widget.setDefaultName(default)
      # Add event binding
      def on_file_path_updated(event):
        value = widget.getCurrentPath()
        self.data[key] = value
        if update_callback:
          update_callback(self, value)
        self.data_updated(key)
      widget.bind('<<FilePathUpdated>>', on_file_path_updated)
      # Initialize data
      self.data[key] = widget.getCurrentPath()
    if pack_opts:
      widget.pack(**pack_opts)
    else:
      widget.pack(fill='x', padx=5, pady=2)
    # Store widget
    self.widget_dict[key] = widget

  def _build_group(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    checkable = node.get('checkable', False)
    default_checked = node.get('default', True)
    elements = node.get('elements', {})
    # Create CheckableLabelFrame
    label_var = get_string_var(label_tr)
    group_frame = CheckableLabelFrame(parent_widget, checkable=checkable, textvariable=label_var)
    if pack_opts:
      group_frame.pack(**pack_opts)
    else:
      group_frame.pack(fill='x', padx=5, pady=2)
    # Set default checked state
    group_frame.set_checked(default_checked)
    # Process elements
    self._build_widgets(elements, group_frame)
    # If checkable, we need to store the checked state
    if checkable:
      var = group_frame._checked_var  # Get the BooleanVar
      def on_checkbutton_toggle(*args):
        self.data[key] = var.get()
        # No update_callback specified
        self.data_updated(key)
      var.trace_add('write', on_checkbutton_toggle)
      # Initialize data
      self.data[key] = var.get()
      # Store variable
      self.variable_dict[key] = var
    # Store widget
    self.widget_dict[key] = group_frame

  def _build_stack(self, key, node, parent_widget, pack_opts):
    selector = node.get('selector')
    stack_nodes = node.get('stack', {})
    # Create a Frame to hold the stack
    stack_frame = ttk.Frame(parent_widget)
    if pack_opts:
      stack_frame.pack(**pack_opts)
    else:
      stack_frame.pack(fill='x', padx=5, pady=2)
    # Create frames for each stack element
    stack_widgets = {}
    for stack_key, stack_node in stack_nodes.items():
      frame = ttk.Frame(stack_frame)
      # Build the widgets in the frame
      self._build_widgets({stack_key: stack_node}, frame)
      # Store the frame
      stack_widgets[stack_key] = frame
      # Hide the frame initially
      frame.pack_forget()
    # Function to update visible frame based on selector value
    def update_stack():
      selected_value = self.data.get(selector)
      for skey, sframe in stack_widgets.items():
        if skey == selected_value:
          sframe.pack(fill='both', expand=True)
        else:
          sframe.pack_forget()
    # Bind the selector variable to update_stack
    if selector in self.variable_dict:
      self.add_data_watcher(selector, update_stack)
    else:
      # If selector variable not yet created, we need to defer the binding
      raise RuntimeError("selector did not appear before stack")
    # Initialize stack
    update_stack()
    # Store widget
    self.widget_dict[key] = stack_frame

  def _build_box(self, key, node, parent_widget, horizontal=True, pack_opts=None):
    elements = node.get('children', {}) or node.get('elements', {})
    box_frame = ttk.Frame(parent_widget)
    if pack_opts:
      box_frame.pack(**pack_opts)
    else:
      box_frame.pack(fill='x', padx=5, pady=2)
    # Process elements
    if horizontal:
      # For hbox or buttonbox, pack elements side by side
      for elem_key, elem_node in elements.items():
        # We can use a frame to wrap each element
        elem_frame = ttk.Frame(box_frame)
        elem_frame.pack(side='left', padx=2, pady=2)
        self._build_widget(elem_key, elem_node, elem_frame)
    else:
      # For vbox, pack elements top to bottom
      for elem_key, elem_node in elements.items():
        self._build_widget(elem_key, elem_node, box_frame)
    # Store widget
    self.widget_dict[key] = box_frame

  def _build_button(self, key, node, parent_widget, pack_opts):
    label_tr = node.get('label')
    action = node.get('action')
    label_var = get_string_var(label_tr)
    button = ttk.Button(parent_widget, textvariable=label_var)
    if pack_opts:
      button.pack(**pack_opts)
    else:
      button.pack(padx=5, pady=2)
    if action:
      button.config(command=lambda: action(self))
    # Store widget
    self.widget_dict[key] = button

  def set_data(self, key: str, value: typing.Any):
    self.data[key] = value
    # Update the UI
    if key in self.variable_dict:
      var = self.variable_dict[key]
      if isinstance(var, tk.Variable):
        var.set(value)
    # Execute action for value changes when specified
    # We need to check if there is an update_callback for this key
    node = self._find_node_by_key(self._decl_dict, key)
    if node:
      update_callback = node.get('update_callback')
      if update_callback:
        update_callback(self, value)
    self.data_updated(key)

  def _find_node_by_key(self, decl, key):
    for k, node in decl.items():
      if k == key:
        return node
      # Check for nested elements
      if 'elements' in node:
        result = self._find_node_by_key(node['elements'], key)
        if result:
          return result
      if 'children' in node:
        result = self._find_node_by_key(node['children'], key)
        if result:
          return result
      if 'stack' in node:
        for stack_node in node['stack'].values():
          result = self._find_node_by_key(stack_node, key)
          if result:
            return result
    return None




class TestFrame(_DeclFrameBase):
  @staticmethod
  def get_translatable(s : str) -> Translatable:
    # just an example
    raise NotImplementedError()

  @classmethod
  def get_decl(cls) -> dict[str, dict[str, typing.Any]]:
    get_translatable = TestFrame.get_translatable
    return  {
      "combobox_test": {
        "label": get_translatable("Combobox Test"),
        "type": "combobox",
        "options" : [
          {
            "data": "data1",
            "label": get_translatable("Data 1")
          },
          {
            "data": "data2",
            "label": get_translatable("Data 2")
          }
        ],
        "default": "data1",
        "update_callback": TestFrame.value_updated
      },
      "checkbox_test": {
        "label": get_translatable("Checkbox Test"),
        "type": "checkbox"
      },
      "file_test": {
        "label": get_translatable("File Test"),
        "type": "file",
        "direction": "input",
      },
      "file_list_test": {
        "label": get_translatable("File List Test"),
        "type": "file",
        "direction": "input",
        "multiple": True
      },
      "file_output_test": {
        "label": get_translatable("File Output Test"),
        "type": "file",
        "direction": "output"
      },
      "int_test": {
        "label": get_translatable("Int Test"),
        "type": "int"
      },
      "float_test": {
        "label": get_translatable("Float Test"),
        "type": "float"
      },
      "string_test": {
        "label": get_translatable("String Test"),
        "type": "string"
      },
      "button_test": {
        "label": get_translatable("Button Test"),
        "type": "button",
        "action": TestFrame.action_dummy
      }
    }

  def __init__(self, parent):
    super().__init__(parent)
    # TODO update the code
    label = tk.Label(self, text="Test Frame")
    label.pack()

  def value_updated(self, v : typing.Any):
    pass

  def action_dummy(self):
    pass

TR_gui_settings = TranslationDomain("gui_settings")

class SettingsFrame(_DeclFrameBase):
  _tr_language = TR_gui_settings.tr("language",
    en="Language",
    zh_cn="语言",
    zh_hk="語言",
  )
  @classmethod
  def get_decl(cls) -> dict[str, dict[str, typing.Any]]:
    return  {
      "language": {
        "label": cls._tr_language,
        "type": "combobox",
        "options": [
          {
            "data": "en",
            "label": "English"
          },
          {
            "data": "zh_cn",
            "label": "中文（简体）"
          },
          {
            "data": "zh_hk",
            "label": "中文（繁體）"
          }
        ],
        "update_callback": SettingsFrame.language_updated
      }
    }
  def __init__(self, parent):
    super().__init__(parent)

  def language_updated(self, lang):
    set_language(lang)

TR_gui_main_pipeline = TranslationDomain("gui_main_pipeline")

class MainPipelineFrame(_DeclFrameBase):
  _tr_input_settings = TR_gui_main_pipeline.tr("input_settings",
    en="Input Settings",
    zh_cn="输入设置",
    zh_hk="輸入設定"
  )
  _tr_input_scripts = TR_gui_main_pipeline.tr("input_scripts",
    en="Story Scripts",
    zh_cn="剧本",
    zh_hk="劇本",
  )
  _tr_input_assetdir_extra = TR_gui_main_pipeline.tr("input_assetdir_extra",
    en="Extra Asset Directories",
    zh_cn="额外资源目录",
    zh_hk="額外資源目錄"
  )
  _tr_output_settings = TR_gui_main_pipeline.tr("output_settings",
    en="Output Settings",
    zh_cn="输出设置",
    zh_hk="輸出設定"
  )
  _tr_backend = TR_gui_main_pipeline.tr("backend",
    en="Backend",
    zh_cn="后端",
    zh_hk="後端",
  )
  _tr_renpy_settings = TR_gui_main_pipeline.tr("renpy_settings",
    en="Ren'Py Settings",
    zh_cn="Ren'Py 设置",
    zh_hk="Ren'Py 設定"
  )
  _tr_webgal_settings = TR_gui_main_pipeline.tr("webgal_settings",
    en="WebGal Settings",
    zh_cn="WebGal 设置",
    zh_hk="WebGal 設定"
  )
  _tr_output_dir = TR_gui_main_pipeline.tr("output_dir",
    en="Output Directory",
    zh_cn="输出目录",
    zh_hk="輸出目錄"
  )
  _tr_enable_template_dir = TR_gui_main_pipeline.tr("enable_template_dir",
    en="Enable Template Directory",
    zh_cn="启用模板目录",
    zh_hk="啟用模板目錄"
  )
  _tr_template_dir = TR_gui_main_pipeline.tr("template_dir",
    en="Template Directory",
    zh_cn="模板目录",
    zh_hk="模板目錄"
  )
  _tr_misc_settings = TR_gui_main_pipeline.tr("misc_settings",
    en="Other Settings",
    zh_cn="其他设置",
    zh_hk="其他設定",
  ),
  _tr_split_long_say = TR_gui_main_pipeline.tr("split_long_say",
    en="Split longer-than-threshold say statements",
    zh_cn="拆分过长的发言",
    zh_hk="拆分過長的發言",
  )
  _tr_split_long_say_threshold = TR_gui_main_pipeline.tr("split_long_say_threshold",
    en="Length threshold",
    zh_cn="长度阈值",
    zh_hk="長度閾值",
  )
  _tr_split_long_say_target = TR_gui_main_pipeline.tr("split_long_say_target",
    en="Target length",
    zh_cn="目标长度",
    zh_hk="目標長度",
  )
  _tr_split_long_say_note = TR_gui_main_pipeline.tr("split_long_say_note",
    en="Lengths are in unit of half-width (English) characters; each full-width (e.g., Chinese) characters count as two.",
    zh_cn="长度以半角（英文）字符为单位；每个全角字符（例如中文）算两个。",
    zh_hk="長度以半角（英文）字符為單位；每個全角字符（例如中文）算兩個。",
  )
  @classmethod
  def get_decl(cls) -> dict[str, dict[str, typing.Any]]:
    return  {
      "main": {
        "type": "hbox",
        "children": {
          "input_setttings" : {
            "label": cls._tr_input_settings,
            "type": "group",
            "elements": {
              "input_scripts": {
                "label": cls._tr_input_scripts,
                "type": "file",
                "direction": "input",
                "multiple": True
              },
              "input_assetdir_extra": {
                "label": cls._tr_input_assetdir_extra,
                "type": "directory",
                "direction": "input",
                "multiple": True
              }
            }
          },
          "output_settings": {
            "label": cls._tr_output_settings,
            "type": "group",
            "elements": {
              "backend": {
                "label": cls._tr_backend,
                "type": "combobox",
                "options": [
                  {
                    "data": "renpy",
                    "label": "Ren'Py",
                  },
                  {
                    "data": "webgal",
                    "label": "WebGal",
                  }
                ]
              },
              "backend_settings": {
                "type": "stack",
                "selector": "backend",
                "stack": {
                  "renpy": {
                    "label": cls._tr_renpy_settings,
                    "type": "group",
                    "elements": {
                      "renpy_output_dir": {
                        "label": cls._tr_output_dir,
                        "type": "directory",
                        "direction": "output"
                      },
                      "renpy_template_dir_settings": {
                        "label": cls._tr_enable_template_dir,
                        "type": "group",
                        "checkable": True,
                        "default": False,
                        "elements": {
                          "renpy_template_dir": {
                            "label": cls._tr_template_dir,
                            "type": "directory",
                            "direction": "input",
                          }
                        }
                      },
                    }
                  },
                  "webgal": {
                    "label": cls._tr_webgal_settings,
                    "type": "group",
                    "elements": {
                      "webgal_output_dir": {
                        "label": cls._tr_output_dir,
                        "type": "directory",
                        "direction": "output"
                      },
                      "webgal_template_dir_settings": {
                        "label": cls._tr_enable_template_dir,
                        "type": "group",
                        "checkable": True,
                        "default": False,
                        "elements": {
                          "webgal_template_dir": {
                            "label": cls._tr_template_dir,
                            "type": "directory",
                            "direction": "input",
                          }
                      },
                    }
                  }
                }
              },
            }
          },
          "misc_settings": {
            "label": cls._tr_misc_settings,
            "type": "group",
            "elements": {
              "split_long_say": {
                "label": cls._tr_split_long_say,
                "type": "group",
                "checkable": True,
                "default": True,
                "elements": {
                  "split_long_say_threshold": {
                    "label": cls._tr_split_long_say_threshold,
                    "type": "int",
                    "default": 180,
                  },
                  "split_long_say_target": {
                    "label": cls._tr_split_long_say_target,
                    "type": "int",
                    "default": 60,
                  }
                },
              }
            }
          }
        }
      }
    },
    "buttonbox": {
      "type": "buttonbox", # 相当于 hbox，只不过成员应该都是按钮，且按钮应该右对齐
      "elements": {
        "launch": {
          "label": cls._tr_launch,
          "type": "button",
          "action": cls.launch
        }
      }
    }
  }
  def __init__(self, parent):
    super().__init__(parent)

  def launch(self):
    print(str(self.data))
