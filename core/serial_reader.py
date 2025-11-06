import serial
import time
import re
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread


# ======================================
# Klasa wątku: QThread do odczytu LoRa
# ======================================
class SerialThread(QThread):
    telemetry_received = pyqtSignal(dict)
    auxiliary_received = pyqtSignal(dict)
    transmission_info_received = pyqtSignal(dict)

    def __init__(self, ser, logger):
        super().__init__()
        self.ser = ser
        self.logger = logger
        self.running = True

    def run(self):
        if not self.ser or not self.ser.is_open:
            self.logger.error("Port szeregowy nie jest otwarty – przerwano wątek odczytu.")
            return

        self.logger.info("Wątek odczytu rozpoczął działanie.")

        while self.running and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors='ignore').strip()
                if line:
                    self.handle_line(line)
            except serial.SerialException as e:
                self.logger.error(f"Błąd wątku odczytu: {e}")
                break
            QThread.msleep(60)

        self.logger.info("Wątek odczytu zakończył działanie.")

    def handle_line(self, line):
        """Proste dekodowanie w wątku, bez blokowania GUI."""
        if not line.startswith("+TEST: RX"):
            pattern = r"\+TEST: LEN:(\d+), RSSI:(-?\d+), SNR:(-?\d+)"
            match = re.search(pattern, line)
            if match:
                transmission = {
                    'len': int(match.group(1)),
                    'rssi': int(match.group(2)),
                    'snr': int(match.group(3))
                }
                self.transmission_info_received.emit(transmission)
            return

        match = re.search(r'"([0-9A-Fa-f]+)"', line)
        if not match:
            return

        try:
            hex_data = match.group(1)
            byte_data = bytes.fromhex(hex_data)
            decoded = byte_data.decode('utf-8', errors='replace').strip()

            prefix = decoded[0]
            data = decoded[1:].split(";")

            if prefix == "A" and len(data) >= 6:
                telemetry = {
                    'pitch': float(data[0]),
                    'roll': float(data[1]),
                    'yaw': float(data[2]),
                    'ver_velocity': float(data[3]),
                    'altitude': float(data[4]),
                    'rbs': float(data[5])
                }
                self.telemetry_received.emit(telemetry)

            elif prefix == "B" and len(data) >= 3:
                auxiliary = {
                    'latitude': data[0],
                    'longitude': data[1],
                    'status': int(data[2])
                }
                self.auxiliary_received.emit(auxiliary)

        except Exception as e:
            self.logger.error(f"Błąd dekodowania w wątku: {e}")




# ======================================
# Główna klasa: SerialReader
# ======================================
class SerialReader(QObject):
    telemetry_received = pyqtSignal(dict)
    auxiliary_received = pyqtSignal(dict)
    transmission_info_received = pyqtSignal(dict)

    def __init__(self, port="COM7", baudrate=9600, transmitter=None):
        super().__init__()
        self.logger = logging.getLogger('HORUS_FAS.serial_reader')
        self.port = port
        self.baudrate = baudrate
        self.transmitter = transmitter

        self.ser = None
        self.thread = None
        self.running = False  # 🔹 to musi być!

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.5)
            self.logger.info(f"Otworzono port {self.port} z baudrate {self.baudrate}")
        except serial.SerialException as e:
            self.logger.error(f"Błąd otwierania portu {self.port}: {e}")

    # -------------------------------
    # Uruchamianie i zatrzymywanie
    # -------------------------------
    def start_reading(self):
        if self.running:
            self.logger.debug("Wątek już działa – pomijam start.")
            return

        self.running = True
        self.thread = SerialThread(self.ser, self.logger)

        # 🔹 połącz sygnały z GUI
        self.thread.telemetry_received.connect(self.telemetry_received)
        self.thread.auxiliary_received.connect(self.auxiliary_received)
        self.thread.transmission_info_received.connect(self.transmission_info_received)

        self.thread.start()
        self.logger.info("Wątek odczytu danych uruchomiony.")

    def stop_reading(self):
        """Zatrzymuje wątek odczytu i zamyka port."""
        self.logger.info("Zatrzymywanie odczytu danych z portu szeregowego...")
        self.running = False

        if self.thread:
            self.thread.running = False
            self.thread.wait(1000)
            self.thread = None

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                self.logger.info(f"Port {self.port} został zamknięty.")
            except Exception as e:
                self.logger.error(f"Błąd przy zamykaniu portu szeregowego: {e}")

    # -------------------------------
    # Dekodowanie danych LoRa
    # -------------------------------
    def DecodeLine(self, line):
        self.logger.debug(f"Odebrano linię: {line}")
        if line.startswith("+TEST: RX"):
            match = re.search(r'"([0-9A-Fa-f]+)"', line)
            if match:
                try:
                    hex_data = match.group(1)
                    byte_data = bytes.fromhex(hex_data)
                    decoded_string = byte_data.decode('utf-8', errors='replace').strip()
                    self.logger.debug(f"Zdekodowany string: {decoded_string}")

                    prefix = decoded_string[0]
                    data = decoded_string[1:].split(";")

                    if prefix == "A":
                        if len(data) < 6:
                            self.logger.warning(f"Niewystarczająca liczba danych A: {data}")
                            return
                        telemetry = {
                            'pitch': float(data[0]),
                            'roll': float(data[1]),
                            'yaw': float(data[2]),
                            'ver_velocity': float(data[3]),
                            'altitude': float(data[4]),
                            'rbs': float(data[5])
                        }
                        self.last_telemetry = telemetry
                        self.telemetry_received.emit(telemetry)

                        self.logger.info(
                            f"Dane telemetryczne A: P={telemetry['pitch']}, R={telemetry['roll']}, "
                            f"H={telemetry['yaw']}, VV={telemetry['ver_velocity']}, "
                            f"ALT={telemetry['altitude']}, RBS={telemetry['rbs']}"
                        )

                    elif prefix == "B":
                        if len(data) < 3:
                            self.logger.warning(f"Niewystarczająca liczba danych B: {data}")
                            return
                        auxiliary = {
                            'latitude': data[0],
                            'longitude': data[1],
                            'status': int(data[2])
                        }
                        self.logger.info(
                            f"Dane pomocnicze B: LAT={auxiliary['latitude']}, "
                            f"LON={auxiliary['longitude']}, STS={auxiliary['status']}"
                        )
                        self.auxiliary_received.emit(auxiliary)
                    else:
                        self.logger.warning(f"Nieznany prefiks danych: {prefix}")

                except Exception as e:
                    self.logger.error(f"Błąd dekodowania danych: {e}")
            else:
                self.logger.debug("Nie znaleziono danych hex w linii RX")
        else:
            pattern = r"\+TEST: LEN:(\d+), RSSI:(-?\d+), SNR:(-?\d+)"
            match = re.search(pattern, line)
            if match:
                try:
                    transmission = {
                        'len': int(match.group(1)),
                        'rssi': int(match.group(2)),
                        'snr': int(match.group(3))
                    }
                    self.logger.debug(
                        f"Parametry transmisji: LEN={transmission['len']}, "
                        f"RSSI={transmission['rssi']}, SNR={transmission['snr']}"
                    )
                    if self.transmitter:
                        self.transmitter.last_transmission = transmission
                    self.transmission_info_received.emit(transmission)
                except Exception as e:
                    self.logger.warning(f"Błąd odczytu parametrów transmisji: {e}")
            else:
                self.logger.debug("Nie rozpoznano formatu linii transmisyjnej")

    def send_data(self, data: str):
        if self.ser is None or not self.ser.is_open:
            self.logger.warning("Port szeregowy nie jest dostępny – nie wysyłam")
            return

        try:
            if not data.endswith("\r\n"):
                data += "\r\n"
            self.ser.write(data.encode("utf-8"))
            self.logger.info(f"Wysłano przez UART: {data.strip()}")
        except Exception as e:
            self.logger.error(f"Błąd wysyłania danych przez UART: {e}")
