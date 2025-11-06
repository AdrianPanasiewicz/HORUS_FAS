import json
import sys
import logging
import platform
import threading
import time
import traceback
from functools import partial
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import QTimer, QThread

from core.csv_handler import CsvHandler
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.utils import Utils
from core.config import Config
from core.gpio_reader import GpioReader
from core.network_handler import NetworkTransmitter
from core.serial_reader import SerialReader
import os


# Enhanced exception handlers
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = logging.getLogger('HORUS_FAS_logger')
    logger.critical("UNCAUGHT EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))
    print(f"Critical error logged: {exc_value}")


sys.excepthook = handle_exception


def thread_exception_handler(args):
    logger = logging.getLogger('HORUS_FAS_logger')
    logger.error(
        f"UNCAUGHT EXCEPTION in thread {args.thread.name if args.thread else 'unknown'}: {args.exc_type.__name__}: {args.exc_value}")
    logger.error("Thread traceback: %s", ''.join(traceback.format_tb(args.exc_traceback)))


threading.excepthook = thread_exception_handler


def main():
    session_dir = Utils.create_session_directory()
    log_file = os.path.join(session_dir, 'app_events.log')

    logging.basicConfig(
        filename=log_file,
        filemode='a',
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('HORUS_FAS_logger')
    logger.info(f"Log file location: {log_file}")
    logger.info("Starting application")

    # Log main thread info
    main_thread = threading.current_thread()
    logger.debug(f"Main thread: {main_thread.name}, ID: {threading.get_ident()}, alive: {main_thread.is_alive()}")

    app = QApplication(sys.argv)
    logger.debug("QApplication instance created")

    # Enhanced thread monitoring with more details
    def monitor_threads():
        try:
            active_threads = threading.enumerate()
            thread_details = []
            for t in active_threads:
                thread_details.append(f"{t.name} (alive: {t.is_alive()}, daemon: {t.daemon})")

            logger.debug(f"Active threads ({len(active_threads)}): {thread_details}")

            # Check GUI responsiveness
            if 'window' in locals():
                logger.debug(f"Main window visible: {window.isVisible()}, active: {window.isActiveWindow()}")

            # Check if QApplication is processing events
            logger.debug(f"QApplication pending events: {app.hasPendingEvents()}")

        except Exception as e:
            logger.error(f"Error in thread monitor: {e}")

    monitor_timer = QTimer()
    monitor_timer.timeout.connect(monitor_threads)
    monitor_timer.start(3000)  # Monitor every 3 seconds
    logger.debug("Thread monitor timer started")

    try:
        config_dialog = SerialConfigDialog(default_ip_address=Config.DEFAULT_IP_ADDRESS)
        logger.debug("SerialConfigDialog initialized with default IP: %s", Config.DEFAULT_IP_ADDRESS)

        if config_dialog.exec_() == QDialog.Accepted:
            config = config_dialog.get_settings()
            logger.info(f"Port configuration loaded: {config}")
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
            logger.warning("User canceled port selection - using default settings: %s", config)

        network_config = config['network']
        logger.debug("Initializing NetworkTransmitter with IP %s and port %s", network_config['ip_address'],
                     network_config['port'])

        # Add timeout and connection status tracking
        transmitter = NetworkTransmitter(host=network_config['ip_address'], port=int(network_config['port']))
        logger.info("NetworkTransmitter initialized")

        # Track connection state
        connection_state = {"connected": False, "last_attempt": None}

        def wrapped_connect():
            try:
                logger.info("NetworkTransmitter.connect thread STARTED")
                connection_state["last_attempt"] = time.time()
                transmitter.connect()
                connection_state["connected"] = True
                logger.info("NetworkTransmitter.connect completed successfully")
            except Exception as e:
                logger.error(f"NetworkTransmitter.connect failed: {e}")
                logger.error(traceback.format_exc())
            finally:
                logger.info("NetworkTransmitter.connect thread FINISHED")

        # Only create SerialReader if we have a valid port
        serial_reader = None
        if config['port']:
            logger.info(f"Creating SerialReader on port {config['port']} with baudrate {config['baudrate']}")
            serial_reader = SerialReader(
                port=config['port'],
                baudrate=config['baudrate'],
                transmitter=transmitter
            )
            logger.info(f"SerialReader initialized on port {config['port']} and baudrate {config['baudrate']}")

            try:
                serial_reader.start_reading()
                logger.info("Started reading from serial port")
            except Exception as e:
                logger.error(f"Failed to start serial reading: {e}")

            if config['lora_config']:
                logger.debug("Configuring LoRa with settings: %s", config['lora_config'])
                serial_reader.LoraSet(config['lora_config'], config['is_config_selected'])
                logger.info("LoRa configuration set")
        else:
            logger.warning("No serial port configured - skipping SerialReader initialization")

        gpio_reader = GpioReader(Config.DEFAULT_GPIO_PIN)
        logger.debug("GpioReader initialized on pin %s", Config.DEFAULT_GPIO_PIN)

        if serial_reader:
            gpio_reader.subscribe_button_held(partial(serial_reader.send_data, "abort"))
            logger.debug("GPIO event subscribed to send abort signal")
        else:
            logger.warning("No serial reader available - GPIO abort signal disabled")

        csv_handler = CsvHandler()

        logger.debug("Creating MainWindow...")
        window = MainWindow(config, transmitter, gpio_reader, csv_handler, serial_reader)
        logger.debug("MainWindow initialized")

        # Enhanced callback logging
        def logged_partner_connected():
            logger.info("Partner connected callback triggered")
            window.on_partner_connected()

        def logged_partner_disconnected():
            logger.info("Partner disconnected callback triggered")
            window.on_partner_disconnected()

        def logged_data_received(data):
            logger.debug(f"Data received from network: {data}")
            if serial_reader:
                serial_reader.send_data(json.dumps(data))
            else:
                logger.warning("No serial reader available to send data")

        transmitter.subscribe_on_partner_connected(logged_partner_connected)
        transmitter.subscribe_on_partner_disconnected(logged_partner_disconnected)
        transmitter.subscribe_on_data_received(logged_data_received)
        logger.debug("NetworkTransmitter callbacks subscribed")

        # Start network connection with enhanced monitoring
        connection_thread = threading.Thread(
            target=wrapped_connect,
            daemon=False,
            name="NetworkTransmitter-Connect"
        )
        logger.debug(f"Created connection thread: {connection_thread.name}")
        connection_thread.start()
        logger.info(f"Connection thread started, alive: {connection_thread.is_alive()}")

        window.resize(800, 600)
        logger.debug("Main window resized to 800x600")
        window.show()
        logger.debug("Main window shown")

        # Initial thread state
        monitor_threads()

        logger.info("Entering main application event loop")
        exit_code = app.exec_()
        logger.info(f"Application exited with code {exit_code}")

    except Exception as e:
        logger.exception("Exception in main application loop")
        exit_code = 1
    finally:
        logger.info("Starting cleanup process...")

        # Stop monitoring first
        monitor_timer.stop()
        logger.debug("Thread monitor timer stopped")

        # Cleanup in reverse order of creation
        cleanup_timeout = 5  # seconds
        start_cleanup_time = time.time()

        # Stop serial reader
        if 'serial_reader' in locals() and serial_reader:
            logger.debug("Stopping serial reader...")
            try:
                serial_reader.stop_reading()
                logger.info("Stopped reading from serial port")
            except Exception as e:
                logger.error(f"Error stopping serial reader: {e}")

        # Close network connection
        if 'transmitter' in locals():
            logger.debug("Closing network connection...")
            try:
                transmitter.close_connection()
                logger.info("Network connection closed")
            except Exception as e:
                logger.error(f"Error closing network connection: {e}")

        # Wait for connection thread
        if 'connection_thread' in locals():
            logger.debug(f"Waiting for connection thread to finish, alive: {connection_thread.is_alive()}")
            connection_thread.join(timeout=2)
            if connection_thread.is_alive():
                logger.warning("Connection thread did not finish within timeout period!")
            else:
                logger.debug("Connection thread finished successfully")

        cleanup_duration = time.time() - start_cleanup_time
        logger.info(f"Cleanup completed in {cleanup_duration:.2f} seconds")

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