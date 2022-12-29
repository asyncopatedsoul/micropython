# This example demonstrates a peripheral implementing the Nordic UART Service (NUS).

import bluetooth
from ble_advertising import advertising_payload

from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

F_READ = bluetooth.FLAG_READ
F_WRITE = bluetooth.FLAG_WRITE
F_NOTIFY = bluetooth.FLAG_NOTIFY
F_READ_WRITE = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE
F_READ_NOTIFY = bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY
F_RD_WR_NTFY = bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_NOTIFY


_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (
    bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
    F_NOTIFY,
)
_UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
    F_WRITE,
)
_UART_SERVICE = (
    _UART_UUID,
    (_UART_TX, _UART_RX),
)

# BLE UART FTP Service
_FTP_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA77")

_FTP_UART_TX = (
    bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA77"),
    F_NOTIFY,
)

_FTP_UART_RX = (
    bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA77"),
    F_WRITE,
)

_FTP_UART_SERVICE = (
    _FTP_UART_UUID,
    (_FTP_UART_TX, _FTP_UART_RX),
)

# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_COMPUTER = const(128)

class BleCharacteristic:
    def __init__(self, uuid):
        self.uuid = bluetooth.UUID(uuid)
        self.handler = None
        self.trigger = None

    def callback(self, trigger, handler):
        # ex: rx_callback = rx_char.callback(trigger=Bluetooth.CHAR_WRITE_EVENT, handler=self.rx_cb_handler)
        self.trigger = trigger
        self.handler = handler

class BleService:
    # ex: uuid = "6E400003-B5A3-F393-E0A9-E50E24DCCA77"
    def __init__(self, uuid, isPrimary=False):
        self.is_primary = isPrimary
        self.uuid = bluetooth.UUID(uuid)
        self.chr_uuids = []
        self.chrs = []

    def get(self):
        flag = F_RD_WR_NTFY
        chrs = [ [bluetooth.UUID(uuid), flag]  for uuid in self.chr_uuids ]
        service = [ self.uuid, chrs ]
        #ex: service = ( _UART_UUID, (_UART_TX, _UART_RX), )
        return service

    def characteristic(self, uuid):
        if uuid not in self.chr_uuids:
            ble_char = BleCharacteristic(uuid)
            self.chrs.append(ble_char)
            self.chr_uuids.append(uuid)
            return ble_char

class BLE:
    def __init__(self, ble):
        self._ble = ble # bluetooth.BLE()
        self.services = []
        self.service_uuids = []
        self.primary_uuid = None

    def service(self, uuid, isPrimary=False, nbr_chars=0):
        if uuid not in self.service_uuids:
            self.service_uuids.append(uuid)
            service = BleService(uuid=uuid, isPrimary=isPrimary)
            if isPrimary:
                self.primary_uuid = uuid
            self.services.append(service)
            return service

    def register(self):
        services = [ service.get() for service in self.services ]
        return self._ble.gatts_register_services(services)

    def advertising_payload(self):
        services = []
        for service in self.services:
            if service.is_primary:
                services = [ service.uuid ]
                print("adv primary service %s" % service.uuid)

        self._payload = advertising_payload(services=services)
        return self._payload

    def advertise(self, interval_us=500000):
        payload = self.advertising_payload()
        self._ble.gap_advertise(interval_us, adv_data=payload)

class BLEUART:
    def __init__(self, ble, name="bleuart", rxbuf=100):
        self._ble = ble
        self._ble.active(True)
        self._ble.config(gap_name=name)
        self._ble.config(mtu=200)
        self._ble.irq(self._irq)

        w_ble = BLE(self._ble) # helper
        uart_service = w_ble.service(uuid="6E400001-B5A3-F393-E0A9-E50E24DCCA9E", isPrimary=True)
        self.tx_char = uart_service.characteristic(uuid="6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
        self.rx_char = uart_service.characteristic(uuid="6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
        self.rx_char.callback(None, self.rx_char_cbk)
        self.tx_char.callback(None, self.tx_char_cbk)
        ftp_service = w_ble.service(uuid="6E400001-B5A3-F393-E0A9-E50E24DCCA77")
        ftp_service.characteristic(uuid="6E400003-B5A3-F393-E0A9-E50E24DCCA77")
        ftp_service.characteristic(uuid="6E400002-B5A3-F393-E0A9-E50E24DCCA77")

        ((self._tx_handle, self._rx_handle), (self._ftp_tx_handle, self._ftp_rx_handle), ) = w_ble.register()

        # Increase the size of the rx buffer and enable append mode.
        self._ble.gatts_set_buffer(self._rx_handle, rxbuf, True)
        self._connections = set()
        self._rx_buffer = bytearray()
        self._handler = None
        # Optionally add services=[_UART_UUID], but this is likely to make the payload too large.
        self.w_ble = w_ble
        self.advertise()

    def advertise(self):
        self.w_ble.advertise()

    def rx_char_cbk(self):
        print("rx_char_cbk")

    def tx_char_cbk(self):
        print("tx_char_cbk")

    def irq(self, handler):
        self._handler = handler

    def _irq(self, event, data):
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            print("irq event: _IRQ_CENTRAL_CONNECT")
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            print("irq event: _IRQ_CENTRAL_DISCONNECT")
            conn_handle, _, _ = data
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self.advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if conn_handle in self._connections and value_handle == self._rx_handle:
                self._rx_buffer += self._ble.gatts_read(self._rx_handle)
                if self._handler:
                    self._handler()
        elif event == _IRQ_MTU_EXCHANGED:
            print("_IRQ_MTU_EXCHANGED %s " % data)

    def any(self):
        return len(self._rx_buffer)

    def read(self, sz=None):
        if not sz:
            sz = len(self._rx_buffer)
        result = self._rx_buffer[0:sz]
        self._rx_buffer = self._rx_buffer[sz:]
        return result

    def write(self, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._tx_handle, data)

    def close(self):
        for conn_handle in self._connections:
            self._ble.gap_disconnect(conn_handle)
        self._connections.clear()


def demo():
    import time

    ble = bluetooth.BLE()
    uart = BLEUART(ble)

    def on_rx():
        print("rx: ", uart.read().decode().strip())

    uart.irq(handler=on_rx)
    nums = [4, 8, 15, 16, 23, 42]
    i = 0

    try:
        while True:
            uart.write(str(nums[i]) + "\n")
            i = (i + 1) % len(nums)
            time.sleep_ms(1000)
    except KeyboardInterrupt:
        pass

    uart.close()


if __name__ == "__main__":
    demo()
