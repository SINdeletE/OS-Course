#!/usr/bin/env python3
"""Local Ubuntu USB interface binding. Never unload the global usbhid driver."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

NAME = "xppen_mouse"
USB = Path("/sys/bus/usb")
RUNTIME = Path("/run/xppen-mouse")


class Bindings:
    def __init__(self):
        self.state_file = RUNTIME / "bindings.json"

    def discover(self):
        result = []
        for interface in sorted((USB / "devices").glob("*:*.?*")):
            try:
                physical = interface.resolve().parent
                if ((physical / "idVendor").read_text().strip() == "28bd"
                        and (physical / "idProduct").read_text().strip() == "0932"
                        and (interface / "bInterfaceNumber").read_text().strip()
                        in ("00", "01")):
                    result.append(interface.name)
            except FileNotFoundError:  # Device can disappear during enumeration.
                continue
        return result

    def driver(self, interface):
        link = USB / "devices" / interface / "driver"
        return link.resolve().name if link.is_symlink() else None

    def detach(self, interface):
        current = self.driver(interface)
        if current:
            (USB / "drivers" / current / "unbind").write_text(interface)

    def attach(self, interface, driver):
        if driver:
            (USB / "drivers" / driver / "bind").write_text(interface)

    def read(self):
        return json.loads(self.state_file.read_text()) if self.state_file.exists() else {}

    def save(self, state):
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(self.state_file)

    def bind(self):
        state = self.read()
        touched = []
        devices = self.discover()
        try:
            # Silence the compatibility interface before enabling the new mouse.
            devices.sort(key=lambda name: (name.rsplit(".", 1)[-1] != "0", name))
            for interface in devices:
                previous = self.driver(interface)
                state.setdefault(interface, "usbhid" if previous == NAME else previous)
                self.save(state)  # Save before unbinding, including on interruption.
                touched.append((interface, previous))
                self.detach(interface)
                self.attach(interface, NAME)
                if self.driver(interface) != NAME:
                    raise RuntimeError("driver did not bind to " + interface)
        except BaseException:
            for interface, previous in reversed(touched):
                try:
                    if interface in self.discover():
                        self.detach(interface)
                        self.attach(interface, previous)
                except Exception as error:
                    print("Rollback failed for %s: %s; run sudo make unload"
                          % (interface, error), file=sys.stderr)
            raise
        print("Bound %d USB interface(s)." % len(devices))
        if not devices:
            print("Connect the tablet to Ubuntu, then run sudo make bind.")

    def unload(self):
        state = self.read()
        for interface in self.discover():
            if self.driver(interface) == NAME:
                state.setdefault(interface, "usbhid")
        self.save(state)
        if Path("/sys/module", NAME).exists():
            subprocess.run(["rmmod", NAME], check=True)
        remaining = dict(state)
        failures = []
        present = set(self.discover())
        for interface, previous in state.items():
            try:
                # Never touch another device that reuses an old USB path.
                if interface in present and self.driver(interface) is None:
                    self.attach(interface, previous)
                remaining.pop(interface)
            except Exception as error:
                failures.append("%s: %s" % (interface, error))
        self.save(remaining)
        if failures:
            raise RuntimeError("Restore failed; retry sudo make unload: " + "; ".join(failures))
        print("Module unloaded; previous USB bindings restored.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("load", "bind", "unload"))
    parser.add_argument("--module", type=Path)
    parser.add_argument("--divisor", type=int, default=8)
    args = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() != 0:
        parser.error("run inside Ubuntu as root: sudo make " + args.action)
    if not 1 <= args.divisor <= 1024:
        parser.error("divisor must be in 1..1024")
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    if (RUNTIME.is_symlink() or RUNTIME.stat().st_uid != 0
            or RUNTIME.stat().st_mode & 0o022):
        parser.error("unsafe runtime directory")
    with (RUNTIME / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        bindings = Bindings()
        if args.action == "unload":
            bindings.unload()
            return
        loaded_here = False
        try:
            if not Path("/sys/module", NAME).exists():
                if args.action != "load" or args.module is None:
                    parser.error("module is not loaded; use sudo make load")
                subprocess.run(["insmod", str(args.module.resolve()),
                                "divisor=%d" % args.divisor], check=True)
                loaded_here = True
            elif args.action == "load":
                print("Module already loaded; divisor is unchanged. Unload to change it.")
            bindings.bind()
        except BaseException:
            if loaded_here:
                bindings.unload()
            raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
