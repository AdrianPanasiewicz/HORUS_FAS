import logging
import gpiozero
import warnings

from PyQt5.QtCore import QObject, pyqtSignal
from gpiozero import Button, GPIODeviceError
from gpiozero.pins.mock import MockFactory

class GpioReader(QObject):
    held = pyqtSignal()  # Qt signal for when the button is held

    def __init__(self, pin_number):
        super().__init__()
        self.logger = logging.getLogger("HORUS_FAS.gpio_reader")

        try:
            warnings.filterwarnings("ignore", message="Falling back from*")
            self.button = Button(pin_number)
            self.logger.info(f"Initialized Button on pin {pin_number} with real GPIO backend.")
        except Exception as e:
            warnings.warn("No GPIO backend available, falling back to MockFactory")
            self.logger.warning(f"No GPIO backend available ({e}), using MockFactory instead.")
            gpiozero.Device.pin_factory = MockFactory()
            self.button = Button(pin_number)
            self.logger.info(f"Initialized Button on pin {pin_number} with MockFactory.")

        self.button.when_held = self._when_button_held_callback

    def _when_button_held_callback(self):
        self.logger.debug("Button held event triggered.")
        self.held.emit()