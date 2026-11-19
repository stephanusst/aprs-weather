import time
import json
import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import paho.mqtt.client as mqtt

# --- Configuration ---
MODBUS_HOST = "11.10.0.100"   # PLC or Sensor IP
MODBUS_PORT = 502
MODBUS_UNIT_ID = 1             # Slave/Device ID
START_REGISTER = 0             # Starting Holding Register address
REGISTER_COUNT = 2             # Number of registers to read

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "factory/line1/sensor_data"
POLL_INTERVAL = 5              # Seconds between reads

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def setup_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="modbus_gateway_01")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()  # Runs background network thread for automatic reconnects
    return client

def main():
    mqtt_client = setup_mqtt()
    modbus_client = ModbusTcpClient(host=MODBUS_HOST, port=MODBUS_PORT)

    try:
        while True:
            if not modbus_client.connected:
                logging.info("Connecting to Modbus device...")
                modbus_client.connect()

            try:
                # Read Holding Registers (Function Code 03)
                response = modbus_client.read_holding_registers(
                    address=START_REGISTER,
                    count=REGISTER_COUNT,
                    device_id=MODBUS_UNIT_ID
                )

                if response.isError():
                    logging.error(f"Modbus protocol error: {response}")
                else:
                    regs = response.registers
                    # Example scaling: divide raw integer by 10.0 for float values
                    payload = {
                        "timestamp": int(time.time()),
                        "humidity": regs[0] / 10.0,
                        "temperature": regs[1] / 10.0
                    }

                    json_payload = json.dumps(payload)
                    result = mqtt_client.publish(MQTT_TOPIC, json_payload, qos=1)
                    
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        logging.info(f"Published: {json_payload}")
                    else:
                        logging.warning(f"MQTT publish failed with code {result.rc}")

            except ModbusException as exc:
                logging.error(f"Modbus communication exception: {exc}")
                modbus_client.close()

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logging.info("Shutting down gateway...")
    finally:
        modbus_client.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
