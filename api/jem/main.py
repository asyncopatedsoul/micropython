from ble_uart_repl import *
from ble_uart_peripheral import *

ble = bluetooth.BLE()
uart = BLEUART(ble, name="mpy-repl")
stream = BLEUARTStream(uart)

os.dupterm(stream)
