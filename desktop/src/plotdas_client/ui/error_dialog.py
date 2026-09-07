from PySide6.QtWidgets import QMessageBox


def show_error(parent, summary: str, details: str = "") -> None:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle("PlotDas 错误")
    dialog.setText(summary or "操作失败")
    if details:
        dialog.setDetailedText(details)
    dialog.exec()
