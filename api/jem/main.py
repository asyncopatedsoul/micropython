from ble_uart_repl import *
from ble_uart_peripheral import *
from ble_uart_ftp import *

esp32_ble = bluetooth.BLE()
jem_ble = BLE(esp32_ble, name="JEM-BLE")
repl_uart = BLEUART(jem_ble, service_uuid="6E400001-B5A3-F393-E0A9-E50E24DCCA9E",
                        tx_chr_uuid="6E400003-B5A3-F393-E0A9-E50E24DCCA9E",
                        rx_chr_uuid="6E400002-B5A3-F393-E0A9-E50E24DCCA9E")

stream = BLEUARTStream(repl_uart)

ftp_uart = BLEUART(jem_ble, service_uuid="6E400001-B5A3-F393-E0A9-E50E24DCCA77",
                        tx_chr_uuid="6E400003-B5A3-F393-E0A9-E50E24DCCA77",
                        rx_chr_uuid="6E400002-B5A3-F393-E0A9-E50E24DCCA77")

ftp = BLEUARTFTP(ftp_uart)

jem_ble.advertise()

os.dupterm(stream)

