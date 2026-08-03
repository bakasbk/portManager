"""
port_manager.py — 端口占用一键清理工具（GUI 版）

基于 PySide6，封装 netstat / findstr / taskkill：
  - 输入端口号，一键查询占用进程（含进程名 / 协议 / 地址 / 状态）
  - 选中进程后直接结束（可选连同子进程）
  - 收藏常用端口，重启后仍保留
  - 日志区回显实际执行的命令与结果

运行：env/Scripts/python port_manager.py  或直接双击 start.bat
"""

import sys
import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QComboBox, QPlainTextEdit, QMessageBox,
    QGroupBox, QAbstractItemView, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import port_core as core


class PortManagerWindow(QMainWindow):
    COLUMNS = ["协议", "本地地址", "外部地址", "状态", "PID", "进程名"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("端口占用一键清理工具")
        self.resize(860, 640)
        self._build_ui()
        self._load_favorites()

    # ---------------- UI 构建 ----------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 1) 端口输入区
        in_box = QGroupBox("查询")
        in_layout = QHBoxLayout(in_box)
        in_layout.addWidget(QLabel("端口号:"))
        self.port_edit = QLineEdit()
        self.port_edit.setPlaceholderText("例如 8080")
        self.port_edit.setFixedWidth(120)
        self.port_edit.returnPressed.connect(self.on_query)
        in_layout.addWidget(self.port_edit)

        self.query_btn = QPushButton("查询占用")
        self.query_btn.setDefault(True)
        self.query_btn.clicked.connect(self.on_query)
        in_layout.addWidget(self.query_btn)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.on_query)
        in_layout.addWidget(self.refresh_btn)
        in_layout.addStretch(1)
        root.addWidget(in_box)

        # 2) 结果表格
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 160)
        root.addWidget(self.table, stretch=3)

        # 3) 操作区
        op_box = QGroupBox("操作")
        op_layout = QHBoxLayout(op_box)
        self.tree_chk = QCheckBox("连同子进程一起结束 (/T)")
        op_layout.addWidget(self.tree_chk)
        op_layout.addStretch(1)
        self.kill_btn = QPushButton("结束选中进程")
        self.kill_btn.setStyleSheet("background-color:#d9534f;color:white;font-weight:bold;")
        self.kill_btn.clicked.connect(self.on_kill)
        op_layout.addWidget(self.kill_btn)
        root.addWidget(op_box)

        # 4) 常用端口收藏区
        fav_box = QGroupBox("常用端口收藏")
        fav_layout = QHBoxLayout(fav_box)
        fav_layout.addWidget(QLabel("收藏:"))
        self.fav_combo = QComboBox()
        self.fav_combo.setMinimumWidth(120)
        self.fav_combo.setEditable(False)
        fav_layout.addWidget(self.fav_combo)

        self.load_fav_btn = QPushButton("加载")
        self.load_fav_btn.clicked.connect(self.on_load_fav)
        fav_layout.addWidget(self.load_fav_btn)

        self.add_fav_btn = QPushButton("收藏当前端口")
        self.add_fav_btn.clicked.connect(self.on_add_fav)
        fav_layout.addWidget(self.add_fav_btn)

        self.del_fav_btn = QPushButton("删除选中")
        self.del_fav_btn.clicked.connect(self.on_del_fav)
        fav_layout.addWidget(self.del_fav_btn)
        fav_layout.addStretch(1)
        root.addWidget(fav_box)

        # 5) 日志区
        log_box = QGroupBox("命令日志（实际执行的 netstat / findstr / taskkill）")
        log_layout = QVBoxLayout(log_box)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        mono = QFont("Consolas", 9)
        self.log.setFont(mono)
        log_layout.addWidget(self.log)
        root.addWidget(log_box, stretch=2)

        self._append_log("就绪。输入端口号后点击“查询占用”。", is_cmd=False)

    # ---------------- 业务逻辑 ----------------

    def on_query(self):
        port_text = self.port_edit.text().strip()
        if not port_text.isdigit():
            QMessageBox.warning(self, "提示", "请输入合法的端口号（数字）。")
            return
        port = int(port_text)
        self._append_log(f">>> 查询端口 {port}", is_cmd=False)
        try:
            rows, cmd, raw = core.query_port(port)
        except Exception as e:  # noqa: BLE001
            self._append_log(f"查询出错: {e}", is_cmd=False)
            QMessageBox.critical(self, "错误", str(e))
            return

        self._append_log(cmd, is_cmd=True)
        if raw.strip():
            self._append_log(raw.strip(), is_cmd=False)

        self.table.setRowCount(0)
        if not rows:
            self._append_log(f"端口 {port} 当前未被占用。", is_cmd=False)
            QMessageBox.information(self, "结果", f"端口 {port} 当前未被占用。")
            return

        self.table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            self._set_cell(r, 0, item["proto"])
            self._set_cell(r, 1, item["local"])
            self._set_cell(r, 2, item["foreign"])
            self._set_cell(r, 3, item["state"] or "-")
            self._set_cell(r, 4, str(item["pid"]))
            self._set_cell(r, 5, item["name"])
        self._append_log(f"找到 {len(rows)} 条占用记录。", is_cmd=False)

    def on_kill(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先在表格中选中要结束的进程。")
            return
        pid = int(self.table.item(row, 4).text())
        name = self.table.item(row, 5).text()
        tree = self.tree_chk.isChecked()
        msg = f"确定要结束该进程吗？\n\nPID: {pid}\n进程名: {name}\n连同子进程: {'是' if tree else '否'}"
        if QMessageBox.question(self, "确认结束进程", msg,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return

        self._append_log(f">>> 结束进程 PID={pid} (tree={tree})", is_cmd=False)
        ok, cmd, output = core.kill_process(pid, tree=tree)
        self._append_log(cmd, is_cmd=True)
        if output:
            self._append_log(output, is_cmd=False)

        if ok:
            self._append_log(f"进程 PID={pid} 已结束。", is_cmd=False)
            QMessageBox.information(self, "完成", f"进程 PID={pid} 已结束。")
            self.on_query()  # 结束后刷新列表
        else:
            self._append_log(f"结束失败（可能需管理员权限或进程已退出）。", is_cmd=False)
            QMessageBox.warning(
                self, "结束失败",
                f"无法结束 PID={pid}。\n若提示“拒绝访问”，请右键以管理员身份运行本程序。\n\n命令输出:\n{output}"
            )

    # ---------------- 收藏端口 ----------------

    def _load_favorites(self):
        self.fav_combo.blockSignals(True)
        self.fav_combo.clear()
        favs = core.load_favorites()
        for p in favs:
            self.fav_combo.addItem(str(p))
        if favs:
            self.fav_combo.setCurrentIndex(0)
        self.fav_combo.blockSignals(False)

    def on_load_fav(self):
        text = self.fav_combo.currentText().strip()
        if text.isdigit():
            self.port_edit.setText(text)
            self.on_query()

    def on_add_fav(self):
        text = self.port_edit.text().strip()
        if not text.isdigit():
            QMessageBox.warning(self, "提示", "请先在端口框输入要收藏的端口号。")
            return
        port = int(text)
        favs = core.load_favorites()
        if port in favs:
            QMessageBox.information(self, "提示", f"端口 {port} 已在收藏列表中。")
            return
        favs.append(port)
        core.save_favorites(favs)
        self._load_favorites()
        # 选中刚添加的端口
        idx = self.fav_combo.findText(str(port))
        if idx >= 0:
            self.fav_combo.setCurrentIndex(idx)
        self._append_log(f"已收藏端口 {port}。", is_cmd=False)

    def on_del_fav(self):
        text = self.fav_combo.currentText().strip()
        if not text.isdigit():
            return
        port = int(text)
        favs = [p for p in core.load_favorites() if p != port]
        core.save_favorites(favs)
        self._load_favorites()
        self._append_log(f"已删除收藏端口 {port}。", is_cmd=False)

    # ---------------- 工具方法 ----------------

    def _set_cell(self, row, col, text):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setItem(row, col, item)

    def _append_log(self, text, is_cmd=False):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = "$ " if is_cmd else "  "
        self.log.appendPlainText(f"[{ts}] {prefix}{text}")


def main():
    app = QApplication(sys.argv)
    win = PortManagerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
