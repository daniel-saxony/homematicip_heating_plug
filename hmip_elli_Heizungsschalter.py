#!/usr/bin/env python3
"""
hmip_elli_Heizungsschalter_v23_throttle_safe.py

Automatisches Schalten einer HomematicIP-Steckdose,
wenn eines der FALMOT-Ventile offen ist.

Kompatibel mit homematicip-rest-api >= 2.3.x
Throttling-sicher (API-Aufrufe nur wenn nötig)
"""

import asyncio
import configparser
import time
import json
from homematicip.async_home import AsyncHome

CONFIG_FILE = "/opt/hmip_elli/bin/config.ini"
PLUG_NAME = "Schalt-Mess-Steckdose"
VALVE_DEVICE_TYPE = "FLOOR_TERMINAL_BLOCK_12"
#API_COOLDOWN = 300          # Sek. Mindestabstand zwischen get_current_state_async
FULL_SYNC_INTERVAL = 900    # Sek. (alle 15 Minuten kompletter Sync)

async def main():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    authtoken = cfg["AUTH"]["authtoken"].strip()
    accesspoint = cfg["AUTH"]["accesspoint"].strip()

    home = AsyncHome()
    await home.init_async(accesspoint)
    home.set_auth_token(authtoken)
    await home.get_current_state_async()

    plug = next((d for d in home.devices if d.label == PLUG_NAME), None)
    if not plug:
        print(f"⚠️ Steckdose '{PLUG_NAME}' nicht gefunden.")
        for d in home.devices:
            print(f"- {d.label} ({d.deviceType})")
        return
    print(f"✅ Steckdose gefunden: {plug.label}")

    valve_open = False
    last_api_call = 0.0
    valve_check_lock = asyncio.Lock()

    def extract_valve_positions_from_event(event_json):
        """Sucht nach valvePosition-Werten in DEVICE_CHANGED Events."""
        valves = []
        try:
            events = event_json.get("events", {})
            for ev in events.values():
                if ev.get("pushEventType") != "DEVICE_CHANGED":
                    continue
                device = ev.get("device", {})
                if VALVE_DEVICE_TYPE not in device.get("type", ""):
                    continue
                fcs = device.get("functionalChannels", {})
                # ⚙️ kompatibel zu dict oder list
                if isinstance(fcs, dict):
                    ch_iter = fcs.values()
                elif isinstance(fcs, list):
                    ch_iter = fcs
                else:
                    continue
                for ch in ch_iter:
                    vp = ch.get("valvePosition")
                    if vp is not None:
                        valves.append(vp)
        except Exception as e:
            print(f"⚠️ Fehler beim Lesen valvePosition: {e}")
        return valves

    def is_any_valve_open_state():
        """Backup: prüft den aktuellen Gerätestatus."""
        for dev in home.devices:
            if VALVE_DEVICE_TYPE in getattr(dev, "deviceType", ""):
                fcs = getattr(dev, "functionalChannels", {})
                if isinstance(fcs, dict):
                    channels = fcs.values()
                elif isinstance(fcs, list):
                    channels = fcs
                else:
                    continue
                for ch in channels:
                    pos = getattr(ch, "valvePosition", None)
                    if pos and pos > 0:
                        return True
        return False

    async def handle_event(event):
        nonlocal valve_open, last_api_call
        try:
            if isinstance(event, (bytes, bytearray)):
                event = json.loads(event.decode("utf-8"))
            elif isinstance(event, str):
                event = json.loads(event)
        except Exception as e:
            print(f"⚠️ Event konnte nicht dekodiert werden: {e}")
            return

        valves = extract_valve_positions_from_event(event)
        if valves:
            any_open = any(v > 0 for v in valves)
            async with valve_check_lock:
                if any_open and not valve_open:
                    valve_open = True

                    print(f"🔥 Ventile {'offen' if valve_open else 'geschlossen'} → Steckdose {'ein' if valve_open else 'aus'} von Event – Zeit: {time.strftime('%H:%M:%S')}")
                    await plug.set_switch_state_async(True)

                elif not any_open and valve_open:
                    valve_open = False

                    print(f"🔥 Ventile {'offen' if valve_open else 'geschlossen'} → Steckdose {'ein' if valve_open else 'aus'} von Event – Zeit: {time.strftime('%H:%M:%S')}")
                    await plug.set_switch_state_async(False)
        else:
            now = time.time()
            #if now - last_api_call > API_COOLDOWN:
            #    print("🔍 Kein Ventilwert im Event, führe Sync durch ...")
            #    await home.get_current_state_async()
            #    last_api_call = time.time()
            #    any_open = is_any_valve_open_state()
            #    async with valve_check_lock:
            #        if any_open and not valve_open:
            #            valve_open = True
            #            print("🔥 Ventile offen → Steckdose EIN")
            #            await plug.set_switch_state_async(True)
            #
            #        elif not any_open and valve_open:
            #            valve_open = False
            #            print("❄️ Alle Ventile zu → Steckdose AUS")
            #            await plug.set_switch_state_async(False)
            #else:
            #    print("⏳ Event ohne valvePosition ignoriert (Cooldown aktiv).")
            print("🔍 Kein Ventilwert im Event")

    await home.enable_events(handle_event)
    print("✅ Event-System aktiviert – warte auf Ventiländerungen ...")

    try:
        while True:
            await asyncio.sleep(FULL_SYNC_INTERVAL)
            print("🔄 Periodischer vollständiger Abgleich ...")
            await home.get_current_state_async()
            any_open = is_any_valve_open_state()
            async with valve_check_lock:
                if any_open and not valve_open:
                    valve_open = True

                    print(f"🔥 Ventile {'offen' if valve_open else 'geschlossen'} → Steckdose {'ein' if valve_open else 'aus'} von Sync – Zeit: {time.strftime('%H:%M:%S')}")
                    await plug.set_switch_state_async(True)

                elif not any_open and valve_open:
                    valve_open = False

                    print(f"🔥 Ventile {'offen' if valve_open else 'geschlossen'} → Steckdose {'ein' if valve_open else 'aus'} von Sync – Zeit: {time.strftime('%H:%M:%S')}")
                    await plug.set_switch_state_async(False)


    except KeyboardInterrupt:
        print("🛑 Beendet durch Benutzer.")
    except asyncio.CancelledError:
        print("🛑 asyncio.Task abgebrochen (Ctrl+C).")
    finally:
        # Kein disable_events() nötig – wird automatisch vom Websocket-Handler geschlossen
        try:
            await home.websocket_handler.close()
            print("📴 WebSocket geschlossen.")
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
