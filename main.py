import sys
import logging
import platform
import threading
from PyQt5.QtWidgets import (QApplication, QDialog)
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.utils import Utils
from core.gpio_reader import GpioReader
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

    config_dialog = SerialConfigDialog()
    if config_dialog.exec_() == QDialog.Accepted:
        config = config_dialog.get_settings()
        logger.info(f"Konfiguracja portu załadowana: {config}")
    else:
        config = {'port': "", 'baudrate': 9600, 'lora_config': None, 'is_config_selected': True, "network": {'ip_address': "192.168.236.1", "port": "65432"}}
        logger.info("Użytkownik zrezygnował z portu – używam domyślnych ustawień")

    network_config = config['network']
    transmitter = NetworkTransmitter(host=network_config['ip_address'], port=int(network_config['port'])) # Trzeba zobaczyć, jaki jest przydzielony ip network adaptera
    logger.info("NetworkTransmitter zainicjalizowany")

    serial_reader = SerialReader(
        port=config['port'],
        baudrate=config['baudrate'],
        transmitter=transmitter
    )

    logger.info(f"SerialReader zainicjalizowany na porcie {config['port']}")

    serial_reader.start_reading()
    logger.info("Rozpoczęto odczyt z portu szeregowego")

    if config['lora_config']:
        serial_reader.LoraSet(config['lora_config'], config['is_config_selected'])
        logger.info(f"Konfiguracja LoRa ustawiona: {config['lora_config']}")

    window = MainWindow(config, transmitter)

    transmitter.subscribe_on_partner_connected(window.on_partner_connected)
    transmitter.subscribe_on_partner_disconnected(window.on_partner_disconnected)
    threading.Thread(target=transmitter.connect).start()

    gpio_reader = GpioReader(Config.DEFAULT_GPIO_PIN)

    window.resize(800, 600)
    window.show()
    exit_code = app.exec_()

    if 'serial_reader' in locals():
        serial_reader.stop_reading()

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
        logger = logging.getLogger('HORUS_FAS_logger')
        logger.error(f"An exception has occurred: {e}")
        print("An exception has occurred: ", e)
