import json
import sys
import logging
import platform
import threading
import traceback  # Add this import
from functools import partial
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import QTimer  # Add this import

from core.csv_handler import CsvHandler
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.utils import Utils
from core.config import Config
from core.gpio_reader import GpioReader
from core.network_handler import NetworkTransmitter
from core.serial_reader import SerialReader
import os


# Add global exception handler for uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = logging.getLogger('HORUS_FAS_logger')
    logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
    print(f"Critical error logged: {exc_value}")


sys.excepthook = handle_exception


# Add thread exception handler
def thread_exception_handler(args):
    logger = logging.getLogger('HORUS_FAS_logger')
    logger.error(
        f"Uncaught exception in thread {args.thread.name if args.thread else 'unknown'}: {args.exc_type.__name__}: {args.exc_value}")
    logger.error("Thread traceback: %s", ''.join(traceback.format_tb(args.exc_traceback)))


threading.excepthook = thread_exception_handler


def main():
    session_dir = Utils.create_session_directory()
    log_file = os.path.join(session_dir, 'app_events.log')

    logging.basicConfig(
        filename=log_file,
        filemode='a',
        level=logging.DEBUG,  # Changed to DEBUG for more verbose logging
        format='%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s - %(message)s',  # Added thread name
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('HORUS_FAS_logger')
    logger.info(f"Log file location: {log_file}")
    logger.info("Uruchamianie aplikacji")

    # Log main thread info
    logger.debug(f"Main thread: {threading.current_thread().name}, ID: {threading.get_ident()}")

    app = QApplication(sys.argv)
    logger.debug("QApplication instance created")

    # Add periodic thread monitoring
    def monitor_threads():
        active_threads = threading.enumerate()
        logger.debug(f"Active threads ({len(active_threads)}): {[t.name for t in active_threads]}")

        # Check if main window is responsive
        if 'window' in locals():
            logger.debug(f"Main window active: {window.isVisible()}")

    monitor_timer = QTimer()
    monitor_timer.timeout.connect(monitor_threads)
    monitor_timer.start(5000)  # Monitor every 5 seconds
    logger.debug("Thread monitor timer started")

    try:
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
        logger.debug("Initializing NetworkTransmitter with IP %s and port %s", network_config['ip_address'],
                     network_config['port'])
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

        csv_handler = CsvHandler()

        window = MainWindow(config, transmitter, gpio_reader, csv_handler)
        logger.debug("MainWindow initialized")

        transmitter.subscribe_on_partner_connected(window.on_partner_connected)
        transmitter.subscribe_on_partner_disconnected(window.on_partner_disconnected)
        transmitter.subscribe_on_data_received(lambda data: serial_reader.send_data(json.dumps(data)))
        logger.debug("NetworkTransmitter callbacks subscribed")

        connection_thread = threading.Thread(
            target=transmitter.connect,
            daemon=False,
            name="NetworkTransmitter-Connect"  # Name the thread for debugging
        )
        logger.debug(f"Created connection thread: {connection_thread.name}")
        connection_thread.start()
        logger.info(f"Thread started for transmitter.connect, thread alive: {connection_thread.is_alive()}")

        window.resize(800, 600)
        logger.debug("Main window resized to 800x600")
        window.show()
        logger.debug("Main window shown")

        # Log initial thread state
        monitor_threads()

        exit_code = app.exec_()
        logger.info(f"Aplikacja zakończona z kodem {exit_code}")

    except Exception as e:
        logger.exception("Exception in main application loop")
        exit_code = 1
    finally:
        logger.info("Starting cleanup process...")
        monitor_timer.stop()
        logger.debug("Thread monitor timer stopped")

        if 'serial_reader' in locals():
            logger.debug("Stopping serial reader...")
            serial_reader.stop_reading()
            logger.info("Zatrzymano odczyt z portu szeregowego")

        if 'transmitter' in locals():
            logger.debug("Closing network connection...")
            transmitter.close_connection()
            logger.info("Połączenie sieciowe zamknięte")

        if 'connection_thread' in locals():
            logger.debug(f"Waiting for connection thread to finish, alive: {connection_thread.is_alive()}")
            connection_thread.join(timeout=2)
            if connection_thread.is_alive():
                logger.warning("Connection thread did not finish within timeout period!")
            else:
                logger.debug("Connection thread finished successfully")

        logger.info("Cleanup completed")

    sys.exit(exit_code)


if __name__ == "__main__":
    operational_system = platform.system()
    if operational_system == 'Windows':
        os.environ["QT_QPA_PLATFORM"] = "windows"
    elif operational_system == 'Linux':
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    startup_logger = logging.getLogger('HORUS_FAS_logger')
    startup_logger.debug("Detected OS: %s, QT_QPA_PLATFORM set to %s", operational_system,
                         os.environ.get("QT_QPA_PLATFORM"))

    try:
        main()
    except Exception as e:
        logger = logging.getLogger('HORUS_FAS_logger')
        logger.exception("An exception has occurred during application startup")
        print("An exception has occurred: ", e)