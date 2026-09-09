import os
import sys
import threading
def _doc_cpu_logical():
    try:
        n = os.cpu_count()
        return n if n and n > 0 else 4
    except Exception:
        return 4
def _doc_ram_windows():
    if sys.platform != "win32":
        return None, None
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        if stat.ullTotalPhys <= 0:
            return None, None
        ram_gb = stat.ullTotalPhys / (1024 ** 3)
        ram_avail_gb = stat.ullAvailPhys / (1024 ** 3)
        return ram_gb, ram_avail_gb
    except Exception:
        return None, None
def _doc_ram_khac_windows():
    try:
        import psutil
        vm = psutil.virtual_memory()
        return vm.total / (1024 ** 3), vm.available / (1024 ** 3)
    except Exception:
        return 8.0, 4.0
_CPU_LOGICAL = _doc_cpu_logical()
_RAM_GB, _RAM_AVAIL_GB = _doc_ram_windows()
if _RAM_GB is None:
    _RAM_GB, _RAM_AVAIL_GB = _doc_ram_khac_windows()
def ram_avail_gb_hien_tai():
    global _RAM_AVAIL_GB
    ram_gb, ram_avail_gb = _doc_ram_windows()
    if ram_gb is None:
        return _RAM_AVAIL_GB
    _RAM_AVAIL_GB = ram_avail_gb
    return ram_avail_gb
PROFILE = {
    "weak":   {"tai_modrinth": 4,  "tai_curseforge": 3, "tai_icon": 2, "doc_jar": 2, "hash": 1},
    "normal": {"tai_modrinth": 8,  "tai_curseforge": 5, "tai_icon": 3, "doc_jar": 4, "hash": 2},
    "strong": {"tai_modrinth": 12, "tai_curseforge": 8, "tai_icon": 4, "doc_jar": 4, "hash": 2},
}
_CO_CHUNG = {
    "batch_api": True,
    "hash_khi_co_project_id": False,
    "cat_nen_khi_choi": True,
}
TEN_PROFILE_HIEN_THI = {
    "auto": "Tự động",
    "weak": "Nhẹ",
    "normal": "Cân bằng",
    "strong": "Mạnh",
}
_HIEN_THI_TOI_PROFILE = {v: k for k, v in TEN_PROFILE_HIEN_THI.items()}
def _phat_hien_profile_tu_dong():
    if _RAM_GB <= 8 or _CPU_LOGICAL <= 4:
        return "weak"
    if _CPU_LOGICAL >= 12 and _RAM_GB >= 16:
        return "strong"
    return "normal"
_PROFILE_TU_DONG = _phat_hien_profile_tu_dong()
def profile_hien_tai():
    try:
        import config
        chon = config.current_config.get("perf_profile", "auto")
    except Exception:
        chon = "auto"
    if chon in PROFILE:
        return chon
    return _PROFILE_TU_DONG
def get_perf():
    profile = profile_hien_tai()
    perf = dict(PROFILE[profile])
    perf.update(_CO_CHUNG)
    perf["profile"] = profile
    perf["cpu_logical"] = _CPU_LOGICAL
    perf["ram_gb"] = _RAM_GB
    perf["ram_avail_gb"] = _RAM_AVAIL_GB
    perf["icon_luc_cai"] = (profile != "weak")
    return perf
_dang_choi_event = threading.Event()
def bat_dau_choi():
    _dang_choi_event.set()
def ket_thuc_choi():
    _dang_choi_event.clear()
def dang_choi():
    return _dang_choi_event.is_set()