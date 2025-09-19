import json
import sys
import logging
import platform
import threading
from functools import partial
from PyQt5.QtWidgets import QApplication, QDialog
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.utils import Utils
from core.config import Config
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
    logger.debug("QApplication instance created")

    config_dialog = SerialConfigDialog(default_ip_address=Config.DEFAULT_IP_ADDRESS)
    logger.debug("SerialConfigDialog initialized with default IP: %s", Config.DEFAULT_IP_ADDRESS)

    if config_dialog.exec_() == QDialog.Accepted:
        config = config_dialog.get_settings()
        logger.info(f"Konfiguracja portu załadowana: {config}")
    else:
        config = {
            'port': "",
            'baudrate': Config.DEFAULT_BAUD_RATE,
            'lora_config': None,
            'is_config_selected': True,
            "network": {
                'ip_address': Config.DEFAULT_IP_ADDRESS,
                "port": Config.DEFAULT_IP_PORT
            }
        }
        logger.warning("Użytkownik zrezygnował z portu – używam domyślnych ustawień: %s", config)

    network_config = config['network']
    logger.debug("Initializing NetworkTransmitter with IP %s and port %s", network_config['ip_address'], network_config['port'])
    transmitter = NetworkTransmitter(host=network_config['ip_address'], port=int(network_config['port']))
    logger.info("NetworkTransmitter zainicjalizowany")

    serial_reader = SerialReader(
        port=config['port'],
        baudrate=config['baudrate'],
        transmitter=transmitter
    )
    logger.info(f"SerialReader zainicjalizowany na porcie {config['port']} i baudrate {config['baudrate']}")

    serial_reader.start_reading()
    logger.info("Rozpoczęto odczyt z portu szeregowego")

    if config['lora_config']:
        logger.debug("Configuring LoRa with settings: %s", config['lora_config'])
        serial_reader.LoraSet(config['lora_config'], config['is_config_selected'])
        logger.info("Konfiguracja LoRa ustawiona")

    gpio_reader = GpioReader(Config.DEFAULT_GPIO_PIN)
    logger.debug("GpioReader initialized on pin %s", Config.DEFAULT_GPIO_PIN)
    gpio_reader.subscribe_button_held(partial(serial_reader.send_data, "abort"))
    logger.debug("GPIO event subscribed to send abort signal")

    window = MainWindow(config, transmitter, gpio_reader)
    logger.debug("MainWindow initialized")

    transmitter.subscribe_on_partner_connected(window.on_partner_connected)
    transmitter.subscribe_on_partner_disconnected(window.on_partner_disconnected)
    transmitter.subscribe_on_data_received(lambda data: serial_reader.send_data(json.dumps(data)))
    logger.debug("NetworkTransmitter callbacks subscribed")

    connection_thread = threading.Thread(target=transmitter.connect, daemon=False)
    connection_thread.start()
    logger.info("Thread started for transmitter.connect")

    window.resize(800, 600)
    logger.debug("Main window resized to 800x600")
    window.show()
    logger.debug("Main window shown")

    exit_code = app.exec_()
    logger.info(f"Aplikacja zakończona z kodem {exit_code}")

    if 'serial_reader' in locals():
        serial_reader.stop_reading()
        logger.info("Zatrzymano odczyt z portu szeregowego")

    transmitter.close_connection()
    logger.info("Połączenie sieciowe zamknięte")

    connection_thread.join(timeout=2)

    sys.exit(exit_code)

if __name__ == "__main__":
    operational_system = platform.system()
    if operational_system == 'Windows':
        os.environ["QT_QPA_PLATFORM"] = "windows"
    elif operational_system == 'Linux':
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    logging.basicConfig(level=logging.DEBUG)
    startup_logger = logging.getLogger('HORUS_FAS_logger')
    startup_logger.debug("Detected OS: %s, QT_QPA_PLATFORM set to %s", operational_system, os.environ.get("QT_QPA_PLATFORM"))

    try:
        main()
    except Exception as e:
        logger = logging.getLogger('HORUS_FAS_logger')
        logger.exception("An exception has occurred")
        print("An exception has occurred: ", e)
