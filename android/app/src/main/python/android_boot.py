# -*- coding: utf-8 -*-
"""Android 启动器：在 Chaquopy 内运行现有 server.py（不修改网页版任何文件）。"""
import os
import runpy
import sys
import threading
import traceback

_started = False


def start(root):
    global _started
    root = str(root)
    if _started:
        return "already"
    _started = True

    sys.dont_write_bytecode = True
    for p in (root, os.path.join(root, "vendor"),
              os.path.join(root, "engine"), os.path.join(root, "engine", "common")):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(root)

    def serve():
        try:
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            sys.argv = ["server.py", "--host", "127.0.0.1", "--port", "8899"]
            runpy.run_path(os.path.join(root, "server.py"), run_name="__main__")
        except SystemExit:
            pass
        except BaseException:
            traceback.print_exc()

    threading.Thread(target=serve, name="wanjie-server", daemon=True).start()
    return "started"
