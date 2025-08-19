import sys
import logging
import platform
from PyQt5.QtWidgets import (QApplication, QDialog)
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.utils import Utils
from core.network_handler import NetworkTransmitter
from core.serial_reader import SerialReader
import os

def main():
    session_dir = Utils.create_session_directory()
    log_file = os.path.join(session_dir, 'app_events.log')

    logging.basicConfig(
        filename=log_file,
        filemode='a',
        level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('HORUS_FAS_logger')
    logger.info(f"Log file location: {log_file}")
    logger.info("Uruchamianie aplikacji")

    app = QApplication(sys.argv)

    # DODANE: Inicjalizacja NetworkTransmitter
    transmitter = NetworkTransmitter(host='192.168.0.66', port=65432)
    logger.info("NetworkTransmitter zainicjalizowany")

    transmitter.connect()
    logger.info(f"Połączono z serwerem TCP {transmitter.host}:{transmitter.port}")

    config_dialog = SerialConfigDialog()
    if config_dialog.exec_() == QDialog.Accepted:
        config = config_dialog.get_settings()
        logger.info(f"Konfiguracja portu załadowana: {config}")
    else:
        config = {'port': "", 'baudrate': 9600, 'lora_config': None, 'is_config_selected': True}
        logger.info("Użytkownik zrezygnował z portu – używam domyślnych ustawień")

        # DODANE: Inicjalizacja SerialReader z przekazaniem transmittera
        serial_reader = SerialReader(
            port=config['port'],
            baudrate=config['baudrate'],
            transmitter=transmitter
        )
        logger.info(f"SerialReader zainicjalizowany na porcie {config['port']}")

        # DODANE: Uruchomienie odczytu z portu szeregowego
        serial_reader.start_reading()
        logger.info("Rozpoczęto odczyt z portu szeregowego")

        if config['lora_config']:
            serial_reader.LoraSet(config['lora_config'], config['is_config_selected'])
            logger.info(f"Konfiguracja LoRa ustawiona: {config['lora_config']}")

    window = MainWindow(config, transmitter)
    window.resize(800, 600)
    window.show()

    exit_code = app.exec_()

    # Zatrzymanie czytnika portu szeregowego
    if 'serial_reader' in locals():
        serial_reader.stop_reading()

    # Zamknięcie połączenia TCP (klient)
    transmitter.close_connection()

    logger.info(f"Aplikacja zakończona z kodem {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    operational_system = platform.system()
    if operational_system == 'Windows':
        os.environ["QT_QPA_PLATFORM"] = "windows"
    elif operational_system == 'Linux':
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    try:
        main()
    except Exception as e:
        print("An exception has occurred: ", e)
