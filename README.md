# Mouse To W/S A/D Mapper

Windows-only Python script for the first stage of the maze control setup:

- one selected physical mouse stops rotating the camera;
- its vertical motion is translated into `W` and `S`;
- a second selected mouse can use the same up/down motion to drive `A` and `D`;
- all other mice continue to work normally.

## Why the script uses Interception

On Windows, `Raw Input` can distinguish between multiple mice, but it does not reliably suppress the chosen mouse for another application's camera. For this reason the script uses the [Interception](https://github.com/oblitum/Interception) driver, which can intercept mouse input before the game receives it.

## Requirements

- Windows
- Python 3.11+
- Installed [Interception](https://github.com/oblitum/Interception) driver

```powershell
.\install-interception.exe /install
```

The driver installation itself must be done from an Administrator console.

## Usage

1. Install the Interception driver.
2. List mice:

```powershell
python .\mouse_to_wsad.py --list
```

3. If the HID names are unclear, identify the slot live:

```powershell
python .\mouse_to_wsad.py --probe
```

Then move each mouse one by one and watch which `slot` number is printed.

4. Start mapping for the chosen mouse:

```powershell
python .\mouse_to_wsad.py --device 11
```

Two-mouse mode:

```powershell
python .\mouse_to_wsad.py --ws-device 11 --ad-device 12
```

In this mode both mice use vertical up/down motion:

- mouse `11`: up -> `W`, down -> `S`
- mouse `12`: up -> `D`, down -> `A`

Useful flags:

- `--threshold 3` for a less sensitive trigger
- `--release-ms 70` if `W`/`S` is released too quickly
- `--invert-all` if you want to swap directions for both mice at once
- `--invert` if up/down feels reversed
- `--ad-invert` if the `A`/`D` mouse feels reversed

## Emergency stop

Press `F12` to stop the mapper and release `W` and `S`.

