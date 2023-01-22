from ble_uart_repl import *
from ble_uart_peripheral import *

esp32_ble = bluetooth.BLE()
jem_ble = BLE(esp32_ble, name="JEM-BLE")
uart = BLEUART(jem_ble)
stream = BLEUARTStream(uart)
os.dupterm(stream)

