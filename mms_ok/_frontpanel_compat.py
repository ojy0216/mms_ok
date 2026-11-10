"""Private adapters for the FrontPanel 5 and 6 binding APIs (``import ok``).

Keep the vendor module untouched. Device control always uses the device handle;
FrontPanel 6 endpoint I/O uses a Classic data port owned by that handle.
"""


def to_text(value):
    return value.decode(errors="replace") if isinstance(value, bytes) else str(value)


def is_frontpanel6(ok):
    return callable(getattr(ok, "FrontPanelDevices", None)) and not callable(
        getattr(ok.okCFrontPanel, "OpenBySerial", None)
    )


def error_message(ok, code):
    owner = ok.okCFrontPanel
    method = getattr(owner, "GetErrorString", None) or getattr(
        owner, "GetErrorMessage", None
    )
    return to_text(method(code)) if method else "FrontPanel error {}".format(code)


def product_id(ok, legacy_name):
    owner = ok.okCFrontPanel
    if hasattr(owner, legacy_name):
        return int(getattr(owner, legacy_name))
    name = "OK_PRODUCT_" + legacy_name[3:]
    if not hasattr(ok, name):
        raise AttributeError(
            "FrontPanel SDK is missing required product-id constants: {} / {}".format(
                legacy_name, name
            )
        )
    return int(getattr(ok, name))


def device_count(ok):
    discovery = ok.FrontPanelDevices() if is_frontpanel6(ok) else ok.okCFrontPanel()
    return discovery.GetCount() if is_frontpanel6(ok) else discovery.GetDeviceCount()


def device_serials(ok):
    if is_frontpanel6(ok):
        discovery = ok.FrontPanelDevices()
        return [
            (to_text(discovery.GetSerial(i)), "")
            for i in range(discovery.GetCount())
        ]
    discovery = ok.okCFrontPanel()
    return [
        (
            to_text(discovery.GetDeviceListSerial(i)),
            to_text(discovery.GetDeviceListModel(i)),
        )
        for i in range(discovery.GetDeviceCount())
    ]


def close_device(handle):
    if handle is None:
        return
    try:
        if handle.IsOpen():
            handle.Close()
    except Exception:
        try:
            handle.Close()
        except Exception:
            pass


def open_device(ok, serial=""):
    handle = None
    try:
        if is_frontpanel6(ok):
            handle = ok.FrontPanelDevices().Open(serial)
            if handle is None or not handle.IsOpen():
                raise ConnectionError(
                    "Device with serial {!r} is not opened! "
                    "(FrontPanelDevices.Open)".format(serial)
                )
        else:
            handle = ok.okCFrontPanel()
            code = handle.OpenBySerial(serial)
            if code:
                raise ConnectionError(
                    "Device with serial {!r} is not opened! "
                    "(OpenBySerial returned {})".format(serial, code)
                )
        return handle
    except BaseException:
        close_device(handle)
        raise


def read_device_info(ok, handle):
    info = ok.okTDeviceInfo()
    code = handle.GetDeviceInfo(info)
    if code is not None and code != 0:
        raise RuntimeError("GetDeviceInfo failed: " + error_message(ok, code))
    return info


class _ClassicDataPort:
    def __init__(self, device):
        # Hold the device strongly: the native port borrows its lifetime.
        self.device = device
        self.port = device.GetFPGADataPortClassic()
        if self.port is None:
            raise RuntimeError("FrontPanel Classic data port is unavailable")

    def GetLastError(self):
        return self.device.GetLastError()

    def __getattr__(self, name):
        if not self.device.IsOpen():
            raise RuntimeError("FrontPanel device is closed")
        return getattr(self.port, name)


def data_port(handle):
    if callable(getattr(handle, "GetFPGADataPortClassic", None)):
        return _ClassicDataPort(handle)
    return handle


def device_settings(ok, handle, settings):
    # Preserve the legacy class call, including older generated bindings.
    if is_frontpanel6(ok):
        return handle.GetDeviceSettings(settings)
    return ok.okCFrontPanel.GetDeviceSettings(handle, settings)
