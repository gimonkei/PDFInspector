from __future__ import annotations

import uuid
import weakref


class WindowRegistry:
    _windows = {}

    @classmethod
    def register(cls, window):
        window_id = str(uuid.uuid4())
        cls._windows[window_id] = weakref.ref(window)
        return window_id

    @classmethod
    def unregister(cls, window_id):
        cls._windows.pop(str(window_id), None)

    @classmethod
    def get(cls, window_id):
        reference = cls._windows.get(str(window_id))
        if reference is None:
            return None
        window = reference()
        if window is None:
            cls.unregister(window_id)
        return window

    @classmethod
    def all_windows(cls):
        result = []
        stale = []
        for window_id, reference in cls._windows.items():
            window = reference()
            if window is None:
                stale.append(window_id)
            else:
                result.append(window)
        for window_id in stale:
            cls.unregister(window_id)
        return result
