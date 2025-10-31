from PyQt5.QtCore import QObject, pyqtSignal
import socket
import json
import logging
import threading
from time import sleep

class NetworkTransmitter(QObject):
    data_received_signal = pyqtSignal()

    def __init__(self, host='192.168.154.1', port=65432):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = None
        self.logger = logging.getLogger('HORUS_FAS.network_transmitter')
        self.on_partner_connected = []
        self.on_partner_disconnected = []
        self.on_data_received = []

        self._stop_event = threading.Event()
        self._receive_thread = None
        self._heartbeat_thread = None

    def connect(self):
        """Łączy się z serwerem TCP (na Ubuntu)"""
        while not self.sock:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                self.logger.info(f"Połączono z serwerem {self.host}:{self.port}")

                self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self._receive_thread.start()

                self._heartbeat_thread = threading.Thread(target=self._heartbeat_check, daemon=True)
                self._heartbeat_thread.start()

                for on_connected in self.on_partner_connected:
                    on_connected()
            except (ConnectionRefusedError, socket.timeout, OSError) as e:
                self.logger.error(f"Błąd łączenia z serwerem: {e}")
                sleep(2)

    def send_data(self, data: dict):
        """Wysyła dane JSON do serwera"""
        if not self.sock:
            self.logger.warning("Brak połączenia z serwerem – nie wysyłam")
            return
        try:
            json_data = json.dumps(data).encode("utf-8") + b"\n"
            self.sock.sendall(json_data)
            self.logger.debug(f"Wysłano dane: {data}")
        except Exception as e:
            self.logger.error(f"Błąd wysyłania danych: {e}")
            self.close_connection()
            self.connect()

    def _heartbeat_check(self):
        while self.sock:
            try:
                self.sock.send(b'')
                sleep(0.5)
            except (BrokenPipeError, ConnectionResetError, OSError):
                self.close_connection()
                break
        self.connect()

    def _receive_loop(self):
        buffer = b""
        while self.sock and not self._stop_event.is_set():
            self.logger.debug("I exist")
            try:
                chunk = self.sock.recv(4096)
                self.logger.debug(f"Raw received chunk: {chunk}")
                if not chunk:
                    self.logger.warning("Serwer zamknął połączenie")
                    self.close_connection()
                    break

                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        self.logger.debug(f"Odebrano dane: {data}")
                        self.data_received_signal.emit()
                        for cb in self.on_data_received:
                            cb(data)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Błąd dekodowania JSON: {e}")
                        continue

            except (ConnectionResetError, OSError) as e:
                self.logger.error(f"Błąd odbierania danych: {e}")
                self.close_connection()
                break

    def subscribe_on_partner_connected(self,callback):
        self.on_partner_connected.append(callback)
        self.logger.info(f"Added {callback} as a subscriber to on_partner_connected.")

    def subscribe_on_partner_disconnected(self,callback):
        self.on_partner_disconnected.append(callback)
        self.logger.info(f"Added {callback} as a subscriber to on_partner_disconnected.")

    def subscribe_on_data_received(self, callback):
        self.on_data_received.append(callback)

    def unsubscribe_on_partner_connected(self, callback):
        if callback in self.on_partner_connected:
            self.on_partner_connected.remove(callback)

    def unsubscribe_on_partner_disconnected(self, callback):
        if callback in self.on_partner_disconnected:
            self.on_partner_disconnected.remove(callback)

    def unsubscribe_on_data_received(self, callback):
        if callback in self.on_data_received:
            self.on_data_received.remove(callback)

    def close_connection(self):
        self._stop_event.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
            self.sock = None
            self.logger.info("Closed server connection")
            for callback in self.on_partner_disconnected:
                callback()

        current_thread = threading.current_thread()
        if self._receive_thread and self._receive_thread != current_thread:
            self._receive_thread.join(timeout=1)
        if self._heartbeat_thread and self._heartbeat_thread != current_thread:
            self._heartbeat_thread.join(timeout=1)