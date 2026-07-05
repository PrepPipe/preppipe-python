# -*- coding: utf-8 -*-
"""脚本流程编辑器工具：嵌入 NodeGraphQt-PySide6，与 ScriptFlowEditor 数据模型双向同步。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsProxyWidget,
    QHBoxLayout,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from NodeGraphQt import BaseNode, NodeGraph
from NodeGraphQt.qgraphics.pipe import PipeItem

from ScriptFlowEditor.models import (
    FlagType,
    FlagVariable,
    GameScriptFlow,
    SegmentPath,
    StorySegment,
)

from preppipe.language import TranslationDomain

from ..mainwindowinterface import MainWindowInterface
from ..toolwidgetinterface import ToolWidgetInterface, ToolWidgetInfo, ToolWidgetUniqueLevel

# 节点类型标识
_SEGMENT_NODE_TYPE = "preppipe.scriptflow.SegmentNode"
_FLAG_NODE_TYPE = "preppipe.scriptflow.FlagNode"

TR_gui_scriptfloweditor = TranslationDomain("gui_scriptfloweditor")


class SegmentContentEditDialog(QDialog):
    """编辑剧情段落正文的对话框，关闭时若接受则把文本写入对应 StorySegment.content。"""

    def __init__(
        self,
        parent: QWidget | None,
        segment: StorySegment,
        *,
        title: str = "",
        placeholder: str = "",
    ):
        super().__init__(parent)
        self._segment = segment
        self.setWindowTitle(title or ("Edit Segment Content" if not parent else parent.tr("编辑剧情文本")))
        layout = QVBoxLayout(self)
        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setPlaceholderText(placeholder or ("Enter segment content…" if not parent else parent.tr("在此输入该段落的剧情文本…")))
        self._text_edit.setPlainText(segment.content or "")
        layout.addWidget(self._text_edit)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def accept(self) -> None:
        self._segment.content = self._text_edit.toPlainText()
        super().accept()


class SegmentCommentEditDialog(QDialog):
    """编辑剧情段落注释的对话框，关闭时若接受则把文本写入对应 StorySegment.comment。"""

    def __init__(
        self,
        parent: QWidget | None,
        segment: StorySegment,
        *,
        title: str = "",
        placeholder: str = "",
    ):
        super().__init__(parent)
        self._segment = segment
        self.setWindowTitle(title or "Edit Comment")
        layout = QVBoxLayout(self)
        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setPlaceholderText(placeholder or "Enter comment…")
        self._text_edit.setPlainText(segment.comment or "")
        layout.addWidget(self._text_edit)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def accept(self) -> None:
        self._segment.comment = self._text_edit.toPlainText()
        super().accept()


class PathConditionEditDialog(QDialog):
    """编辑连线分支条件的对话框，关闭时若接受则把文本写入对应 SegmentPath.condition_expression。"""

    def __init__(
        self,
        parent: QWidget | None,
        segment_path: SegmentPath,
        *,
        title: str = "",
        placeholder: str = "",
    ):
        super().__init__(parent)
        self._path = segment_path
        self.setWindowTitle(title or "Edit Branch Condition")
        layout = QVBoxLayout(self)
        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setPlaceholderText(placeholder or "Enter condition expression…")
        self._text_edit.setPlainText(segment_path.condition_expression or "")
        layout.addWidget(self._text_edit)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def accept(self) -> None:
        self._path.condition_expression = self._text_edit.toPlainText()
        super().accept()


class FlagCommentEditDialog(QDialog):
    """编辑 Flag 变量注释的对话框，关闭时若接受则把文本写入对应 FlagVariable.comment。"""

    def __init__(
        self,
        parent: QWidget | None,
        flag_var: FlagVariable,
        *,
        title: str = "",
        placeholder: str = "",
    ):
        super().__init__(parent)
        self._flag_var = flag_var
        self.setWindowTitle(title or "Edit Comment")
        layout = QVBoxLayout(self)
        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setPlaceholderText(placeholder or "Enter comment…")
        self._text_edit.setPlainText(flag_var.comment or "")
        layout.addWidget(self._text_edit)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def accept(self) -> None:
        self._flag_var.comment = self._text_edit.toPlainText()
        super().accept()


class FlagInitialValueEditDialog(QDialog):
    """编辑 Flag 变量初始值的对话框，根据 flag_type 显示布尔单选/整数/浮点数输入。"""

    def __init__(
        self,
        parent: QWidget | None,
        flag_var: FlagVariable,
        *,
        title: str = "",
    ):
        super().__init__(parent)
        self._flag_var = flag_var
        self.setWindowTitle(title or "Edit Flag Initial Value")
        layout = QFormLayout(self)
        if flag_var.flag_type == FlagType.BOOL:
            group = QButtonGroup(self)
            self._radio_true = QRadioButton("True", self)
            self._radio_false = QRadioButton("False", self)
            group.addButton(self._radio_true)
            group.addButton(self._radio_false)
            self._radio_true.setChecked(bool(flag_var.initial_value))
            self._radio_false.setChecked(not bool(flag_var.initial_value))
            bool_row = QWidget(self)
            bool_layout = QHBoxLayout(bool_row)
            bool_layout.setContentsMargins(0, 0, 0, 0)
            bool_layout.addWidget(self._radio_true)
            bool_layout.addWidget(self._radio_false)
            self._widget = bool_row
        elif flag_var.flag_type == FlagType.INT:
            self._widget = QSpinBox(self)
            self._widget.setRange(-(2**31), 2**31 - 1)
            self._widget.setValue(int(flag_var.initial_value))
        else:
            self._widget = QDoubleSpinBox(self)
            self._widget.setDecimals(6)
            self._widget.setRange(-1e308, 1e308)
            self._widget.setValue(float(flag_var.initial_value))
        layout.addRow(self._widget)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def accept(self) -> None:
        w = self._widget
        if self._flag_var.flag_type == FlagType.BOOL:
            self._flag_var.initial_value = self._radio_true.isChecked()
        elif self._flag_var.flag_type == FlagType.INT:
            self._flag_var.initial_value = w.value()
        else:
            self._flag_var.initial_value = w.value()
        super().accept()


class SegmentNode(BaseNode):
    """剧情段落节点：一个输入、一个输出，对应数据层 StorySegment。"""
    __identifier__ = "preppipe.scriptflow"
    NODE_NAME = "Segment"

    def __init__(self):
        super().__init__()
        self.add_input("in", multi_input=True, display_name=True)
        self.add_output("out", display_name=True)


class FlagNode(BaseNode):
    """Flag 节点：无端口、不允许连线，对应数据层 FlagVariable；中间显示 initial_value。"""
    __identifier__ = "preppipe.scriptflow"
    NODE_NAME = "Flag"

    def __init__(self):
        super().__init__()
        # 不添加 input/output，节点不可连线
        self.add_text_input("initial_value_display", label="", text="—")
        w = self.get_widget("initial_value_display")
        le = w.get_custom_widget()
        le.setReadOnly(True)
        le.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 避免关闭对话框后弹出 QLineEdit 默认菜单（Select All 等）
        QGraphicsProxyWidget.setToolTip(w, "")  # 禁用显示初始值的控件的 tooltip（避免库默认加属性名）


class ScriptFlowEditorWidget(QWidget, ToolWidgetInterface):
    """脚本流程编辑器 Tab：内嵌节点图，与 GameScriptFlow 数据层双向同步。"""

    # 多语言：与 setting、home 等一致，使用 TranslationDomain + bind_text，语言切换时由 update_text 更新
    # _tr_add_node = TR_gui_scriptfloweditor.tr("add_node", en="Add Node", zh_cn="添加节点", zh_hk="添加節點")
    _tr_add_script_node = TR_gui_scriptfloweditor.tr("add_script_node", en="Add Script Node", zh_cn="增加剧情节点", zh_hk="增加劇情節點")
    _tr_add_flag = TR_gui_scriptfloweditor.tr("add_flag_variable", en="Add Flag Variable", zh_cn="添加Flag变量", zh_hk="添加Flag變量")
    # _tr_btn_add_flag = TR_gui_scriptfloweditor.tr("btn_add_flag", en="Add Flag", zh_cn="添加Flag", zh_hk="添加Flag")
    _tr_btn_add_flag_tooltip = TR_gui_scriptfloweditor.tr("btn_add_flag_tooltip", en="Add a flag variable node.", zh_cn="添加一个 Flag 变量节点", zh_hk="添加一個 Flag 變量節點")
    _tr_edit_segment_content = TR_gui_scriptfloweditor.tr("edit_segment_content", en="Edit Segment Content", zh_cn="编辑剧情文本", zh_hk="編輯劇情文本")
    _tr_edit_comment = TR_gui_scriptfloweditor.tr("edit_comment", en="Edit Comment", zh_cn="编辑注释", zh_hk="編輯註釋")
    _tr_edit_dialog_title = TR_gui_scriptfloweditor.tr("edit_dialog_title", en="Edit Segment Content", zh_cn="编辑剧情文本", zh_hk="編輯劇情文本")
    _tr_edit_comment_dialog_title = TR_gui_scriptfloweditor.tr("edit_comment_dialog_title", en="Edit Comment", zh_cn="编辑注释", zh_hk="編輯註釋")
    _tr_edit_comment_dialog_placeholder = TR_gui_scriptfloweditor.tr("edit_comment_dialog_placeholder", en="Enter comment for this node…", zh_cn="在此输入该节点的注释…", zh_hk="在此輸入該節點的註釋…")
    _tr_edit_dialog_placeholder = TR_gui_scriptfloweditor.tr("edit_dialog_placeholder", en="Enter the segment story text here…", zh_cn="在此输入该段落的剧情文本…", zh_hk="在此輸入該段落的劇情文本…")
    # _tr_btn_add = TR_gui_scriptfloweditor.tr("btn_add", en="Add Segment Node", zh_cn="增加剧情节点", zh_hk="增加劇情節點")
    _tr_btn_add_tooltip = TR_gui_scriptfloweditor.tr("btn_add_tooltip", en="Add a new segment node at the top-left of the view.", zh_cn="当前视图左上角新增一个剧情节点", zh_hk="當前視圖左上角新增一個劇情節點")
    _tr_btn_del = TR_gui_scriptfloweditor.tr("btn_del", en="Delete Selected", zh_cn="删除选中节点", zh_hk="刪除選中節點")
    _tr_btn_del_tooltip = TR_gui_scriptfloweditor.tr("btn_del_tooltip", en="Delete the selected nodes.", zh_cn="删除当前选中节点", zh_hk="刪除當前選中節點")
    _tr_chk_acyclic = TR_gui_scriptfloweditor.tr("chk_acyclic", en="Acyclic", zh_cn="无环模式", zh_hk="無環模式")
    _tr_chk_acyclic_tooltip = TR_gui_scriptfloweditor.tr("chk_acyclic_tooltip", en="When checked, cycles are not allowed.", zh_cn="勾选后，禁止创建闭环连接", zh_hk="勾選後，禁止創建閉環連接")
    _tr_save_flow = TR_gui_scriptfloweditor.tr("save_flow", en="Save Flow", zh_cn="保存流程", zh_hk="保存流程")
    _tr_save_tooltip = TR_gui_scriptfloweditor.tr("save_tooltip", en="Save current flow and node positions to a JSON file.", zh_cn="将当前流程与节点位置保存为 JSON 文件", zh_hk="將當前流程與節點位置保存為 JSON 文件")
    _tr_load_flow = TR_gui_scriptfloweditor.tr("load_flow", en="Load Flow", zh_cn="打开流程", zh_hk="打開流程")
    _tr_open_tooltip = TR_gui_scriptfloweditor.tr("open_tooltip", en="Load flow and node positions from a JSON file.", zh_cn="从 JSON 文件加载流程与节点位置", zh_hk="從 JSON 文件加載流程與節點位置")
    _tr_save_dialog_title = TR_gui_scriptfloweditor.tr("save_dialog_title", en="Save Flow", zh_cn="保存流程", zh_hk="保存流程")
    _tr_open_dialog_title = TR_gui_scriptfloweditor.tr("open_dialog_title", en="Open Flow", zh_cn="打开流程", zh_hk="打開流程")
    _tr_json_filter = TR_gui_scriptfloweditor.tr("json_filter", en="JSON files (*.json);;All files (*)", zh_cn="JSON 文件 (*.json);;所有文件 (*)", zh_hk="JSON 文件 (*.json);;所有文件 (*)")

    _tr_node_tooltip_ending = TR_gui_scriptfloweditor.tr("node_tooltip_ending", en="Ending segment.", zh_cn="剧本结局节点", zh_hk="劇本結局節點")
    _tr_node_tooltip_start = TR_gui_scriptfloweditor.tr("node_tooltip_start", en="Start segment.", zh_cn="剧本起始节点", zh_hk="劇本起始節點")
    _tr_node_tooltip_default = TR_gui_scriptfloweditor.tr("node_tooltip_default", en="Segment node.", zh_cn="新剧情段落节点", zh_hk="新劇情段落節點")
    _tr_node_tooltip_flag_default = TR_gui_scriptfloweditor.tr("node_tooltip_flag_default", en="Flag variable node.", zh_cn="Flag 变量节点", zh_hk="Flag 變量節點")
    _tr_node_name_edit_tooltip = TR_gui_scriptfloweditor.tr("node_name_edit_tooltip", en="Double-click to edit node name.", zh_cn="双击编辑节点名称", zh_hk="雙擊編輯節點名稱")

    _tr_flag_change_type = TR_gui_scriptfloweditor.tr("flag_change_type", en="Change Flag Type", zh_cn="修改flag变量类型", zh_hk="修改flag變量類型")
    _tr_flag_type_bool = TR_gui_scriptfloweditor.tr("flag_type_bool", en="Boolean", zh_cn="布尔型", zh_hk="布爾型")
    _tr_flag_type_int = TR_gui_scriptfloweditor.tr("flag_type_int", en="Integer", zh_cn="整型", zh_hk="整型")
    _tr_flag_type_float = TR_gui_scriptfloweditor.tr("flag_type_float", en="Float", zh_cn="浮点型", zh_hk="浮點型")
    _tr_flag_change_initial = TR_gui_scriptfloweditor.tr("flag_change_initial", en="Change Flag Initial Value", zh_cn="修改flag初始值", zh_hk="修改flag初始值")
    _tr_flag_initial_dialog_title = TR_gui_scriptfloweditor.tr("flag_initial_dialog_title", en="Edit Flag Initial Value", zh_cn="修改flag初始值", zh_hk="修改flag初始值")

    _tr_edit_branch_condition = TR_gui_scriptfloweditor.tr("edit_branch_condition", en="Edit Branch Condition", zh_cn="编辑分支条件", zh_hk="編輯分支條件")
    _tr_edit_branch_condition_dialog_title = TR_gui_scriptfloweditor.tr("edit_branch_condition_dialog_title", en="Edit Branch Condition", zh_cn="编辑分支条件", zh_hk="編輯分支條件")
    _tr_edit_branch_condition_placeholder = TR_gui_scriptfloweditor.tr("edit_branch_condition_placeholder", en="Enter condition expression for this path…", zh_cn="在此输入该连线的条件表达式…", zh_hk="在此輸入該連線的條件表達式…")

    _tr_toolname = MainWindowInterface.tr_toolname_scriptflow_editor

    @classmethod
    def getToolInfo(cls) -> ToolWidgetInfo:
        return ToolWidgetInfo(
            idstr="scriptflow_editor",
            name=ScriptFlowEditorWidget._tr_toolname,
            widget=cls,
            uniquelevel=ToolWidgetUniqueLevel.SINGLE_INSTANCE,
        )

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self._graph = NodeGraph(parent=self)
        self._graph.register_node(SegmentNode)
        self._graph.register_node(FlagNode)
        self._graph.set_acyclic(True)

        # 数据层：与节点视图一一对应
        self._flow = GameScriptFlow(name="ScriptFlow")
        self._node_id_to_segment_id: dict[str, str] = {}
        self._node_id_to_flag_id: dict[str, str] = {}
        # 为 True 时表示正在根据 flow 构建图，不把连线/断开同步回 flow，避免重复路径与误判闭环
        self._building_from_flow = False

        # 视图 → 数据：连线、删除、改名
        self._graph.port_connected.connect(self._on_port_connected)
        self._graph.port_disconnected.connect(self._on_port_disconnected)
        self._graph.nodes_deleted.connect(self._on_nodes_deleted)
        self._graph.viewer().node_name_changed.connect(self._on_node_name_changed)

        # 在节点图右键菜单中增加「Add Node」；右键空白处时在点击位置创建节点；右键节点时记录节点 id 供 Flag 子菜单使用
        self._last_context_menu_scene_pos = None
        self._last_context_menu_node_id: str | None = None
        # 右键前缓存的选中连线（右键后 selection 可能被清空，用于「编辑分支条件」）
        self._context_menu_pipe_selection: list = []
        self._graph.context_menu_prompt.connect(self._on_context_menu_prompt)
        graph_menu = self._graph.viewer().context_menus()["graph"]
        self._ctx_action_add_node = QAction(self._tr_add_script_node.get(), self)
        self._ctx_action_add_node.triggered.connect(self._on_add_node)
        graph_menu.addAction(self._ctx_action_add_node)
        self.bind_text(self._ctx_action_add_node.setText, self._tr_add_script_node)
        self._ctx_action_add_flag = QAction(self._tr_add_flag.get(), self)
        self._ctx_action_add_flag.triggered.connect(self._on_add_flag)
        graph_menu.addAction(self._ctx_action_add_flag)
        self.bind_text(self._ctx_action_add_flag.setText, self._tr_add_flag)
        self._ctx_action_edit_path_condition = QAction(self._tr_edit_branch_condition.get(), self)
        self._ctx_action_edit_path_condition.triggered.connect(self._on_edit_path_condition)
        graph_menu.addAction(self._ctx_action_edit_path_condition)
        self.bind_text(self._ctx_action_edit_path_condition.setText, self._tr_edit_branch_condition)

        # 节点右键菜单：编辑剧情文本（保留 command 引用以便 update_text 时更新文案）
        nodes_menu = self._graph.get_context_menu("nodes")
        self._ctx_command_edit_content = nodes_menu.add_command(
            self._tr_edit_segment_content.get(),
            func=self._on_edit_segment_content,
            node_class=SegmentNode,
        )
        self._ctx_command_edit_comment = nodes_menu.add_command(
            self._tr_edit_comment.get(),
            func=self._on_edit_segment_comment,
            node_class=SegmentNode,
        )
        # FlagNode 右键菜单：「修改flag变量类型」二级菜单（布尔型/整型/浮点型）、「修改flag初始值」
        self._ctx_command_edit_flag_initial = nodes_menu.add_command(
            self._tr_flag_change_initial.get(),
            func=self._on_edit_flag_initial_value,
            node_class=FlagNode,
        )
        self._ctx_command_edit_flag_comment = nodes_menu.add_command(
            self._tr_edit_comment.get(),
            func=self._on_edit_flag_comment,
            node_class=FlagNode,
        )
        # 在 FlagNode 子菜单前插入「修改flag变量类型」二级菜单（库只对直接 action 设置 node_id，子菜单项用 _last_context_menu_node_id）
        nodes_qmenu = nodes_menu.qmenu
        for action in nodes_qmenu.actions():
            sub = action.menu()
            if sub is not None and getattr(sub, "node_class", None) is FlagNode:
                type_submenu = QMenu(self._tr_flag_change_type.get(), self)
                for label_tr, flag_type in [
                    (self._tr_flag_type_bool, FlagType.BOOL),
                    (self._tr_flag_type_int, FlagType.INT),
                    (self._tr_flag_type_float, FlagType.FLOAT),
                ]:
                    a = QAction(label_tr.get(), self)
                    a.triggered.connect(lambda checked=False, ft=flag_type: self._on_set_flag_type(ft))
                    type_submenu.addAction(a)
                sub.insertMenu(sub.actions()[0], type_submenu)
                self._ctx_menu_flag_type = type_submenu
                break
        else:
            self._ctx_menu_flag_type = None

        # 工具栏：所有文案用 bind_text 绑定，语言切换时由 update_text 更新
        toolbar = QWidget()
        bar_layout = QHBoxLayout(toolbar)
        bar_layout.setContentsMargins(4, 2, 4, 2)
        self._btn_add = QPushButton(self._tr_add_script_node.get())
        self._btn_add.clicked.connect(self._on_add_node)
        self.bind_text(self._btn_add.setText, self._tr_add_script_node)
        self.bind_text(self._btn_add.setToolTip, self._tr_btn_add_tooltip)
        self._btn_del = QPushButton(self._tr_btn_del.get())
        self._btn_del.clicked.connect(self._on_delete_selected)
        self.bind_text(self._btn_del.setText, self._tr_btn_del)
        self.bind_text(self._btn_del.setToolTip, self._tr_btn_del_tooltip)
        self._chk_acyclic = QCheckBox(self._tr_chk_acyclic.get())
        self._chk_acyclic.setChecked(True)
        self._chk_acyclic.toggled.connect(self._on_acyclic_toggled)
        self.bind_text(self._chk_acyclic.setText, self._tr_chk_acyclic)
        self.bind_text(self._chk_acyclic.setToolTip, self._tr_chk_acyclic_tooltip)
        self._btn_save = QPushButton(self._tr_save_flow.get())
        self._btn_save.clicked.connect(self._on_save)
        self.bind_text(self._btn_save.setText, self._tr_save_flow)
        self.bind_text(self._btn_save.setToolTip, self._tr_save_tooltip)
        self._btn_load = QPushButton(self._tr_load_flow.get())
        self._btn_load.clicked.connect(self._on_load)
        self.bind_text(self._btn_load.setText, self._tr_load_flow)
        self.bind_text(self._btn_load.setToolTip, self._tr_open_tooltip)
        self._btn_add_flag = QPushButton(self._tr_add_flag.get())
        self._btn_add_flag.clicked.connect(self._on_add_flag)
        self.bind_text(self._btn_add_flag.setText, self._tr_add_flag)
        self.bind_text(self._btn_add_flag.setToolTip, self._tr_btn_add_flag_tooltip)
        bar_layout.addWidget(self._btn_add)
        bar_layout.addWidget(self._btn_add_flag)
        bar_layout.addWidget(self._btn_del)
        bar_layout.addWidget(self._chk_acyclic)
        bar_layout.addWidget(self._btn_save)
        bar_layout.addWidget(self._btn_load)
        bar_layout.addStretch()
        main_layout.addWidget(toolbar)

        # 从数据层构建初始图：Start → Ending
        self._build_initial_flow()
        self._build_graph_from_flow()

        main_layout.addWidget(self._graph.widget)
        for key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            shortcut = QShortcut(QKeySequence(key), self, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(self._on_delete_key)

    def update_text(self) -> None:
        super().update_text()
        # 图右键菜单项需随语言更新
        self._ctx_action_add_node.setText(self._tr_add_script_node.get())
        self._ctx_action_add_flag.setText(self._tr_add_flag.get())
        self._ctx_action_edit_path_condition.setText(self._tr_edit_branch_condition.get())
        # 节点右键菜单由库管理，需手动更新
        self._ctx_command_edit_content.qaction.setText(self._tr_edit_segment_content.get())
        self._ctx_command_edit_comment.qaction.setText(self._tr_edit_comment.get())
        self._ctx_command_edit_flag_initial.qaction.setText(self._tr_flag_change_initial.get())
        self._ctx_command_edit_flag_comment.qaction.setText(self._tr_edit_comment.get())
        if hasattr(self, "_ctx_menu_flag_type") and self._ctx_menu_flag_type is not None:
            self._ctx_menu_flag_type.setTitle(self._tr_flag_change_type.get())
            for action, label_tr in zip(
                self._ctx_menu_flag_type.actions(),
                (self._tr_flag_type_bool, self._tr_flag_type_int, self._tr_flag_type_float),
            ):
                action.setText(label_tr.get())
        # 所有节点及名称区的 tooltip 随语言更新
        for node in self._graph.all_nodes():
            seg_id = self._node_id_to_segment_id.get(node.id)
            if seg_id is not None:
                seg = self._flow.get_segment_by_id(seg_id)
                if seg is not None:
                    self._set_node_tooltips(node, seg)
                continue
            flag_id = self._node_id_to_flag_id.get(node.id)
            if flag_id is not None:
                flag_var = self._flow.get_flag_by_id(flag_id)
                if flag_var is not None:
                    self._set_flag_node_tooltips(node, flag_var)

    def _build_initial_flow(self) -> None:
        """数据层初始状态：Start 段落、Ending 段落、一条路径。"""
        seg_start = StorySegment(name="Start", content="\"剧情从这里开始。\"", is_ending_segment=False)
        seg_ending = StorySegment(name="Ending", content="\"剧情在这里结束。\"", is_ending_segment=True)
        self._flow.segments = [seg_start, seg_ending]
        path = SegmentPath(prev_segment_id=seg_start.id, next_segment_id=seg_ending.id)
        self._flow.paths = [path]
        seg_start.add_path_segment_id(path.id, seg_ending.id)

    def _build_graph_from_flow(
        self,
        segment_positions: dict[str, list[float]] | None = None,
        flag_positions: dict[str, list[float]] | None = None,
    ) -> None:
        """根据当前 flow 在图中创建节点与连线；segment_positions / flag_positions 用于恢复位置。"""
        self._building_from_flow = True
        try:
            self._build_graph_from_flow_impl(
                segment_positions=segment_positions,
                flag_positions=flag_positions,
            )
        finally:
            self._building_from_flow = False

    def _build_graph_from_flow_impl(
        self,
        segment_positions: dict[str, list[float]] | None = None,
        flag_positions: dict[str, list[float]] | None = None,
    ) -> None:
        segment_positions = segment_positions or {}
        flag_positions = flag_positions or {}
        default_positions = [(0, 0), (400, 0)]
        for i, seg in enumerate(self._flow.segments):
            pos = segment_positions.get(seg.id)
            if pos is not None and len(pos) >= 2:
                pos = (float(pos[0]), float(pos[1]))
            else:
                pos = default_positions[i] if i < len(default_positions) else (0, 0)
            node = self._graph.create_node(
                _SEGMENT_NODE_TYPE,
                name=seg.name,
                pos=pos,
            )
            self._node_id_to_segment_id[node.id] = seg.id
            self._set_node_tooltips(node, seg)
        for f in self._flow.flags:
            pos = flag_positions.get(f.id)
            if pos is not None and len(pos) >= 2:
                pos = (float(pos[0]), float(pos[1]))
            else:
                pos = (0, 0)
            node = self._graph.create_node(
                _FLAG_NODE_TYPE,
                name=f.name,
                pos=pos,
            )
            self._node_id_to_flag_id[node.id] = f.id
            self._update_flag_node_display(node)
            self._set_flag_node_tooltips(node, f)
        seg_id_to_node = {
            self._node_id_to_segment_id[n.id]: n
            for n in self._graph.all_nodes()
            if n.id in self._node_id_to_segment_id
        }
        for path in self._flow.paths:
            prev_node = seg_id_to_node.get(path.prev_segment_id)
            next_node = seg_id_to_node.get(path.next_segment_id)
            if prev_node is not None and next_node is not None:
                prev_node.set_output(0, next_node.input(0))
        self._update_pipe_tooltips()

    def _update_pipe_tooltips(self) -> None:
        """根据 SegmentPath.condition_expression 刷新场景中所有连线的 tooltip。"""
        scene = self._graph.viewer().scene()
        for item in scene.items():
            if not isinstance(item, PipeItem):
                continue
            if not item.input_port or not item.output_port:
                continue
            prev_seg_id = self._node_id_to_segment_id.get(item.output_port.node.id)
            next_seg_id = self._node_id_to_segment_id.get(item.input_port.node.id)
            if prev_seg_id is None or next_seg_id is None:
                item.setToolTip("")
                continue
            path = next(
                (p for p in self._flow.paths if p.prev_segment_id == prev_seg_id and p.next_segment_id == next_seg_id),
                None,
            )
            text = (path.condition_expression or "").strip() if path is not None else ""
            item.setToolTip(text)

    def _set_node_tooltips(self, node, segment: StorySegment) -> None:
        """根据段落类型或注释设置节点与名称区的 tooltip（使用当前语言）。有注释时节点 tooltip 显示注释。"""
        if segment.comment and segment.comment.strip():
            node.view.setToolTip(segment.comment.strip())
        elif segment.is_ending_segment:
            node.view.setToolTip(self._tr_node_tooltip_ending.get())
        elif segment.name == "Start":
            node.view.setToolTip(self._tr_node_tooltip_start.get())
        else:
            node.view.setToolTip(self._tr_node_tooltip_default.get())
        node.view.text_item.setToolTip(self._tr_node_name_edit_tooltip.get())

    def _set_flag_node_tooltips(self, node, flag_var: FlagVariable) -> None:
        """根据 FlagVariable.comment 或当前语言默认文案设置 Flag 节点及名称区的 tooltip。"""
        if flag_var.comment and flag_var.comment.strip():
            node.view.setToolTip(flag_var.comment.strip())
        else:
            node.view.setToolTip(self._tr_node_tooltip_flag_default.get())
        node.view.text_item.setToolTip(self._tr_node_name_edit_tooltip.get())

    def _format_flag_initial_value(self, flag_var: FlagVariable) -> str:
        """将 FlagVariable.initial_value 格式化为节点中部显示的字符串。"""
        if flag_var.flag_type == FlagType.BOOL:
            return "True" if flag_var.initial_value else "False"
        if flag_var.flag_type == FlagType.INT:
            return str(int(flag_var.initial_value))
        return str(float(flag_var.initial_value))

    def _update_flag_node_display(self, node) -> None:
        """根据节点对应的 FlagVariable 更新节点中部的 initial_value 显示。"""
        flag_id = self._node_id_to_flag_id.get(node.id)
        if flag_id is None:
            return
        flag_var = self._flow.get_flag_by_id(flag_id)
        if flag_var is None:
            return
        if node.view.has_widget("initial_value_display"):
            node.get_widget("initial_value_display").set_value(
                self._format_flag_initial_value(flag_var)
            )

    def _next_segment_name(self) -> str:
        """生成下一个 segment_<index> 名称，保证不与已有节点重名。"""
        pattern = re.compile(r"^segment_(\d+)$")
        max_index = -1
        for node in self._graph.all_nodes():
            m = pattern.match(node.name())
            if m:
                max_index = max(max_index, int(m.group(1)))
        return "segment_{}".format(max_index + 1)

    def _next_flag_name(self) -> str:
        """生成下一个 flag_<index> 名称，保证不与已有节点重名。"""
        pattern = re.compile(r"^flag_(\d+)$")
        max_index = -1
        for node in self._graph.all_nodes():
            m = pattern.match(node.name())
            if m:
                max_index = max(max_index, int(m.group(1)))
        return "flag_{}".format(max_index + 1)

    def _on_context_menu_prompt(self, _menu: object, node: object) -> None:
        """右键菜单即将弹出时记录场景坐标，供「Add Node」在点击位置创建节点；记录节点 id 供 Flag 子菜单使用；图菜单时根据光标下或已选中的单条连线启用「编辑分支条件」。"""
        if node is None:
            pos = self._graph.viewer().scene_cursor_pos()
            self._last_context_menu_scene_pos = (pos.x(), pos.y())
            self._last_context_menu_node_id = None
            # 优先用当前选中连线；若无则取光标下的连线（右键后 selection 常被清空）
            self._context_menu_pipe_selection = list(self._graph.selected_pipes())
            if len(self._context_menu_pipe_selection) != 1:
                scene = self._graph.viewer().scene()
                pt = QPointF(pos.x(), pos.y())
                items_at = scene.items(pt)
                pipes_at = [i for i in items_at if isinstance(i, PipeItem)]
                if len(pipes_at) == 1:
                    old_sel = list(scene.selectedItems())
                    scene.clearSelection()
                    pipes_at[0].setSelected(True)
                    self._context_menu_pipe_selection = list(self._graph.selected_pipes())
                    scene.clearSelection()
                    for item in old_sel:
                        item.setSelected(True)
            self._ctx_action_edit_path_condition.setEnabled(len(self._context_menu_pipe_selection) == 1)
        else:
            self._last_context_menu_scene_pos = None
            self._last_context_menu_node_id = node.id

    def _on_add_node(self) -> None:
        if self._last_context_menu_scene_pos is not None:
            pos = self._last_context_menu_scene_pos
            self._last_context_menu_scene_pos = None
        else:
            pos = (0, 0)
        name = self._next_segment_name()
        segment = StorySegment(name=name, content="", is_ending_segment=False)
        self._flow.segments.append(segment)
        node = self._graph.create_node(_SEGMENT_NODE_TYPE, name=name, pos=pos)
        self._node_id_to_segment_id[node.id] = segment.id
        self._set_node_tooltips(node, segment)

    def _on_add_flag(self) -> None:
        """在图中添加一个 FlagNode，并在 flow.flags 中新增对应 FlagVariable。"""
        if self._last_context_menu_scene_pos is not None:
            pos = self._last_context_menu_scene_pos
            self._last_context_menu_scene_pos = None
        else:
            pos = (0, 0)
        name = self._next_flag_name()
        flag_var = FlagVariable(name=name, flag_type=FlagType.BOOL, initial_value=False)
        self._flow.flags.append(flag_var)
        node = self._graph.create_node(_FLAG_NODE_TYPE, name=name, pos=pos)
        self._node_id_to_flag_id[node.id] = flag_var.id
        self._update_flag_node_display(node)
        self._set_flag_node_tooltips(node, flag_var)

    def _on_delete_selected(self) -> None:
        self._delete_selected_pipes()
        self._graph.delete_nodes(self._graph.selected_nodes())

    def _on_acyclic_toggled(self, checked: bool) -> None:
        self._graph.set_acyclic(checked)

    def _on_delete_key(self) -> None:
        self._on_delete_selected()

    def _on_edit_path_condition(self) -> None:
        """图右键「编辑分支条件」：对当前选中的单条连线，编辑对应 SegmentPath.condition_expression。"""
        pipes = self._context_menu_pipe_selection if len(self._context_menu_pipe_selection) == 1 else self._graph.selected_pipes()
        if len(pipes) != 1:
            return
        in_port, out_port = pipes[0]
        prev_seg_id = self._node_id_to_segment_id.get(out_port.node().id)
        next_seg_id = self._node_id_to_segment_id.get(in_port.node().id)
        if prev_seg_id is None or next_seg_id is None:
            return
        path = next(
            (p for p in self._flow.paths if p.prev_segment_id == prev_seg_id and p.next_segment_id == next_seg_id),
            None,
        )
        if path is None:
            return
        dialog = PathConditionEditDialog(
            self,
            segment_path=path,
            title=self._tr_edit_branch_condition_dialog_title.get(),
            placeholder=self._tr_edit_branch_condition_placeholder.get(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_pipe_tooltips()

    def _on_port_connected(self, in_port, out_port) -> None:
        """连线建立：在数据层添加 SegmentPath。NodeGraphQt 信号参数顺序为 (input_port, output_port)。同一条连线只添加一次。"""
        if self._building_from_flow:
            return
        out_node = out_port.node()
        in_node = in_port.node()
        prev_seg_id = self._node_id_to_segment_id.get(out_node.id)
        next_seg_id = self._node_id_to_segment_id.get(in_node.id)
        if prev_seg_id is None or next_seg_id is None:
            return
        already = any(
            p.prev_segment_id == prev_seg_id and p.next_segment_id == next_seg_id
            for p in self._flow.paths
        )
        if already:
            return
        path = SegmentPath(prev_segment_id=prev_seg_id, next_segment_id=next_seg_id)
        self._flow.paths.append(path)
        prev_seg = self._flow.get_segment_by_id(prev_seg_id)
        if prev_seg is not None:
            prev_seg.add_path_segment_id(path.id, next_seg_id)
        self._update_pipe_tooltips()

    def _on_port_disconnected(self, in_port, out_port) -> None:
        """连线断开：从数据层移除对应 SegmentPath。NodeGraphQt 信号参数顺序为 (input_port, output_port)。"""
        if self._building_from_flow:
            return
        out_node = out_port.node()
        in_node = in_port.node()
        prev_seg_id = self._node_id_to_segment_id.get(out_node.id)
        next_seg_id = self._node_id_to_segment_id.get(in_node.id)
        if prev_seg_id is None or next_seg_id is None:
            return
        to_remove = [
            p for p in self._flow.paths
            if p.prev_segment_id == prev_seg_id and p.next_segment_id == next_seg_id
        ]
        for p in to_remove:
            self._flow.paths.remove(p)
            prev_seg = self._flow.get_segment_by_id(prev_seg_id)
            if prev_seg is not None and p.id in prev_seg.paths_segment_ids:
                del prev_seg.paths_segment_ids[p.id]

    def _on_nodes_deleted(self, node_ids: list) -> None:
        """节点删除：从数据层移除对应段落/Flag 及关联路径，并清理映射。"""
        for nid in node_ids:
            seg_id = self._node_id_to_segment_id.pop(nid, None)
            if seg_id is not None:
                self._flow.segments = [s for s in self._flow.segments if s.id != seg_id]
                self._flow.paths = [
                    p for p in self._flow.paths
                    if p.prev_segment_id != seg_id and p.next_segment_id != seg_id
                ]
                for s in self._flow.segments:
                    for path_id in list(s.paths_segment_ids.keys()):
                        if s.paths_segment_ids[path_id] == seg_id:
                            del s.paths_segment_ids[path_id]
                continue
            flag_id = self._node_id_to_flag_id.pop(nid, None)
            if flag_id is not None:
                self._flow.flags = [f for f in self._flow.flags if f.id != flag_id]

    def _on_node_name_changed(self, node_id: str, name: str) -> None:
        """节点改名：同步到数据层 StorySegment.name 或 FlagVariable.name（id 保持不变），Segment 依 comment 重设 tooltip。"""
        seg_id = self._node_id_to_segment_id.get(node_id)
        if seg_id is not None:
            seg = self._flow.get_segment_by_id(seg_id)
            if seg is not None:
                seg.name = name
                node = self._graph.get_node_by_id(node_id)
                if node is not None:
                    self._set_node_tooltips(node, seg)
            return
        flag_id = self._node_id_to_flag_id.get(node_id)
        if flag_id is not None:
            flag_var = self._flow.get_flag_by_id(flag_id)
            if flag_var is not None:
                flag_var.name = name
                node = self._graph.get_node_by_id(node_id)
                if node is not None:
                    self._set_flag_node_tooltips(node, flag_var)

    def _on_edit_segment_content(self, _graph, node) -> None:
        """节点右键「编辑剧情文本」：弹出对话框编辑对应 StorySegment.content，关闭时保存。"""
        seg_id = self._node_id_to_segment_id.get(node.id)
        if seg_id is None:
            return
        seg = self._flow.get_segment_by_id(seg_id)
        if seg is None:
            return
        dialog = SegmentContentEditDialog(
            self,
            segment=seg,
            title=self._tr_edit_dialog_title.get(),
            placeholder=self._tr_edit_dialog_placeholder.get(),
        )
        dialog.exec()

    def _on_edit_segment_comment(self, _graph, node) -> None:
        """节点右键「编辑注释」：弹出对话框编辑对应 StorySegment.comment，关闭时保存并设为节点 tooltip。"""
        seg_id = self._node_id_to_segment_id.get(node.id)
        if seg_id is None:
            return
        seg = self._flow.get_segment_by_id(seg_id)
        if seg is None:
            return
        dialog = SegmentCommentEditDialog(
            self,
            segment=seg,
            title=self._tr_edit_comment_dialog_title.get(),
            placeholder=self._tr_edit_comment_dialog_placeholder.get(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._set_node_tooltips(node, seg)

    def _on_set_flag_type(self, new_type: FlagType) -> None:
        """将当前右键的 Flag 节点对应的 FlagVariable 的 flag_type 设为 new_type；类型未变则不改 initial_value，类型改变则 bool→False、int/float→0。"""
        node_id = self._last_context_menu_node_id
        if node_id is None:
            return
        flag_id = self._node_id_to_flag_id.get(node_id)
        if flag_id is None:
            return
        flag_var = self._flow.get_flag_by_id(flag_id)
        if flag_var is None:
            return
        old_type = flag_var.flag_type
        flag_var.flag_type = new_type
        if old_type != new_type:
            flag_var.initial_value = False if new_type == FlagType.BOOL else 0
        graph_node = self._graph.get_node_by_id(node_id)
        if graph_node is not None:
            self._update_flag_node_display(graph_node)

    def _on_edit_flag_initial_value(self, _graph, node) -> None:
        """节点右键「修改flag初始值」：弹出对话框编辑对应 FlagVariable.initial_value。"""
        flag_id = self._node_id_to_flag_id.get(node.id)
        if flag_id is None:
            return
        flag_var = self._flow.get_flag_by_id(flag_id)
        if flag_var is None:
            return
        dialog = FlagInitialValueEditDialog(
            self,
            flag_var=flag_var,
            title=self._tr_flag_initial_dialog_title.get(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_flag_node_display(node)
            self._set_flag_node_tooltips(node, flag_var)

    def _on_edit_flag_comment(self, _graph, node) -> None:
        """节点右键「编辑注释」：弹出对话框编辑对应 FlagVariable.comment，关闭时同步到节点 tooltip。"""
        flag_id = self._node_id_to_flag_id.get(node.id)
        if flag_id is None:
            return
        flag_var = self._flow.get_flag_by_id(flag_id)
        if flag_var is None:
            return
        dialog = FlagCommentEditDialog(
            self,
            flag_var=flag_var,
            title=self._tr_edit_comment_dialog_title.get(),
            placeholder=self._tr_edit_comment_dialog_placeholder.get(),
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._set_flag_node_tooltips(node, flag_var)

    def _on_save(self) -> None:
        """将当前流程数据与节点位置保存为 JSON 文件。"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr_save_dialog_title.get(),
            "",
            self._tr_json_filter.get(),
        )
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        flow_dict = self._flow.to_dict()
        node_positions = {}
        flag_positions = {}
        for node in self._graph.all_nodes():
            pos = getattr(node.model, "pos", [0.0, 0.0])
            pos_list = list(pos) if isinstance(pos, (list, tuple)) else [0.0, 0.0]
            seg_id = self._node_id_to_segment_id.get(node.id)
            if seg_id is not None:
                node_positions[seg_id] = pos_list
            else:
                flag_id = self._node_id_to_flag_id.get(node.id)
                if flag_id is not None:
                    flag_positions[flag_id] = pos_list
        flow_dict["node_positions"] = node_positions
        flow_dict["flag_positions"] = flag_positions
        path.write_text(
            json.dumps(flow_dict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _on_load(self) -> None:
        """从 JSON 文件加载流程数据与节点位置，重建视图。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr_open_dialog_title.get(),
            "",
            self._tr_json_filter.get(),
        )
        if not path:
            return
        path = Path(path)
        if not path.is_file():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        node_positions = data.pop("node_positions", {})
        flag_positions = data.pop("flag_positions", {})
        self._node_id_to_segment_id.clear()
        self._node_id_to_flag_id.clear()
        for node in list(self._graph.all_nodes()):
            self._graph.delete_nodes([node])
        self._flow = GameScriptFlow.load_from_dict(data)
        self._build_graph_from_flow(
            segment_positions=node_positions,
            flag_positions=flag_positions,
        )

    def _delete_selected_pipes(self) -> None:
        """删除当前选中的连线。selected_pipes() 返回 (Port, Port) 列表。"""
        for port1, port2 in self._graph.selected_pipes():
            port1.disconnect_from(port2)
