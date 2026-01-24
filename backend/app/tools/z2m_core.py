"""
app/tools/z2m_core.py
"""
import json
import asyncio
import paho.mqtt.subscribe as subscribe
from config.settings import get_config

cfg = get_config()

async def get_sensor_data(friendly_name: str):
    """Hämtar sensorvärden (temp, fukt etc) via Zigbee2MQTT."""
    topic = f"{cfg['MQTT_TOPIC_BASE']}/{friendly_name}"
    print(f"[Z2M] Läser: {topic}")

    try:
        # Kör den blockerande subscribe-funktionen i en executor (tråd)
        loop = asyncio.get_event_loop()
        msg = await loop.run_in_executor(None, lambda: subscribe.simple(
            topic, 
            hostname=cfg['MQTT_BROKER_IP'], 
            port=cfg['MQTT_PORT'], 
            timeout=2.0
        ))

        if not msg: return f"Inget svar från {friendly_name}"
        
        data = json.loads(msg.payload.decode("utf-8"))
        output = []
        ignored = ["linkquality", "update_available", "voltage", "device"]
        
        for k, v in data.items():
            if k not in ignored: output.append(f"{k}: {v}")
            
        return f"Data för {friendly_name}: " + ", ".join(output)
    except Exception as e:
        return f"Fel vid sensorläsning: {e}"