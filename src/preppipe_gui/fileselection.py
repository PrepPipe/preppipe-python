# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import typing
import tkinter as tk
from tkinter import filedialog
from preppipe.language import *
from .languageupdate import *

TR_gui_fileselection = TranslationDomain("gui_fileselection")

class _FileSelectionBaseWidget(tk.Frame):
  _tr_select = TR_gui_fileselection.tr("select",
    en="Select",
    zh_cn="选择",
    zh_hk="選取"
  )
  _tr_file_not_selected = TR_gui_fileselection.tr("file_not_selected",
    en="(Not selected)",
    zh_cn="(未选择)",
    zh_hk="(未選取)"
  )
  _tr_file_select_fialog_title = TR_gui_fileselection.tr("file_select_fialog_title",
    en="Please select: {fieldname}",
    zh_cn="请选择：{fieldname}",
    zh_hk="請選取：{fieldname}"
  )
  _tr_all_files = TR_gui_fileselection.tr("all_files",
    en="All Files",
    zh_cn="所有文件",
    zh_hk="所有檔案",
  )

  isDirectoryMode : bool
  fieldName : typing.Optional[Translatable]
  filter : typing.Optional[Translatable]
  verifyCB : typing.Optional[typing.Callable[[str], bool]]

  def __init__(self, master=None):
    super().__init__(master)
    self.isDirectoryMode = False
    self.fieldName = None
    self.filter = None
    self.verifyCB = None

  @staticmethod
  def getDefaultVerifier(isDirectoryMode: bool) -> typing.Callable[[str], bool]:
    if isDirectoryMode:
      return _FileSelectionBaseWidget.defaultDirectoryChecker
    else:
      return _FileSelectionBaseWidget.defaultFileChecker

  @staticmethod
  def defaultFileChecker(path: str) -> bool:
    return os.path.isfile(path)

  @staticmethod
  def defaultDirectoryChecker(path: str) -> bool:
    return os.path.isdir(path)

  def setDirectoryMode(self, v: bool):
    self.isDirectoryMode = v
    if self.isDirectoryMode and self.verifyCB is None:
      self.verifyCB = self.getDefaultVerifier(True)
    else:
      self.verifyCB = self.getDefaultVerifier(False)

  def getIsDirectoryMode(self) -> bool:
    return self.isDirectoryMode

  def setVerifyCallBack(self, cb: typing.Callable[[str], bool]):
    self.verifyCB = cb

  def field_name_updated(self):
    pass

  def setFieldName(self, name: Translatable):
    self.fieldName = name
    self.field_name_updated()

  def getFieldName(self) -> Translatable | None:
    return self.fieldName

  def setFilter(self, filter: Translatable):
    self.filter = filter

  def getFilter(self) -> Translatable | None:
    return self.filter

  def open_dialog_for_path_input(self, default_path : str | None, default_name : str | None, isOutputInsteadofInput : bool = False) -> str | None:
    dialogTitle = self._tr_file_select_fialog_title.format(fieldname=(self.fieldName.get() if self.fieldName else ''))
    initialdir = os.path.dirname(default_path) if default_path else None
    initialfile = os.path.basename(default_path) if default_path else default_name

    if self.isDirectoryMode:
      # No direct way to select a non-existing directory
      selected_dir = filedialog.askdirectory(title=dialogTitle, initialdir=initialdir)
      if selected_dir:
        if self.verifyCB is None or self.verifyCB(selected_dir):
          return selected_dir
    else:
      if isOutputInsteadofInput:
        selected_file = filedialog.asksaveasfilename(title=dialogTitle, initialdir=initialdir,
                                                     initialfile=initialfile, filetypes=self.getFiletypes())
        if selected_file:
          if self.verifyCB is None or self.verifyCB(selected_file):
            return selected_file
      else:
        selected_file = filedialog.askopenfilename(title=dialogTitle, initialdir=initialdir,
                                                    filetypes=self.getFiletypes())
        if selected_file:
          if self.verifyCB is None or self.verifyCB(selected_file):
            return selected_file

  def getFiletypes(self):
    # Convert self.filter to tkinter's filetypes format
    # Qt uses a filter string like "All Files (*);;Text Files (*.txt)"
    # Tkinter expects a list of (label, pattern) tuples, e.g., [("All Files", "*"), ("Text Files", "*.txt")]
    # So we need to parse self.filter accordingly
    filetypes = []
    if self.filter:
      # Split by ';;'
      filters = self.filter.get().split(';;')
      for f in filters:
        # Split label and patterns
        if '(' in f and ')' in f:
          label, patterns = f.strip().split('(', 1)
          label = label.strip()
          patterns = patterns.rstrip(')').strip()
          # patterns can be multiple patterns separated by spaces, e.g., '*.txt *.md'
          patterns_list = patterns.split()
          patterns_str = ' '.join(patterns_list)
          filetypes.append((label, patterns_str))
        else:
          # If no patterns specified
          pass
    else:
      filetypes = [(self._tr_all_files.get(), "*")]
    return filetypes

class FileSelectionWidget(_FileSelectionBaseWidget):
  isOutputInsteadofInput : bool
  currentPath : str
  defaultName : typing.Optional[Translatable]

  def __init__(self, master=None):
    super().__init__(master)
    self.isOutputInsteadofInput = False
    self.currentPath = ''
    self.defaultName = None

    # Create the UI elements
    self.pathLabel = tk.Label(self, textvariable=get_string_var(self._tr_file_not_selected), bd=1, relief='sunken', anchor='w')
    self.selectButton = tk.Button(self, textvariable=get_string_var(self._tr_select), command=self.requestOpenDialog)

    # Layout
    self.pathLabel.pack(side='left', fill='x', expand=True)
    self.selectButton.pack(side='right')

    # Update the label text
    self.updateLabelText()

  def setIsOutputInsteadofInput(self, v: bool):
    self.isOutputInsteadofInput = v

  def getIsOutputInsteadofInput(self) -> bool:
    return self.isOutputInsteadofInput

  def field_name_updated(self):
    self.updateLabelText()

  def getCurrentPath(self) -> str:
    return self.currentPath

  def setDefaultName(self, name: Translatable):
    self.defaultName = name

  def getDefaultName(self) -> Translatable | None:
    return self.defaultName

  def setCurrentPath(self, newpath: str):
    self.currentPath = newpath
    self.updateLabelText()
    self.event_generate('<<FilePathUpdated>>')

  def updateLabelText(self):
    if len(self.currentPath) == 0:
      self.pathLabel.config(textvariable=get_string_var_alt(self, lambda: (self.fieldName.get() + ': ' if self.fieldName else '') + self._tr_file_not_selected.get()))
    else:
      self.pathLabel.config(text=self.currentPath)

  def requestOpenDialog(self):
    if path := self.open_dialog_for_path_input(self.currentPath, self.defaultName.get() if self.defaultName else '', self.isOutputInsteadofInput):
      self.setCurrentPath(path)

class FileListInputWidget(_FileSelectionBaseWidget):
  _tr_add = TR_gui_fileselection.tr("filelist_add",
    en="Add",
    zh_cn="添加",
    zh_hk="添加"
  )
  _tr_remove = TR_gui_fileselection.tr("filelist_remove",
    en="Remove",
    zh_cn="删除",
    zh_hk="删除"
  )
  _tr_up = TR_gui_fileselection.tr("filelist_up",
    en="Up",
    zh_cn="上移",
    zh_hk="上移"
  )
  _tr_down = TR_gui_fileselection.tr("filelist_down",
    en="Down",
    zh_cn="下移",
    zh_hk="下移"
  )
  lastAddedPath : str
  def __init__(self, master=None):
    super().__init__(master)
    self.lastAddedPath = ''

    # Build the UI
    self.setup_ui()

    # Set up drag and drop (optional)
    # Implement drag-and-drop if desired

  def setup_ui(self):
    # Create the label and buttons in a horizontal frame
    h_frame = tk.Frame(self)
    h_frame.pack(fill='x')

    # Label
    self.label = tk.Label(h_frame, text='')
    self.label.pack(side='left', fill='x', expand=True)

    # Add button
    self.addButton = tk.Button(h_frame, textvariable=get_string_var(self._tr_add), command=self.itemAdd)
    self.addButton.pack(side='left')

    # Remove button
    self.removeButton = tk.Button(h_frame, textvariable=get_string_var(self._tr_remove), command=self.itemRemove)
    self.removeButton.pack(side='left')
    self.removeButton.config(state='disabled')  # Initially disabled

    # Move Up button
    self.moveUpButton = tk.Button(h_frame, textvariable=get_string_var(self._tr_up), command=self.itemMoveUp)
    self.moveUpButton.pack(side='left')
    self.moveUpButton.config(state='disabled')  # Initially disabled

    # Move Down button
    self.moveDownButton = tk.Button(h_frame, textvariable=get_string_var(self._tr_down), command=self.itemMoveDown)
    self.moveDownButton.pack(side='left')
    self.moveDownButton.config(state='disabled')  # Initially disabled

    # Listbox
    self.listWidget = tk.Listbox(self, selectmode='browse')
    self.listWidget.pack(fill='both', expand=True)

    # Bindings
    # Bind listWidget selection to update buttons
    self.listWidget.bind('<<ListboxSelect>>', self.on_listbox_select)


  def field_name_updated(self):
    if self.fieldName:
      self.label.config(textvariable=get_string_var(self.fieldName))
    else:
      self.label.config(text='')

  def getCurrentList(self) -> list[str]:
    return list(self.listWidget.get(0, tk.END))

  def on_listbox_select(self, event):
    selection = self.listWidget.curselection()
    if selection:
      self.removeButton.config(state='normal')
      index = selection[0]
      # Enable moveUpButton if not at the top
      if index > 0:
        self.moveUpButton.config(state='normal')
      else:
        self.moveUpButton.config(state='disabled')
      # Enable moveDownButton if not at the bottom
      if index < self.listWidget.size() - 1:
        self.moveDownButton.config(state='normal')
      else:
        self.moveDownButton.config(state='disabled')
    else:
      self.removeButton.config(state='disabled')
      self.moveUpButton.config(state='disabled')
      self.moveDownButton.config(state='disabled')

  def itemAdd(self):
    if path := self.open_dialog_for_path_input(self.lastAddedPath, None):
      self.addPath(path)

  def itemRemove(self):
    selection = self.listWidget.curselection()
    if selection:
      index = selection[0]
      self.listWidget.delete(index)
      self.event_generate('<<ListChanged>>')
      # Update buttons
      self.on_listbox_select(None)

  def itemMoveUp(self):
    selection = self.listWidget.curselection()
    if selection:
      index = selection[0]
      if index > 0:
        # Swap with the item above
        above_text = self.listWidget.get(index - 1)
        current_text = self.listWidget.get(index)
        self.listWidget.delete(index - 1, index)
        self.listWidget.insert(index - 1, current_text)
        self.listWidget.insert(index, above_text)
        # Update selection
        self.listWidget.selection_set(index - 1)
        self.event_generate('<<ListChanged>>')
        # Update buttons
        self.on_listbox_select(None)

  def itemMoveDown(self):
    selection = self.listWidget.curselection()
    if selection:
      index = selection[0]
      if index < self.listWidget.size() - 1:
        # Swap with the item below
        below_text = self.listWidget.get(index + 1)
        current_text = self.listWidget.get(index)
        self.listWidget.delete(index, index + 1)
        self.listWidget.insert(index, below_text)
        self.listWidget.insert(index + 1, current_text)
        # Update selection
        self.listWidget.selection_set(index + 1)
        self.event_generate('<<ListChanged>>')
        # Update buttons
        self.on_listbox_select(None)

  def addPath(self, path: str):
    # Check if path is already in the list
    existing_paths = self.listWidget.get(0, tk.END)
    if path in existing_paths:
      return
    # Add the path to the list
    self.listWidget.insert(tk.END, path)
    self.lastAddedPath = path
    self.event_generate('<<ListChanged>>')
