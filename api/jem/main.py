from ble_uart_repl import *
from ble_uart_peripheral import *

ble = bluetooth.BLE()
uart = BLEUART(ble, name="jem-ble")
stream = BLEUARTStream(uart)

os.dupterm(stream)
print("Staring ble")

