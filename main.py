import sys
import logging
import platform
from PyQt5.QtWidgets import (QApplication, QDialog)
from gui.main_window import MainWindow
from core.serial_config import SerialConfigDialog
from core.utils import Utils
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
        config = {'port': "", 'baudrate': 9600, 'lora_config': None, 'is_config_selected': True}
        logger.info("Użytkownik zrezygnował z portu – używam domyślnych ustawień")

    window = MainWindow(config)
    window.resize(800, 600)
    window.show()
    exit_code = app.exec_()
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
