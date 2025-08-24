import socket
import json
import logging
import threading
from time import sleep

class NetworkTransmitter:
    def __init__(self, host='192.168.0.66', port=65432):
        self.host = host
        self.port = port
        self.sock = None
        self.logger = logging.getLogger('HORUS_FAS.network_transmitter')
        self.on_partner_connected = []
        self.on_partner_disconnected = []

    def connect(self):
        """Łączy się z serwerem TCP (na Ubuntu)"""
        while not self.sock:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                self.logger.info(f"Połączono z serwerem {self.host}:{self.port}")
                threading.Thread(target=self.heartbeat_check, daemon=True).start()
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

    def heartbeat_check(self):
        while self.sock:
            try:
                self.sock.send(b'')
                sleep(0.5)
            except (BrokenPipeError, ConnectionResetError, OSError):
                self.close_connection()
                break
        self.connect()

    def subscribe_on_partner_connected(self,callback):
        self.on_partner_connected.append(callback)
        self.logger.info(f"Added {callback} as a subscriber to on_partner_connected.")

    def subscribe_on_partner_disconnected(self,callback):
        self.on_partner_disconnected.append(callback)
        self.logger.info(f"Added {callback} as a subscriber to on_partner_disconnected.")

    def unsubscribe_on_partner_connected(self, callback):
        if callback in self.on_partner_connected:
            self.on_partner_connected.remove(callback)

    def unsubscribe_on_partner_disconnected(self, callback):
        if callback in self.on_partner_disconnected:
            self.on_partner_disconnected.remove(callback)

    def close_connection(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            self.logger.info("Zamknięto połączenie z serwerem")
            for on_disconnected in self.on_partner_disconnected:
                on_disconnected()