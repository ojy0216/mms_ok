"""SDK 6 fakes intentionally have none of the removed SDK 5 methods."""

import gc
import types
import weakref

import pytest

from mms_ok import bist, cli, devices, doctor, fpga_base, fpga_factory, ok_setup
from mms_ok.fpga_xem7310 import XEM7310
from mms_ok.fpga_xem7360 import XEM7360


class ClassicPort:
    def __init__(self, device):
        self.device = weakref.ref(device)
        self.wire = 0

    def SetWireInValue(self, addr, value, mask):
        self.wire = value & mask
        return 0

    def UpdateWireIns(self):
        return 0

    def UpdateWireOuts(self):
        return 0

    def GetWireOutValue(self, addr):
        return self.wire

    def ActivateTriggerIn(self, addr, bit):
        return 0

    def UpdateTriggerOuts(self):
        return 0

    def IsTriggered(self, addr, mask):
        return True

    def WriteToPipeIn(self, addr, data):
        return self.device().state.transfer_error or len(data)

    def ReadFromPipeOut(self, addr, data):
        data[:] = b'\x11' * len(data)
        return len(data)

    def WriteToBlockPipeIn(self, addr, block_size, data):
        return len(data)

    def ReadFromBlockPipeOut(self, addr, block_size, data):
        data[:] = b'\x22' * len(data)
        return len(data)

    def WriteRegister(self, addr, value):
        self.device().register = value
        return 0

    def ReadRegister(self, addr):
        if self.device().state.register_error:
            raise RuntimeError('native read failed')
        return self.device().register


class Device:
    # No GetErrorString, product constants, discovery, opening, or endpoint I/O.
    @staticmethod
    def GetErrorMessage(code):
        return 'sdk6 error {}'.format(code)

    def __init__(self, state, serial):
        self.state = state
        self.serial = serial
        self.open = True
        self.close_calls = 0
        self.configured = []
        self.port_calls = 0
        self.last_error_calls = 0
        self.settings_calls = 0
        self.register = 0
        self.port = ClassicPort(self)

    def IsOpen(self):
        return self.open

    def Close(self):
        self.close_calls += 1
        self.open = False

    def GetDeviceInfo(self, info):
        if self.state.info_error:
            return -9
        board = self.state.boards[self.serial]
        info.serialNumber = self.state.reported_serial or self.serial
        info.productID, info.productName = board
        info.deviceID = 'test board'
        info.deviceInterface = 3
        info.usbSpeed = 2  # High-Speed USB3-capable board
        info.wireWidth = info.triggerWidth = info.pipeWidth = 32
        return 0

    def ConfigureFPGA(self, path):
        self.configured.append(path)
        return self.state.configure_error

    def IsFrontPanelEnabled(self):
        return self.state.enabled

    def GetFPGADataPortClassic(self):
        assert self.configured
        assert not self.state.configure_error
        self.port_calls += 1
        if self.state.port_error:
            raise RuntimeError('no classic port')
        return self.port

    def GetLastError(self):
        self.last_error_calls += 1
        return self.state.last_error

    def GetDeviceSettings(self, settings):
        self.settings_calls += 1
        return 0


@pytest.fixture
def sdk6(monkeypatch):
    state = types.SimpleNamespace(
        boards={'A200': (201, 'XEM7310-A200')}, handles=[], opens=[],
        configure_error=0, info_error=False, enabled=True, port_error=False,
        reported_serial=None, last_error=0, register_error=False, transfer_error=0,
    )

    class Manager:
        def GetCount(self):
            return len(state.boards)

        def GetSerial(self, index):
            return list(state.boards)[index]

        def Open(self, serial=''):
            serial = serial or next(iter(state.boards), '')
            state.opens.append(serial)
            if serial not in state.boards:
                return None
            handle = Device(state, serial)
            state.handles.append(handle)
            return handle

    ok = types.SimpleNamespace(
        okCFrontPanel=Device, FrontPanelDevices=Manager,
        okTDeviceInfo=types.SimpleNamespace, OK_INTERFACE_USB3=3,
        OK_PRODUCT_XEM7310A75=200, OK_PRODUCT_XEM7310A200=201,
        OK_PRODUCT_XEM7360K160T=300,
        GetAPIVersionString=lambda: '6.1.0',
        okCDeviceSettings=lambda: types.SimpleNamespace(GetInt=lambda key: 120),
    )
    state.ok = ok
    monkeypatch.setattr(ok_setup, '_ok_module', ok)
    monkeypatch.setattr(devices, 'import_ok', lambda: ok)
    monkeypatch.setattr(fpga_base, 'print_fpga_overview', lambda **kwargs: None)
    return state


@pytest.fixture
def bitstream(tmp_path):
    path = tmp_path / 'test.bit'
    path.write_bytes(b'test')
    return str(path)


def test_discovery_and_doctor_use_v6_manager_and_close_handles(sdk6):
    found = devices.list_devices()
    assert found[0].as_dict() == dict(serial='A200', model='XEM7310-A200', device_id='test board', product_id=201)
    assert doctor._get_device_count(sdk6.ok) == (1, None)
    assert sdk6.handles[0].close_calls == 1
    assert not hasattr(Device, 'OpenBySerial')
    assert not hasattr(Device, 'SetWireInValue')
    assert not hasattr(Device, 'GetErrorString')


@pytest.mark.parametrize('product,model,cls', [
    (200, 'XEM7310-A75', XEM7310), (201, 'XEM7310-A200', XEM7310),
    (300, 'XEM7360-K160T', XEM7360),
])
def test_auto_select_and_board_classes_use_module_product_constants(sdk6, bitstream, product, model, cls):
    sdk6.boards['A200'] = (product, model)
    with fpga_factory.XEM(bitstream, serial='A200') as fpga:
        assert isinstance(fpga, cls)
        assert fpga.xem is sdk6.handles[-1]
        assert fpga.xem.port_calls == 1
        if cls is XEM7360:
            assert fpga.xem.settings_calls == 1
    assert all(h.close_calls == 1 for h in sdk6.handles)
    assert not hasattr(sdk6.ok, 'brdXEM7310A200')


def test_all_endpoint_operations_route_to_classic_port(sdk6, bitstream):
    with XEM7310(bitstream, serial='A200') as fpga:
        fpga.SetWireInValue(0, 42)
        assert fpga.GetWireOutValue(0x20) == 42
        fpga.ActivateTriggerIn(0x40, 0)
        assert fpga.IsTriggered(0x60, 1)
        assert fpga.WriteToPipeIn(0x80, bytearray(16)) == 16
        assert fpga.ReadFromPipeOut(0xA0, 16).raw_data == bytearray(b'\x11' * 16)
        assert fpga.WriteToBlockPipeIn(0x80, bytearray(16)) == 16
        assert fpga.ReadFromBlockPipeOut(0xA0, 16).raw_data == bytearray(b'\x22' * 16)
        fpga.WriteRegister(0, 123)
        assert fpga.ReadRegister(0) == 123
        assert fpga.xem.last_error_calls == 1
        retained_port = fpga.wire_ops.xem
    with pytest.raises(RuntimeError, match='closed'):
        retained_port.UpdateWireIns()


def test_port_keeps_device_alive_and_finalizer_closes_it(sdk6, bitstream):
    fpga = XEM7310(bitstream)
    port = fpga.wire_ops.xem
    ref = weakref.ref(fpga.xem)
    sdk6.handles.clear()
    del fpga
    gc.collect()
    assert ref() is port.device
    assert ref().close_calls == 1


@pytest.mark.parametrize('stage', ['configure', 'info', 'enabled', 'port'])
def test_initialization_failure_closes_device(sdk6, bitstream, stage):
    if stage == 'configure':
        sdk6.configure_error = -7
    elif stage == 'info':
        sdk6.info_error = True
    elif stage == 'enabled':
        sdk6.enabled = False
    else:
        sdk6.port_error = True
    with pytest.raises(RuntimeError):
        XEM7310(bitstream)
    handle = sdk6.handles[0]
    assert handle.close_calls == 1
    assert handle.port_calls == (1 if stage == 'port' else 0)


@pytest.mark.parametrize('identity', ['serial', 'product'])
def test_identity_mismatch_prevents_configuration_and_closes(sdk6, bitstream, identity):
    if identity == 'serial':
        sdk6.reported_serial = 'OTHER'
    with pytest.raises(fpga_base.ProductIDMismatchError):
        XEM7310(bitstream, serial='A200', _expected_product_id=200)
    assert sdk6.handles[0].configured == []
    assert sdk6.handles[0].close_calls == 1


def test_error_messages_and_last_error_stay_on_device(sdk6, bitstream):
    with XEM7310(bitstream) as fpga:
        sdk6.transfer_error = -8
        with pytest.raises(RuntimeError, match='sdk6 error -8'):
            fpga.WriteToPipeIn(0x80, bytearray(16))
        sdk6.last_error = -9
        with pytest.raises(RuntimeError, match='sdk6 error -9'):
            fpga.GetWireOutValue(0x20)
        sdk6.register_error = True
        with pytest.raises(RuntimeError, match='sdk6 error -9'):
            fpga.ReadRegister(0)
        assert fpga.xem.last_error_calls == 2


def test_missing_serial_does_not_create_device(sdk6, bitstream):
    with pytest.raises(ConnectionError, match='MISSING'):
        XEM7310(bitstream, serial='MISSING')
    assert sdk6.handles == []


def test_bist_requires_choice_for_multiple_boards_and_preserves_identity(sdk6):
    sdk6.boards['K160T'] = (300, 'XEM7360-K160T')
    with pytest.raises(fpga_factory.FPGASelectionError, match='Multiple.*serial'):
        bist.BIST()
    assert not any(h.configured for h in sdk6.handles)
    test = bist.BIST(serial='A200')
    with test._create_fpga() as fpga:
        assert fpga.config.serial_number == 'A200'
        assert fpga.config.product_id == 201
        assert fpga._bitstream_path.endswith('A200_boardtest.bit')
    sdk6.boards['A200'] = (200, 'XEM7310-A75')
    with pytest.raises(fpga_base.ProductIDMismatchError):
        test._create_fpga()
    assert sdk6.handles[-1].configured == []
    assert all(h.close_calls == 1 for h in sdk6.handles)


def test_bist_selects_single_board_and_rejects_missing(sdk6):
    test = bist.BIST()
    assert test.config.serial_number == 'A200'
    with pytest.raises(fpga_factory.FPGASelectionError, match='MISSING'):
        bist.BIST(serial='MISSING')
    sdk6.boards.clear()
    with pytest.raises(fpga_factory.FPGASelectionError, match='No Opal Kelly'):
        bist.BIST()


def test_cli_serial_and_selection_failure(sdk6, monkeypatch, capsys):
    args = cli.build_parser().parse_args(['bist', '--serial', 'A200'])
    assert args.serial == 'A200'
    assert cli.main(['bist', '--serial', 'MISSING']) == cli.EXIT_BIST_FAILED
    assert 'MISSING' in capsys.readouterr().out
    monkeypatch.setattr(bist.BIST, 'run_test', lambda self: self.config.serial_number == 'A200')
    assert cli.main(['bist', '--serial', 'A200']) == 0
