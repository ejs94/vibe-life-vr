#!/usr/bin/env python3
"""Hide the Monado compositor target window from the desktop during tests.

The Monado windowed fallback shows a black target window in this environment.
The engine eye dumps remain the evidence; the target window is only visual
clutter. This helper waits for the window and unmaps it without stopping the
Monado service.
"""

from __future__ import annotations

import time

from Xlib import display


def find_windows(window, depth=0):
    found = []
    try:
        if window.get_wm_name() == "Monado":
            found.append(window)
        for child in window.query_tree().children:
            found.extend(find_windows(child, depth + 1))
    except Exception:
        pass
    return found


def main() -> int:
    deadline = time.time() + 20.0
    while time.time() < deadline:
        try:
            d = display.Display()
            root = d.screen().root
            windows = find_windows(root)
            if windows:
                for w in windows:
                    w.unmap()
                d.sync()
                print(f"[hide-monado] unmapped {len(windows)} Monado window(s)")
                return 0
        except Exception:
            pass
        time.sleep(0.5)
    print("[hide-monado] no Monado window found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
