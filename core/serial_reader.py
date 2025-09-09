import datetime

import serial
import time
import re
import logging
import threading
from PyQt5.QtCore import QObject, pyqtSignal


class SerialReader(QObject):
    telemetry_received = pyqtSignal(dict)
    transmission_info_received = pyqtSignal(dict)

    def __init__(self, port="COM7", baudrate=9600, transmitter=None):
        super().__init__()
        self.logger = logging.getLogger('HORUS_FAS.serial_reader')
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.thread = None
        self.transmitter = transmitter

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.5)
            self.logger.info(f"Otworzono port {self.port} z baudrate {self.baudrate}")
        except serial.SerialException as e:
            self.ser = None
            self.logger.error(f"Błąd otwierania portu {self.port}: {e}")

    def start_reading(self):
        if self.running:
            self.logger.debug("start_reading() wywołane, ale wątek już działa")
            return

        self.running = True
        self.thread = threading.Thread(target=self._read_serial)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info("Wątek odczytu szeregowego uruchomiony")

    def stop_reading(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.logger.debug("Zatrzymywanie wątku odczytu szeregowego...")
            self.thread.join(timeout=1.0)
        self.logger.info("Wątek odczytu szeregowego zatrzymany")

    def _read_serial(self):
        self.logger.debug("Rozpoczęto działanie metody _read_serial")
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors='ignore').strip()
                if line:
                    self.logger.debug(f"Odczytano linię z portu szeregowego: {line}")
                    self.DecodeLine(line)
                else:
                    self.logger.debug("Odczytano pustą linię")
                time.sleep(0.25)
            except Exception as e:
                self.logger.error(f"Błąd odczytu: {e}")
                time.sleep(0.25)

    def DecodeLine(self, line):
        self.logger.debug(f"Odebrano linię: {line}")
        if line.startswith("+TEST: RX"):
            match = re.search(r'"([0-9A-Fa-f]+)"', line)
            if match:
                try:
                    hex_data = match.group(1)
                    self.logger.debug(f"Odczytany hex: {hex_data}")
                    byte_data = bytes.fromhex(hex_data)
                    decoded_string = byte_data.decode('utf-8', errors='replace')
                    self.logger.debug(f"Zdekodowany string: {decoded_string}")
                    data = decoded_string.split(";")

                    if len(data) < 7:
                        self.logger.warning(f"Niewystarczająca liczba danych: {data}")
                        return

                    telemetry = {
                        'velocity': float(data[0]),
                        'pitch': float(data[1]),
                        'roll': float(data[2]),
                        'status': int(data[3],2),
                        'altitude': float(data[4]),
                        'latitude': float(data[5]),
                        'longitude': float(data[6])
                    }

                    self.logger.info(
                        f"Dane telemetryczne: "
                        f"V={telemetry['velocity']}, "
                        f"P={telemetry['pitch']}, "
                        f"R={telemetry['roll']}, "
                        f"ST={telemetry['status']}, "
                        f"ALT={telemetry['altitude']}, "
                        f"LAT={telemetry['latitude']}, "
                        f"LON={telemetry['longitude']}")

                    self.telemetry_received.emit(telemetry)
                except Exception as e:
                    self.logger.error(f"Błąd dekodowania danych telemetrycznych: {e}")
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
                        f"Parametry transmisji: "
                        f"LEN={transmission['len']}, "
                        f"RSSI={transmission['rssi']}, "
                        f"SNR={transmission['snr']}")

                    if self.transmitter:
                        self.transmitter.last_transmission = transmission

                    self.transmission_info_received.emit(transmission)
                except Exception as e:
                    self.logger.warning(f"Błąd odczytu parametrów transmisji: {e}")
            else:
                self.logger.debug("Nie rozpoznano formatu linii transmisyjnej")

    def LoraSet(self, config, is_config_selected):
        if self.ser is None:
            self.logger.warning("Port szeregowy nie jest dostępny, pomijam konfigurację LoRa")
            return

        try:
            self.logger.info("Rozpoczynanie konfiguracji LoRa...")
            self.ser.write(b'at\r\n')
            self.logger.debug("Wyslano komendę: at")
            time.sleep(0.5)
            self.ser.write(b'at+mode=test\r\n')
            self.logger.debug("Wyslano komendę: at+mode=test")
            time.sleep(0.5)

            if is_config_selected:
                rf_cmd = (f'at+test=rfcfg,'
                          f'{config["frequency"]}.000,'
                          f'{config["spread_factor"]},'
                          f'{config["bandwidth"]},'
                          f'{config["txpr"]},'
                          f'{config["rxpr"]},'
                          f'{config["power"]},'
                          f'{config["crc"]},'
                          f'{config["iq"]},'
                          f'{config["net"]}\r\n')

                self.ser.write(rf_cmd.encode('utf-8'))
                self.logger.debug(f"Wyslano komendę konfiguracyjną: {rf_cmd.strip()}")
                time.sleep(0.5)
            else:
                self.logger.debug("Nie wyslano komendy konfiguracyjnej do LoRa - is_config_selected=False")

            self.ser.write(b'at+test=rxlrpkt\r\n')
            self.logger.debug("Wyslano komendę: at+test=rxlrpkt")
            time.sleep(0.5)

            self.ser.reset_input_buffer()
            self.logger.info("Konfiguracja LoRa zakończona pomyślnie")
        except Exception as e:
            self.logger.error(f"Błąd podczas konfiguracji LoRa: {e}")

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