#!/usr/bin/env python3
"""Manual regression test for crestron_nvx_api.py against real hardware.

Reads NVX_HOSTS / NVX_USERNAME / NVX_PASSWORD / NVX_VERIFY_SSL from .env in
this directory. Exercises every read endpoint against each configured host,
and (only if you pass --write and/or --cec) tests a real AvRouting source
switch or the CEC long-poll listener interactively.

Usage:
    python3 test_live.py            # read-only checks
    python3 test_live.py --write    # also test a live route switch
    python3 test_live.py --cec      # also test the CEC long-poll listener
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "custom_components" / "crestron_nvx"))

from crestron_nvx_api import CrestronNVXAPI, decode_cec_message  # noqa: E402


def load_env() -> dict[str, str]:
    env_path = Path(__file__).parent / ".env"
    env = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


async def check_device(api: CrestronNVXAPI, host: str, username: str, password: str) -> None:
    print(f"\n=== {host} ===")
    try:
        device = await api.add_device(host=host, name=host, username=username, password=password)
    except Exception as err:  # noqa: BLE001 - report and continue to next device
        print(f"  LOGIN FAILED: {err}")
        return

    print(f"  mode: {device.device_mode}")

    info = await device.get_device_info()
    if info:
        print(f"  model={info.get('Model')} name={info.get('Name')} fw={info.get('DeviceVersion')}")
    else:
        print("  DeviceInfo: FAILED")

    video = await device.get_video_status()
    print(f"  video: {video}")

    eth = await device.get_ethernet_status()
    print(f"  ethernet: {eth}")

    if device.is_receiver:
        streams = await device.get_discovered_streams()
        print(f"  discovered streams: {[s.get('SessionName') for s in streams.values()]}")
        route = await device.get_current_route()
        print(f"  current route: {route}")

    if device.is_transmitter:
        cec_raw = await device.get_cec_input_message()
        print(f"  last CEC message: {cec_raw!r} -> {decode_cec_message(cec_raw)}")


async def test_route_switch(api: CrestronNVXAPI) -> None:
    receivers = [d for d in api.devices.values() if d.is_receiver]
    if not receivers:
        print("\nNo receivers configured, skipping write test.")
        return

    print("\nReceivers available for a live route-switch test:")
    for i, dev in enumerate(receivers):
        print(f"  [{i}] {dev.host}")
    choice = input("Pick one to test (or blank to skip): ").strip()
    if not choice:
        return
    device = receivers[int(choice)]

    streams = await device.get_discovered_streams()
    if not streams:
        print("No discovered streams to switch to.")
        return

    original = await device.get_current_route()
    print(f"Current route: {original}")

    print("Available sources:")
    items = list(streams.items())
    for i, (uid, info) in enumerate(items):
        print(f"  [{i}] {info.get('SessionName')} ({uid})")
    idx = input("Switch to which source? (blank to skip): ").strip()
    if not idx:
        return
    target_uid, target_info = items[int(idx)]

    ok = await device.set_route(target_uid)
    print(f"set_route({target_info.get('SessionName')}) -> {'OK' if ok else 'FAILED'}")

    if original and input("Revert to original source? [Y/n]: ").strip().lower() != "n":
        restore_uid = original.get("VideoSource")
        if restore_uid:
            ok = await device.set_route(restore_uid)
            print(f"Reverted -> {'OK' if ok else 'FAILED'}")


async def test_cec_listener(api: CrestronNVXAPI) -> None:
    transmitters = [d for d in api.devices.values() if d.is_transmitter]
    if not transmitters:
        print("\nNo transmitters configured, skipping CEC test.")
        return

    print("\nTransmitters available for a live CEC long-poll test:")
    for i, dev in enumerate(transmitters):
        print(f"  [{i}] {dev.name} ({dev.host})")
    choice = input("Pick one to test (or blank to skip): ").strip()
    if not choice:
        return
    device = transmitters[int(choice)]

    print(f"Long-polling {device.name} for 30s - press a button on its remote now...")
    changed = await device.longpoll(timeout=30)
    if not changed:
        print("No change detected (timeout).")
        return

    try:
        raw = changed["Device"]["AudioVideoInputOutput"]["Inputs"][0]["Ports"][0]["Hdmi"][
            "ReceiveCecMessage"
        ]
    except (KeyError, TypeError, IndexError):
        print(f"Changed, but not a CEC message: {changed}")
        return

    print(f"Raw CEC message: {raw!r} -> event: {decode_cec_message(raw)}")


async def main() -> None:
    env = load_env()
    hosts = [h.strip() for h in env.get("NVX_HOSTS", "").split(",") if h.strip()]
    username = env.get("NVX_USERNAME", "")
    password = env.get("NVX_PASSWORD", "")
    verify_ssl = env.get("NVX_VERIFY_SSL", "false").lower() == "true"

    if not hosts:
        print("NVX_HOSTS is empty in .env - nothing to test.")
        return

    api = CrestronNVXAPI(verify_ssl=verify_ssl)
    try:
        for host in hosts:
            await check_device(api, host, username, password)

        if "--write" in sys.argv:
            await test_route_switch(api)

        if "--cec" in sys.argv:
            await test_cec_listener(api)
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
