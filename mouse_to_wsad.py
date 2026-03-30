"""Map one physical mouse to W/S on Windows using the Interception driver.

This script is aimed at the first step of your setup:
the selected mouse no longer rotates the camera and instead its vertical
movement emulates W/S. Other mice keep working normally.

Examples:
    python mouse_to_wsad.py --list
    python mouse_to_wsad.py --device 11
    python mouse_to_wsad.py --ws-device 11 --ad-device 12
    python mouse_to_wsad.py --ws-device 11 --ad-device 12 --threshold 3 --release-ms 70

Emergency stop:
    Press F12 to stop the mapper and release W/S.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from ctypes import wintypes
from enum import IntFlag


if sys.platform != "win32":
    raise SystemExit("This script only works on Windows.")


LPVOID = ctypes.c_void_p
ULONG_PTR = wintypes.WPARAM

GENERIC_READ = 0x80000000
OPEN_EXISTING = 3

WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF

IOCTL_SET_EVENT = 0x222040
IOCTL_SET_FILTER = 0x222010
IOCTL_GET_HARDWARE_ID = 0x222200
IOCTL_READ = 0x222100
IOCTL_WRITE = 0x222080

MIN_DEVICE = 1
MAX_DEVICE = 20
MIN_MOUSE = 11
MAX_MOUSE = 20

MAPVK_VK_TO_VSC = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

VK_W = 0x57
VK_S = 0x53
VK_A = 0x41
VK_D = 0x44
VK_F12 = 0x7B

KEY_NAMES = {
    VK_W: "W",
    VK_S: "S",
    VK_A: "A",
    VK_D: "D",
}

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


class MouseFilter(IntFlag):
    ALL = 0xFFFF


class MouseFlags(IntFlag):
    ATTRIBUTES_CHANGED = 0x0004


class MouseStroke(ctypes.Structure):
    _fields_ = [
        ("unit_id", wintypes.USHORT),
        ("flags", wintypes.USHORT),
        ("state", wintypes.USHORT),
        ("rolling", ctypes.c_short),
        ("raw_buttons", wintypes.ULONG),
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
        ("information", wintypes.ULONG),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]


CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
CreateFileW.restype = wintypes.HANDLE

CreateEventW = kernel32.CreateEventW
CreateEventW.argtypes = [LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
CreateEventW.restype = wintypes.HANDLE

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    LPVOID,
    wintypes.DWORD,
    LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    LPVOID,
]
DeviceIoControl.restype = wintypes.BOOL

WaitForMultipleObjects = kernel32.WaitForMultipleObjects
WaitForMultipleObjects.argtypes = [
    wintypes.DWORD,
    ctypes.POINTER(wintypes.HANDLE),
    wintypes.BOOL,
    wintypes.DWORD,
]
WaitForMultipleObjects.restype = wintypes.DWORD

MapVirtualKeyW = user32.MapVirtualKeyW
MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
MapVirtualKeyW.restype = wintypes.UINT

SendInput = user32.SendInput
SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = wintypes.UINT

GetAsyncKeyState = user32.GetAsyncKeyState
GetAsyncKeyState.argtypes = [ctypes.c_int]
GetAsyncKeyState.restype = ctypes.c_short


def raise_last_winerror() -> None:
    raise ctypes.WinError(ctypes.get_last_error())


def close_handle(handle: int | None) -> None:
    if handle and handle != INVALID_HANDLE_VALUE:
        CloseHandle(handle)


def device_io_control(
    handle: int,
    code: int,
    in_buffer: ctypes.Array | ctypes.Structure | None = None,
    out_buffer: ctypes.Array | ctypes.Structure | None = None,
) -> int:
    bytes_returned = wintypes.DWORD()
    in_pointer = ctypes.byref(in_buffer) if in_buffer is not None else None
    out_pointer = ctypes.byref(out_buffer) if out_buffer is not None else None
    in_size = ctypes.sizeof(in_buffer) if in_buffer is not None else 0
    out_size = ctypes.sizeof(out_buffer) if out_buffer is not None else 0

    ok = DeviceIoControl(
        handle,
        code,
        in_pointer,
        in_size,
        out_pointer,
        out_size,
        ctypes.byref(bytes_returned),
        None,
    )
    if not ok:
        raise_last_winerror()
    return bytes_returned.value


class InterceptionDevice:
    def __init__(self, number: int) -> None:
        self.number = number
        self.is_mouse = MIN_MOUSE <= number <= MAX_MOUSE

        path = rf"\\.\interception{number - 1:02d}"
        self.handle = CreateFileW(path, GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
        if not self.handle or self.handle == INVALID_HANDLE_VALUE:
            raise_last_winerror()

        self.event = CreateEventW(None, True, False, None)
        if not self.event:
            close_handle(self.handle)
            raise_last_winerror()

        event_payload = (wintypes.HANDLE * 2)(self.event, 0)
        try:
            device_io_control(self.handle, IOCTL_SET_EVENT, in_buffer=event_payload)
        except Exception:
            self.close()
            raise

        self.stroke = MouseStroke()

    def close(self) -> None:
        close_handle(self.event)
        close_handle(self.handle)
        self.event = None
        self.handle = None

    def receive(self) -> MouseStroke:
        device_io_control(self.handle, IOCTL_READ, out_buffer=self.stroke)
        return self.stroke

    def send(self, stroke: MouseStroke | None = None) -> None:
        device_io_control(self.handle, IOCTL_WRITE, in_buffer=stroke or self.stroke)

    def set_filter(self, filter_value: int) -> None:
        filter_buffer = wintypes.USHORT(filter_value)
        device_io_control(self.handle, IOCTL_SET_FILTER, in_buffer=filter_buffer)

    def get_hardware_id(self) -> str:
        hardware_id = ctypes.create_unicode_buffer(512)
        try:
            device_io_control(self.handle, IOCTL_GET_HARDWARE_ID, out_buffer=hardware_id)
        except OSError:
            return ""
        return hardware_id.value


class InterceptionContext:
    def __init__(self) -> None:
        self.devices: list[InterceptionDevice] = []
        try:
            for number in range(MIN_DEVICE, MAX_DEVICE + 1):
                self.devices.append(InterceptionDevice(number))
        except OSError as exc:
            self.close()
            raise RuntimeError(
                "Interception driver is not installed. Install it as Administrator "
                "and then rerun the script."
            ) from exc

        self.events = (wintypes.HANDLE * MAX_DEVICE)(*(device.event for device in self.devices))

    def close(self) -> None:
        for device in self.devices:
            device.close()
        self.devices.clear()

    def set_mouse_filter(self, filter_value: int) -> None:
        for device in self.devices:
            if device.is_mouse:
                device.set_filter(filter_value)

    def get_device(self, number: int) -> InterceptionDevice:
        return self.devices[number - 1]

    def wait(self, timeout_ms: int = INFINITE) -> InterceptionDevice | None:
        result = WaitForMultipleObjects(MAX_DEVICE, self.events, False, timeout_ms)
        if result == WAIT_TIMEOUT:
            return None
        if result == WAIT_FAILED:
            raise_last_winerror()
        if result >= MAX_DEVICE:
            raise RuntimeError(f"Unexpected wait result: {result}")
        return self.devices[result]

    def wait_receive(self, timeout_ms: int = INFINITE) -> InterceptionDevice | None:
        device = self.wait(timeout_ms)
        if device is not None:
            device.receive()
        return device


class KeyboardSender:
    def __init__(self) -> None:
        self.held: set[int] = set()
        self.scan_codes = {
            VK_W: self._scan_code(VK_W),
            VK_S: self._scan_code(VK_S),
            VK_A: self._scan_code(VK_A),
            VK_D: self._scan_code(VK_D),
        }

    @staticmethod
    def _scan_code(vk: int) -> int:
        scan_code = MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        if scan_code == 0:
            raise RuntimeError(f"Could not resolve scan code for VK={vk}.")
        return scan_code

    def _send(self, vk: int, key_up: bool) -> None:
        input_record = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=0,
                wScan=self.scan_codes[vk],
                dwFlags=KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0),
                time=0,
                dwExtraInfo=0,
            ),
        )
        sent = SendInput(1, ctypes.byref(input_record), ctypes.sizeof(INPUT))
        if sent != 1:
            raise_last_winerror()

    def press(self, vk: int) -> None:
        if vk not in self.held:
            self._send(vk, key_up=False)
            self.held.add(vk)

    def release(self, vk: int) -> None:
        if vk in self.held:
            self._send(vk, key_up=True)
            self.held.remove(vk)

    def release_all(self) -> None:
        self.release(VK_W)
        self.release(VK_S)
        self.release(VK_A)
        self.release(VK_D)


class VerticalMouseMapping:
    def __init__(
        self,
        device: InterceptionDevice,
        keyboard: KeyboardSender,
        up_key: int,
        down_key: int,
        threshold: int,
        release_ms: int,
        invert: bool,
        label: str,
    ) -> None:
        self.device = device
        self.keyboard = keyboard
        self.up_key = down_key if invert else up_key
        self.down_key = up_key if invert else down_key
        self.threshold = max(1, threshold)
        self.release_after = max(1, release_ms) / 1000.0
        self.label = label
        self.last_motion_at = 0.0
        self.active_direction = 0

    def describe(self) -> str:
        hardware_id = self.device.get_hardware_id() or "<unknown mouse>"
        return (
            f"{self.label}: mouse {self.device.number} | "
            f"up -> {KEY_NAMES[self.up_key]}, down -> {KEY_NAMES[self.down_key]} | "
            f"{hardware_id}"
        )

    def handle_stroke(self, stroke: MouseStroke, now: float) -> MouseStroke | None:
        direction = self._direction_from_vertical_motion(stroke.y)
        if direction != 0:
            self.last_motion_at = now
            self._apply_direction(direction)

        return self._without_movement(stroke)

    def _direction_from_vertical_motion(self, delta_y: int) -> int:
        if delta_y <= -self.threshold:
            return -1
        if delta_y >= self.threshold:
            return 1
        return 0

    def _apply_direction(self, direction: int) -> None:
        if direction == self.active_direction:
            return

        if direction < 0:
            self.keyboard.press(self.up_key)
            self.keyboard.release(self.down_key)
        else:
            self.keyboard.press(self.down_key)
            self.keyboard.release(self.up_key)

        self.active_direction = direction

    def release_if_idle(self, now: float) -> None:
        if self.active_direction == 0:
            return
        if now - self.last_motion_at >= self.release_after:
            self.release()

    def release(self) -> None:
        self.keyboard.release(self.up_key)
        self.keyboard.release(self.down_key)
        self.active_direction = 0

    @staticmethod
    def _without_movement(stroke: MouseStroke) -> MouseStroke | None:
        passthrough = MouseStroke()
        ctypes.pointer(passthrough)[0] = stroke
        passthrough.x = 0
        passthrough.y = 0

        if (
            passthrough.state == 0
            and passthrough.rolling == 0
            and passthrough.raw_buttons == 0
            and (passthrough.flags & int(MouseFlags.ATTRIBUTES_CHANGED)) == 0
        ):
            return None

        return passthrough

    @staticmethod
    def _stop_requested() -> bool:
        return bool(GetAsyncKeyState(VK_F12) & 0x8000)


class MultiMouseMapper:
    def __init__(self, context: InterceptionContext, mappings: list[VerticalMouseMapping]) -> None:
        self.context = context
        self.mappings = mappings
        self.mapping_by_device = {mapping.device.number: mapping for mapping in mappings}
        self.keyboard = mappings[0].keyboard if mappings else KeyboardSender()

    def run(self) -> None:
        print("Active mappings:")
        for mapping in self.mappings:
            print(mapping.describe())
        print("All mapped mice swallow their movement, so they should not rotate the camera.")
        print("Press F12 to stop.\n")

        self.context.set_mouse_filter(int(MouseFilter.ALL))

        try:
            while True:
                if VerticalMouseMapping._stop_requested():
                    break

                device = self.context.wait_receive(timeout_ms=10)
                now = time.monotonic()

                if device is None:
                    self._release_if_idle(now)
                    continue

                if not device.is_mouse:
                    continue

                mapping = self.mapping_by_device.get(device.number)
                if mapping is None:
                    device.send()
                    continue

                passthrough = mapping.handle_stroke(device.stroke, now)
                if passthrough is not None:
                    device.send(passthrough)

                self._release_if_idle(now)
        finally:
            self.keyboard.release_all()

    def _release_if_idle(self, now: float) -> None:
        for mapping in self.mappings:
            mapping.release_if_idle(now)


def probe_mice(context: InterceptionContext) -> int:
    print("Probe mode: move or click the mouse you want to identify.")
    print("For each activity the script will print the slot number and HID.")
    print("Press F12 to stop.\n")

    context.set_mouse_filter(int(MouseFilter.ALL))
    last_printed: dict[int, float] = {}

    while True:
        if GetAsyncKeyState(VK_F12) & 0x8000:
            print("\nProbe stopped.")
            return 0

        device = context.wait_receive(timeout_ms=50)
        if device is None or not device.is_mouse:
            continue

        now = time.monotonic()
        last_time = last_printed.get(device.number, 0.0)
        if now - last_time >= 0.20:
            hardware_id = device.get_hardware_id() or "<unknown mouse>"
            print(
                f"slot {device.number}: x={device.stroke.x:+d} "
                f"y={device.stroke.y:+d} state={device.stroke.state} "
                f"id={hardware_id}"
            )
            last_printed[device.number] = now

        device.send()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Map one selected mouse to W/S and swallow its camera movement."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available mouse slots and their hardware IDs.",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Single-mouse mode: map this mouse to W/S.",
    )
    parser.add_argument(
        "--ws-device",
        type=int,
        help="Mouse device number for W/S.",
    )
    parser.add_argument(
        "--ad-device",
        type=int,
        help="Mouse device number for A/D. This mouse also uses up/down motion.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Print the slot of each mouse when it moves, to identify the correct device.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=2,
        help="Minimum absolute Y delta to treat as movement. Default: 2.",
    )
    parser.add_argument(
        "--release-ms",
        type=int,
        default=60,
        help="Release the active key after this many milliseconds without movement. Default: 60.",
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Swap directions for the W/S mouse if the controls feel reversed.",
    )
    parser.add_argument(
        "--invert-all",
        action="store_true",
        help="Swap directions for all configured mice at once.",
    )
    parser.add_argument(
        "--ad-invert",
        action="store_true",
        help="Swap directions for the A/D mouse if the controls feel reversed.",
    )
    return parser


def list_mice(context: InterceptionContext) -> int:
    print("Mouse slots:")
    found = False
    for number in range(MIN_MOUSE, MAX_MOUSE + 1):
        device = context.get_device(number)
        hardware_id = device.get_hardware_id()
        if hardware_id:
            found = True
            print(f"  {number}: {hardware_id}")

    if not found:
        print("  No active mice were detected by the Interception driver.")
        print("  Try reconnecting the mice and run the command again.")
        return 1

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ws_device = args.ws_device if args.ws_device is not None else args.device

    if not args.list and not args.probe and ws_device is None and args.ad_device is None:
        parser.error("specify --list, --probe, --device, --ws-device, or --ad-device")

    for flag_name, value in (
        ("--device", args.device),
        ("--ws-device", args.ws_device),
        ("--ad-device", args.ad_device),
    ):
        if value is not None and not (MIN_MOUSE <= value <= MAX_MOUSE):
            parser.error(f"{flag_name} must be a number from 11 to 20")

    if ws_device is not None and args.ad_device is not None and ws_device == args.ad_device:
        parser.error("--ws-device and --ad-device must use different mice")

    try:
        context = InterceptionContext()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        print(
            "Download and install Interception first: "
            "https://github.com/oblitum/Interception",
            file=sys.stderr,
        )
        return 1

    try:
        if args.list:
            return list_mice(context)

        if args.probe:
            return probe_mice(context)

        keyboard = KeyboardSender()
        mappings: list[VerticalMouseMapping] = []
        ws_invert = bool(args.invert_all) ^ bool(args.invert)
        ad_invert = bool(args.invert_all) ^ bool(args.ad_invert)

        if ws_device is not None:
            mappings.append(
                VerticalMouseMapping(
                    device=context.get_device(ws_device),
                    keyboard=keyboard,
                    up_key=VK_W,
                    down_key=VK_S,
                    threshold=args.threshold,
                    release_ms=args.release_ms,
                    invert=ws_invert,
                    label="W/S",
                )
            )

        if args.ad_device is not None:
            mappings.append(
                VerticalMouseMapping(
                    device=context.get_device(args.ad_device),
                    keyboard=keyboard,
                    up_key=VK_D,
                    down_key=VK_A,
                    threshold=args.threshold,
                    release_ms=args.release_ms,
                    invert=ad_invert,
                    label="A/D",
                )
            )

        mapper = MultiMouseMapper(context=context, mappings=mappings)
        mapper.run()
        return 0
    finally:
        context.close()


if __name__ == "__main__":
    raise SystemExit(main())
