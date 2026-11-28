"""Read this isolated Windows CI process working set; no extra dependency."""


def rss_bytes():
    import ctypes as c
    from ctypes import wintypes as w

    class Counters(c.Structure):
        _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD)] + [
            (name, c.c_size_t)
            for name in (
                'PeakWorkingSetSize',
                'WorkingSetSize',
                'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage',
                'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage',
                'PagefileUsage',
                'PeakPagefileUsage',
            )
        ]

    kernel, api = c.windll.kernel32, c.windll.psapi
    kernel.GetCurrentProcess.restype = w.HANDLE
    values = Counters()
    values.cb = c.sizeof(values)
    api.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Counters), w.DWORD]
    if not api.GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), c.byref(values), values.cb
    ):
        raise c.WinError()
    return values.WorkingSetSize
