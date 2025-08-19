import socket
import json
import logging


class NetworkTransmitter:
    def __init__(self, host='192.168.0.66', port=65432):
        self.host = host
        self.port = port
        self.sock = None
        self.logger = logging.getLogger('HORUS_FAS.network_transmitter')

    def connect(self):
        """Łączy się z serwerem TCP (na Ubuntu)"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.logger.info(f"Połączono z serwerem {self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Błąd łączenia z serwerem: {e}")

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
            self.sock = None

    def close_connection(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            self.logger.info("Zamknięto połączenie z serwerem")

