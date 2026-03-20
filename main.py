#!/usr/bin/env python3
"""
BusTimer — entry point.

Usage:
  python main.py

Environment variables (set in /etc/bustimer.env):
  QT_QPA_PLATFORM=eglfs
  QT_QPA_EGLFS_KMS_CONFIG=/etc/kiosk-eglfs.json
  DISPLAY=:0  (for desktop testing)
"""

import logging
import os
import sys

from PyQt6.QtCore import QUrl, QObject, pyqtSlot, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

from bus_model import BusModel
from data_fetcher import DataFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


class ContextBridge(QObject):
    """Lives on the GUI thread; updates QML context properties safely."""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self._ctx = ctx

    @pyqtSlot(str)
    def setAlert(self, text: str):
        self._ctx.setContextProperty("alertText", text)

    @pyqtSlot(str)
    def setStatus(self, text: str):
        self._ctx.setContextProperty("dataStatus", text)


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("BusTimer")

    engine = QQmlApplicationEngine()

    model = BusModel()
    ctx = engine.rootContext()
    ctx.setContextProperty("busModel", model)
    ctx.setContextProperty("alertText", "")
    ctx.setContextProperty("dataStatus", "")

    qml_file = os.path.join(os.path.dirname(__file__), "bustimer.qml")
    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        log.error("Failed to load QML — exiting")
        sys.exit(1)

    bridge = ContextBridge(ctx)
    fetcher = DataFetcher(model)

    # Queued connections ensure slots run on GUI thread
    fetcher.alertChanged.connect(bridge.setAlert, Qt.ConnectionType.QueuedConnection)
    fetcher.statusChanged.connect(bridge.setStatus, Qt.ConnectionType.QueuedConnection)
    fetcher.start()

    log.info("BusTimer started — window 800×480")
    ret = app.exec()

    fetcher.quit()
    fetcher.wait(3000)
    sys.exit(ret)


if __name__ == "__main__":
    main()
