# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import traceback
from PySide6.QtCore import *
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QStyle

from preppipe.language import TranslationDomain
from ..forms.generated.ui_errordialog import Ui_ErrorDialog

TR_gui_errordialog = TranslationDomain("gui_errordialog")


class ErrorDialog(QDialog):
  """Generic error dialog with summary, copyable details and OK button. Uses critical/error style (icon)."""

  ui: Ui_ErrorDialog

  _tr_ok_button = TR_gui_errordialog.tr("ok_button",
    en="OK",
    zh_cn="了解了",
    zh_hk="了解了",
  )
  _tr_error_title = TR_gui_errordialog.tr("error_title",
    en="Error",
    zh_cn="错误",
    zh_hk="錯誤",
  )
  _tr_error_summary = TR_gui_errordialog.tr("error_summary",
    en="An error occurred. See details below. If you need to contact the developer, please send the error message.",
    zh_cn="发生错误，详见下方。如需联系开发者，请将报错信息一并发送。",
    zh_hk="發生錯誤，詳見下方。如需聯繫開發者，請將報錯信息一併發送。",
  )

  def __init__(self, parent, title: str, summary: str, detail: str):
    super().__init__(parent)
    self.ui = Ui_ErrorDialog()
    self.ui.setupUi(self)
    self.setWindowTitle(title)
    critical_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
    self.setWindowIcon(critical_icon)
    icon_size = 48
    self.ui.iconLabel.setPixmap(critical_icon.pixmap(icon_size, icon_size))
    self.ui.summaryLabel.setText(summary)
    self.ui.detailsPlainTextEdit.setPlainText(detail)
    ok_btn = self.ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    if ok_btn:
      ok_btn.setText(ErrorDialog._tr_ok_button.get())
      ok_btn.setDefault(True)
    self.ui.buttonBox.accepted.connect(self.accept)

  @staticmethod
  def show_exception(parent, exc: BaseException) -> None:
    title = ErrorDialog._tr_error_title.get()
    summary = ErrorDialog._tr_error_summary.get()
    detail = traceback.format_exc()
    dlg = ErrorDialog(parent, title, summary, detail)
    dlg.exec()
