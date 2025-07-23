# csv_handler.py
import os
import csv
import logging
from datetime import datetime
from core.utils import Utils


class CsvHandler:
    def __init__(self):
        self.logger = logging.getLogger(
            'HORUS_FAS.csv_handler')
        self.session_dir = Utils.session_path
        self.filename = os.path.join(self.session_dir,
                                     'telemetry_data.csv')
        self.file = None
        self.writer = None
        self.header = ['timestamp', 'velocity', 'pitch',
                       'roll', 'status',
                       'altitude', 'latitude', 'longitude',
                       'len', 'rssi', 'snr']
        self.create_file_with_header()

    def create_file_with_header(self):
        try:
            with open(self.filename, 'w', newline='',
                      encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(self.header)
            self.logger.info(
                f"Created CSV file with header: {self.filename}")
            
            self.file = open(self.filename, 'a', newline='',
                             encoding='utf-8')
            self.writer = csv.writer(self.file,
                                     delimiter=';')
        except Exception as e:
            self.logger.error(
                f"Failed to create CSV file: {e}")

    def write_row(self, data_dict):
        if not self.writer:
            self.logger.error("CSV writer not initialized")
            return

        try:
            timestamp = datetime.now().isoformat()
            row = [timestamp]
            for key in self.header[1:]:
                row.append(data_dict.get(key, ''))

            self.writer.writerow(row)
            self.file.flush()
        except Exception as e:
            self.logger.error(f"Error writing to CSV: {e}")

    def close_file(self):
        if self.file:
            try:
                self.file.close()
                self.logger.info("CSV file closed")
            except Exception as e:
                self.logger.error(
                    f"Error closing CSV file: {e}")
            finally:
                self.file = None
                self.writer = None

    def __del__(self):
        self.close_file()