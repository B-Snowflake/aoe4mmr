#!/usr/bin/env python3 
# Author: B_Snowflake 
# Date: 2026/5/24 21:51:28 
# LastEditTime: 2026/5/24 21:51:28

import os
import sys
import logging
import threading
from pathlib import Path
import traceback
from src.aoe4mmr import Aoe4mmr, MouseFilter
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import QApplication


app_name = "Aoe4mmr"
base_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) / app_name
if not base_path.exists():
    os.makedirs(base_path, exist_ok=True)
log_path = base_path / "error.log"
if log_path.exists() and log_path.stat().st_size > 1_000_000:
    log_path.unlink()
logging.basicConfig(filename=log_path, level=logging.ERROR, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def handle_exception(exc_type, exc_value, exc_traceback):
    # Ctrl+C 不记录
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
sys.excepthook = handle_exception


def thread_exception_handler(args):
    logger.error(
        f"Uncaught threading exception in {args.thread.native_id}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)                                                                                                                                                                                                                                                                                                                                                                                        
    )
    traceback.print_exception(
        args.exc_type, args.exc_value, args.exc_traceback
    )

threading.excepthook = thread_exception_handler
    
    
if __name__ == "__main__":
    pid_path = base_path / "pid"
    # 仅单实例运行，启动时校验实例是否已经运行
    if Aoe4mmr.is_process_running(pid_path):
        app = QApplication(sys.argv)
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        window = Aoe4mmr(base_path, pid_path, app_name)
        mouse_filter = MouseFilter()
        mouse_filter.backward_forward_signal.connect(window.backward_forward)
        app.installEventFilter(mouse_filter)
        app.exec()
    else:
        print("Another instance is already running.")