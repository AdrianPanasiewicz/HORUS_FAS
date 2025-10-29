import re
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QTimer


class ProcessData(QObject):
    processed_data_ready = pyqtSignal(dict)

    def __init__(self, csv_handler):
        super().__init__()
        self.first_telemetry_packet_received = False
        self.first_auxiliary_packet_received = False
        self.logger = logging.getLogger(
            'HORUS_FAS.data_processor')
        self.csv_handler = csv_handler
        self.current_telemetry = None
        self.current_auxiliary = None
        self.current_transmission = None
        self.past = None

        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.process_and_emit)

    def handle_telemetry(self, telemetry):
        if not self.first_telemetry_packet_received:
            self.current_telemetry = telemetry
            self.first_telemetry_packet_received = True
            self.timeout_timer.start(500)
        else:
            if telemetry['snr'] > self.current_telemetry['snr']:
                self.current_telemetry = telemetry
            self.first_telemetry_packet_received = False
            self.process_and_emit()

    def handle_auxiliary(self, auxiliary):
        if not self.first_auxiliary_packet_received:
            self.current_auxiliary = auxiliary
            self.first_auxiliary_packet_received = True
            self.timeout_timer.start(500)
        else:
            if auxiliary['snr'] > self.current_auxiliary['snr']:
                self.current_auxiliary = auxiliary
            self.first_auxiliary_packet_received = False
            self.process_and_emit()

    def handle_transmission_info(self, transmission):
        # This is mostly legacy function, but this was left in because it might be useful in the future
        self.current_transmission = transmission
        # self.process_and_emit()

    def process_and_emit(self):
        try:
            if self.current_telemetry and self.current_auxiliary:
                combined_data = {**self.current_telemetry, **self.current_auxiliary}
                self.logger.debug(f"Combined telemetry + auxiliary data: {combined_data}")
            elif self.current_telemetry:
                combined_data = self.current_telemetry
                self.logger.debug(f"Telemetry-only data: {combined_data}")
            elif self.current_auxiliary:
                combined_data = self.current_auxiliary
                self.logger.debug(f"Auxiliary-only data: {combined_data}")
            else:
                return

            self.csv_handler.write_row(combined_data)
            self.processed_data_ready.emit(combined_data)

            self.current_telemetry = None
            self.current_auxiliary = None
            self.first_telemetry_packet_received = False
            self.first_auxiliary_packet_received = False
            self.timeout_timer.stop()

        except Exception as e:
            self.logger.exception(f"Error processing data: {e}")