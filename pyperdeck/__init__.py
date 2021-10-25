from telnetlib import Telnet
from threading import Thread
from typing import List, Tuple, Dict

from ._internals import Slot

class Hyperdeck:
    def __init__(self, ip: str) -> None:
        self.connection = Telnet(ip, 9993)

        self._reader_thread = Thread(target=self._reader)
        self._reader_thread.start()

        self._send('device info')

        # Device Info
        self.protocol_version = None
        self.model = None
        self.unique_id = None
        self.slot_count = 0
        self.software_version = None

        # Slot Info
        self.slots = {} # type: Dict[str, Slot]
        self.remaining_time = 0 # recording time remaining in seconds
    
    def _reader(self) -> None:
        while True:
            message = self.connection.read_until(bytes('\r\n', 'ascii'))
            if message.decode('ascii')[-3] == ':':
                message += self.connection.read_until(bytes('\r\n\r\n', 'ascii'))
                self._decode_message(message)
            else:
                self._decode_response(message)
    
    def _send(self, command: str) -> None:
        self.connection.write(bytes(command + '\r\n', 'ascii'))
    
    def _decode_response(self, message: bytes) -> None:
        response = message.decode('ascii').rstrip('\r\n')
        status = self._get_status_of_message(response)
        print(status)

    def _decode_message(self, message: bytes) -> None:
        msg = message.decode('ascii').rstrip('\r\n\r\n')
        lines = msg.split('\r\n')
        status = self._get_status_of_message(lines[0])
        body = lines[1:]
        if 500 <= status[0] <= 599:
            self._asynchronous_response_processor(status, body)
        elif 200 < status[0] <= 299:
            self._success_response_processor(status, body)
        print(status)
        print(body)
        
    def _get_status_of_message(self, status_line: str) -> Tuple[int, str]:
        blocks = status_line.rstrip(':').split(' ', maxsplit=1)
        status = int(blocks[0])
        response = blocks[1]
        return status, response
    
    def _asynchronous_response_processor(self, status: Tuple[int, str], body: List[str]) -> None:
        if status[1] == 'connection info':
            self._connection_info(body)
        elif status[1] == 'slot info':
            self._slot_info(body)
    
    def _connection_info(self, body: List[str]) -> None:
        for field in body:
            prop, value = field.split(': ')
            if prop == 'protocol version':
                self.protocol_version = value
            elif prop == 'model':
                self.model = value
    
    def _slot_info(self, body: List[str]) -> None:
        slot = None
        for field in body:
            prop, value = field.split(': ')
            if prop == 'slot id':
                slot = value
                break
        self.slots[slot]._slot_info(body)
        self._recording_time_remaining()
    
    def _recording_time_remaining(self) -> None:
        remaining_time = 0
        for slot in self.slots.values():
            remaining_time += slot.recording_time
        self.remaining_time = remaining_time
    
    def _success_response_processor(self, status: Tuple[int, str], body: List[str]) -> None:
        if status[1] == 'slot info':
            self._slot_info(body)
        elif status[1] == 'device info':
            self._device_info(body)
    
    def _device_info(self, body: List[str]) -> None:
        for field in body:
            prop, value = field.split(': ')
            if prop == 'protocol version':
                self.protocol_version = value
            elif prop == 'model':
                self.model = value
            elif prop == 'unique id':
                self.unique_id = value
            elif prop == 'slot count':
                self.slot_count = int(value)
            elif prop == 'software version':
                self.software_version = value
        
        for slot in range(self.slot_count):
            self.slots[str(slot + 1)] = Slot(slot + 1)
            self._send(f'slot info: slot id: {slot + 1}')
        