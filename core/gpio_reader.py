import logging
import gpiozero
import warnings
from gpiozero import Button, GPIODeviceError
from gpiozero.pins.mock import MockFactory


class GpioReader:
    def __init__(self, pin_number):
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

        self.when_held_subscribers = []
        self.button.when_held = self.when_button_held_callback

    def when_button_held_callback(self):
        self.logger.debug("Button held event triggered.")
        for subscriber in self.when_held_subscribers:
            self.logger.debug(f"Calling subscriber: {subscriber}")
            subscriber()

    def subscribe_when_held(self, callback):
        self.when_held_subscribers.append(callback)
        self.logger.info(f"Added {callback} as a subscriber to when_held_subscribers.")

    def unsubscribe_when_held(self, callback):
        if callback in self.when_held_subscribers:
            self.when_held_subscribers.remove(callback)
            self.logger.info(f"Removed {callback} from when_held_subscribers.")
        else:
            self.logger.warning(f"Tried to unsubscribe {callback}, but it was not found.")