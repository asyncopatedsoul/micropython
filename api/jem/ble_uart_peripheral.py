# This example demonstrates a peripheral implementing the Nordic UART Service (NUS).

import bluetooth
from ble_advertising import advertising_payload

from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)
_IRQ_GATTS_INDICATE_DONE = const(20)
_IRQ_MTU_EXCHANGED = const(21)
_IRQ_L2CAP_ACCEPT = const(22)
_IRQ_L2CAP_CONNECT = const(23)
_IRQ_L2CAP_DISCONNECT = const(24)
_IRQ_L2CAP_RECV = const(25)
_IRQ_L2CAP_SEND_READY = const(26)
_IRQ_CONNECTION_UPDATE = const(27)
_IRQ_ENCRYPTION_UPDATE = const(28)
_IRQ_GET_SECRET = const(29)
_IRQ_SET_SECRET = const(30)

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

class BleCharEvent:
    def __init__(self, event, value):
        self.e = event
        self.v = value

    def event(self):
        return self.e

    def value(self):
        return self.v

class BleCharacteristic:
    def __init__(self, uuid, buf_size=None):
        self.uuid = bluetooth.UUID(uuid)
        self.handler = None
        self.trigger = None
        self.value_handle = None # this is what we get back from ble after register services / chars
        self.buf_size = buf_size

    def callback(self, trigger, handler):
        # ex: rx_callback = rx_char.callback(trigger=Bluetooth.CHAR_WRITE_EVENT, handler=self.rx_cb_handler)
        self.trigger = trigger
        self.handler = handler

    def irq(self, event, value):
        self.handler(BleCharEvent(event, value))

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

    def characteristic(self, uuid, buf_size=None):
        if uuid not in self.chr_uuids:
            ble_char = BleCharacteristic(uuid, buf_size)
            self.chrs.append(ble_char)
            self.chr_uuids.append(uuid)
            return ble_char

class BLE:
    def __init__(self, esp32_ble, name="JEM-BLE"):
        self._ble = esp32_ble # bluetooth.BLE()
        self.services = []
        self.service_uuids = []
        self.primary_uuid = None
        self.char_handles_map = {}

        self._ble.active(True)
        self._ble.config(gap_name=name)
        self._ble.config(mtu=200)
        self._ble.irq(self._irq)

        # Increase the size of the rx buffer and enable append mode.
        self._connections = set()

    def service(self, uuid, isPrimary=False, nbr_chars=0):
        if uuid not in self.service_uuids:
            self.service_uuids.append(uuid)
            service = BleService(uuid=uuid, isPrimary=isPrimary)
            if isPrimary:
                self.primary_uuid = uuid
            self.services.append(service)
            return service

    def get_chr_handles(self):
        char_handles = []
        for service in self.services:
            chrs = service.chrs
            char_handles += chrs

        char_handles.reverse() # we reverse so that when we call pop it spits out the as fifo
        return char_handles

    def register(self):
        services = [ service.get() for service in self.services ]
        value_handles = self._ble.gatts_register_services(services)
        # ex: ((self._tx_handle, self._rx_handle), (self._ftp_tx_handle, self._ftp_rx_handle), ) = _ble.gatts_register_services()

        char_handles = self.get_chr_handles()
        # we use the value_handles provided by gatts register ( list of ble characteristic hooks by how they were added by user)
        # to build a connection between the ble characteristic class object we created and the one the esp32 driver created
        self.char_handles_map = {}
        for chr_val_handles in value_handles:
            for value_handle in chr_val_handles:
                char_handle = char_handles.pop()
                self.char_handles_map[value_handle] = char_handle
                # char_handle is instance of BleCharacteristic
                # and value_handle is one created by esp32 ble driver
                char_handle.value_handle = value_handle
                if char_handle.buf_size:
                    self._ble.gatts_set_buffer(value_handle.value_handle, value_handle.buf_size, True)

    def advertising_payload(self):
        services = []
        for service in self.services:
            if service.is_primary:
                services = [ service.uuid ]
                print("adv primary service %s" % service.uuid)

        self._payload = advertising_payload(services=services)
        return self._payload

    def advertise(self, interval_us=500000):
        self.register()
        payload = self.advertising_payload()
        self._ble.gap_advertise(interval_us, adv_data=payload)

    def write(self, chr, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, chr.value_handle, data)

    def close(self):
        for conn_handle in self._connections:
            self._ble.gap_disconnect(conn_handle)
        self._connections.clear()

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
        elif event == _IRQ_GATTS_WRITE or event == _IRQ_GATTS_READ_REQUEST or event == _IRQ_GATTS_INDICATE_DONE:
            conn_handle, value_handle = data
            if conn_handle in self._connections and value_handle in self.char_handles_map:
                # self._rx_buffer += self._ble.gatts_read(self._rx_handle)
                if event == _IRQ_GATTS_WRITE:
                    value = self._ble.gatts_read(value_handle)
                    char_handle = self.char_handles_map[value_handle] # ex: self.rx_char
                    char_handle.irq(event, value)
                elif event == _IRQ_GATTS_READ_REQUEST:
                    print("_IRQ_GATTS_READ_REQUEST unhandled")
                elif event == _IRQ_GATTS_INDICATE_DONE:
                    print("_IRQ_GATTS_INDICATE_DONE unhandled")
            else:
                print("Fail: %s not in %s" % (value_handle, self.char_handles_map))
        elif event == _IRQ_GATTC_WRITE_DONE:
            print("_IRQ_GATTC_WRITE_DONE")

        elif event == _IRQ_MTU_EXCHANGED:
            print("_IRQ_MTU_EXCHANGED %s " % data)

class BLEUART:
    def __init__(self, jem_ble, service_uuid, tx_chr_uuid, rx_chr_uuid, rxbuf=100):
        self.ble = jem_ble # jem ble wrapper
        uart_service = self.ble.service(uuid=service_uuid, isPrimary=True)
        self.tx_char = uart_service.characteristic(uuid=tx_chr_uuid)
        self.rx_char = uart_service.characteristic(uuid=rx_chr_uuid)
        self.rx_char.callback(None, self.rx_cbk)
        self.tx_char.callback(None, self.tx_cbk)

        ftp_service = self.ble.service(uuid="6E400001-B5A3-F393-E0A9-E50E24DCCA77")
        self.ftp_char1 = ftp_service.characteristic(uuid="6E400003-B5A3-F393-E0A9-E50E24DCCA77")
        self.ftp_char2 = ftp_service.characteristic(uuid="6E400002-B5A3-F393-E0A9-E50E24DCCA77")
        self.ftp_char1.callback(None, self.ftp_char1_cbk)
        self.ftp_char2.callback(None, self.ftp_char2_cbk)

        self._rx_buffer = bytearray()
        self._handler = None
        self.ble.advertise()

    def rx_cbk(self, chr, data=None):
        value = chr.value()
        self._rx_buffer += value
        if self._handler:
            self._handler()

    def ftp_char2_cbk(self, chr, data=None):
        print("ftp_char2_cbk")

    def ftp_char1_cbk(self, chr, data=None):
        print("ftp_char1_cbk")

    def tx_cbk(self):
        print("tx_char_cbk")

    def irq(self, handler):
        self._handler = handler

    def any(self):
        return len(self._rx_buffer)

    def read(self, sz=None):
        if not sz:
            sz = len(self._rx_buffer)
        result = self._rx_buffer[0:sz]
        self._rx_buffer = self._rx_buffer[sz:]
        return result

    def write(self, data):
        self.ble.write(self.tx_char, data)


