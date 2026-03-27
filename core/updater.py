"""
EthoTrack Pro - 在线版本检测与更新模块
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt, QUrl, QThread
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QApplication, QProgressBar, QMessageBox
)
from PyQt6.QtGui import QDesktopServices, QFont

from core.logger import logger


# ─────────────────────────────────────────────
#   软件当前版本（开发者在此处维护）
# ─────────────────────────────────────────────
CURRENT_VERSION = "1.0.0"

# 版本信息托管地址
VERSION_CHECK_URL = "https://gitee.com/ethotrack/ethotrack/raw/master/version.json"

# 超时时间（秒）
REQUEST_TIMEOUT = 8


# ─────────────────────────────────────────────
#   版本信息数据类
# ─────────────────────────────────────────────
@dataclass
class VersionInfo:
    version: str
    title: str
    notes: str
    download_url: str
    mandatory: bool = False


# ─────────────────────────────────────────────
#   版本比较工具
# ─────────────────────────────────────────────
def _parse_version(v: str) -> tuple:
    nums = re.findall(r'\d+', v)
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer(remote: str, current: str) -> bool:
    return _parse_version(remote) > _parse_version(current)


# ─────────────────────────────────────────────
#   更新检测信号发射器
# ─────────────────────────────────────────────
class UpdateSignals(QObject):
    update_available = pyqtSignal(object)
    check_failed     = pyqtSignal(str)


# ─────────────────────────────────────────────
#   后台下载线程
# ─────────────────────────────────────────────
class DownloadWorker(QThread):
    """在后台线程中下载安装包，实时报告进度"""
    progress = pyqtSignal(int)   # 0-100
    finished = pyqtSignal(str)   # 下载完成，传回本地文件路径
    failed   = pyqtSignal(str)   # 下载失败，传回错误信息

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url  = url
        self.dest = dest

    def run(self):
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": f"EthoTrackPro/{CURRENT_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192
                with open(self.dest, 'wb') as f:
                    while True:
                        if self.isInterruptionRequested():
                            raise RuntimeError("下载已取消")
                        buf = resp.read(chunk_size)
                        if not buf:
                            break
                        f.write(buf)
                        downloaded += len(buf)
                        if total > 0:
                            self.progress.emit(int(downloaded * 100 / total))
            self.progress.emit(100)
            self.finished.emit(self.dest)
        except Exception as e:
            self.failed.emit(str(e))


# ─────────────────────────────────────────────
#   后台检测线程
# ─────────────────────────────────────────────
class UpdateChecker:
    def __init__(self, url: str = VERSION_CHECK_URL, current: str = CURRENT_VERSION):
        self.url = url
        self.current = current
        self.signals = UpdateSignals()

    def check_async(self):
        """启动后台检测线程（非阻塞）"""
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            logger.info(f"[更新检测] 请求: {self.url}")
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": f"EthoTrackPro/{self.current}"},
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")

            data = json.loads(raw)
            remote_ver = data.get("version", "0.0.0")
            logger.info(f"[更新检测] 远程版本: {remote_ver}, 本地版本: {self.current}")

            if is_newer(remote_ver, self.current):
                info = VersionInfo(
                    version      = remote_ver,
                    title        = data.get("title", f"EthoTrack Pro {remote_ver}"),
                    notes        = data.get("notes", "暂无更新说明"),
                    download_url = data.get("download_url", ""),
                    mandatory    = data.get("mandatory", False),
                )
                self.signals.update_available.emit(info)
            else:
                logger.info("[更新检测] 当前已是最新版本")

        except urllib.error.URLError as e:
            logger.warning(f"[更新检测] 网络错误: {e}")
            self.signals.check_failed.emit(str(e))
        except Exception as e:
            logger.warning(f"[更新检测] 解析失败: {e}")
            self.signals.check_failed.emit(str(e))


# ─────────────────────────────────────────────
#   更新通知对话框（含应用内下载）
# ─────────────────────────────────────────────
class UpdateDialog(QDialog):
    """弹出更新通知，支持应用内自动下载安装包"""

    def __init__(self, info: VersionInfo, parent=None):
        super().__init__(parent)
        self.info = info
        self._worker: Optional[DownloadWorker] = None
        self.setWindowTitle("发现新版本")
        self.setFixedWidth(500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 20)
        layout.setSpacing(14)

        # 标题
        title_lbl = QLabel(f"🚀  {self.info.title}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        layout.addWidget(title_lbl)

        # 版本对比
        ver_lbl = QLabel(
            f"当前版本 <b>{CURRENT_VERSION}</b>　→　最新版本 "
            f"<span style='color:#2563EB;'><b>{self.info.version}</b></span>"
        )
        ver_lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(ver_lbl)

        # 分割线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # 更新日志
        notes_lbl = QLabel("更新内容：")
        notes_lbl.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        layout.addWidget(notes_lbl)

        notes_box = QTextEdit()
        notes_box.setMarkdown(self.info.notes)
        notes_box.setReadOnly(True)
        notes_box.setFixedHeight(140)
        layout.addWidget(notes_box)

        # 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态提示
        self.hint_lbl = QLabel("点击「立即更新」将自动下载并启动安装程序。")
        self.hint_lbl.setStyleSheet("color: #71717A; font-size: 11px;")
        self.hint_lbl.setWordWrap(True)
        layout.addWidget(self.hint_lbl)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        if not self.info.mandatory:
            self.skip_btn = QPushButton("稍后再说")
            self.skip_btn.setFixedHeight(36)
            self.skip_btn.clicked.connect(self.reject)
            btn_row.addWidget(self.skip_btn)
        else:
            self.skip_btn = None

        btn_row.addStretch()

        # 浏览器下载（备用）
        self.browser_btn = QPushButton("浏览器下载")
        self.browser_btn.setFixedHeight(36)
        self.browser_btn.setStyleSheet(
            "color: #2563EB; border: 1px solid #2563EB; "
            "border-radius: 8px; padding: 0 14px;"
        )
        self.browser_btn.clicked.connect(self._open_browser)
        btn_row.addWidget(self.browser_btn)

        # 主按钮
        self.dl_btn = QPushButton("立即更新  ↓")
        self.dl_btn.setFixedHeight(36)
        self.dl_btn.setDefault(True)
        self.dl_btn.setStyleSheet(
            "background-color: #2563EB; color: white; "
            "border: none; border-radius: 8px; padding: 0 18px; font-weight: bold;"
        )
        self.dl_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.dl_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------

    def _open_browser(self):
        """回退：用系统浏览器打开下载链接"""
        if self.info.download_url:
            QDesktopServices.openUrl(QUrl(self.info.download_url))

    def _start_download(self):
        """开始应用内下载"""
        if not self.info.download_url:
            self._open_browser()
            return

        # 推断文件名
        url_path = self.info.download_url.split('?')[0]
        filename = url_path.split('/')[-1] or f"EthoTrackPro_{self.info.version}_setup.exe"
        dest = os.path.join(tempfile.gettempdir(), filename)

        # 锁定 UI
        self.dl_btn.setEnabled(False)
        self.dl_btn.setText("下载中...")
        self.browser_btn.setEnabled(False)
        if self.skip_btn:
            self.skip_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.hint_lbl.setText(f"正在下载 {filename}，请稍候...")
        self.hint_lbl.setStyleSheet("color: #71717A; font-size: 11px;")

        # 启动下载线程
        self._worker = DownloadWorker(self.info.download_url, dest)
        self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.failed.connect(self._on_download_failed)
        self._worker.start()

    def _on_download_finished(self, path: str):
        """下载完成：启动安装包并退出程序"""
        self.progress_bar.setValue(100)
        self.hint_lbl.setText("下载完成！正在启动安装程序，软件即将关闭...")
        self.hint_lbl.setStyleSheet("color: #22C55E; font-size: 11px;")
        logger.info(f"[更新] 安装包已下载至: {path}")
        try:
            if os.name == 'nt':
                os.startfile(path)   # Windows：直接启动 .exe
            else:
                subprocess.Popen(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', path])
            QApplication.quit()
        except Exception as e:
            logger.error(f"[更新] 启动安装失败: {e}")
            QMessageBox.critical(
                self, "启动安装失败",
                f"无法自动启动安装程序：\n{path}\n\n错误：{e}\n\n请手动运行该文件。"
            )
            self._reset_buttons()

    def _on_download_failed(self, msg: str):
        """下载失败：提示用户改用浏览器"""
        logger.warning(f"[更新] 下载失败: {msg}")
        self.progress_bar.setVisible(False)
        self.hint_lbl.setText(f"下载失败，请使用「浏览器下载」手动获取安装包。")
        self.hint_lbl.setStyleSheet("color: #EF4444; font-size: 11px;")
        self._reset_buttons()
        QMessageBox.warning(
            self, "下载失败",
            f"自动下载失败：\n{msg}\n\n请点击「浏览器下载」手动下载安装包。"
        )

    def _reset_buttons(self):
        """恢复按钮可用状态"""
        self.dl_btn.setEnabled(True)
        self.dl_btn.setText("重试")
        self.browser_btn.setEnabled(True)
        if self.skip_btn:
            self.skip_btn.setEnabled(True)

    def closeEvent(self, event):
        """关闭时停止下载线程"""
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(3000)
        super().closeEvent(event)


# ─────────────────────────────────────────────
#   快捷函数：在主窗口启动后触发检测
# ─────────────────────────────────────────────
def start_update_check(parent_window, delay_ms: int = 3000):
    """
    在主窗口完全加载后，延迟 delay_ms 毫秒再后台检测版本。
    """
    checker = UpdateChecker()

    def _on_update_available(info: VersionInfo):
        dlg = UpdateDialog(info, parent=parent_window)
        dlg.exec()

    def _on_check_failed(msg: str):
        logger.debug(f"[更新检测] 静默失败: {msg}")

    checker.signals.update_available.connect(_on_update_available)
    checker.signals.check_failed.connect(_on_check_failed)

    # 延迟启动，不阻塞 UI
    QTimer.singleShot(delay_ms, checker.check_async)
