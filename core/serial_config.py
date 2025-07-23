import sys
import logging
from PyQt5.QtWidgets import (QApplication, QDialog,
                             QVBoxLayout, QHBoxLayout,
                             QLabel,
                             QComboBox, QPushButton,
                             QGroupBox)
from PyQt5.QtCore import Qt
import serial.tools.list_ports


class SerialConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('HORUS_FAS.serial_config')
        self.setWindowTitle(
            "Konfiguracja portu szeregowego i LoRa")
        self.setFixedSize(490, 600)
        self.setStyleSheet("""
            QDialog { background-color: #2c3e50; }
            QLabel { color: #ecf0f1; font-size: 12px; }
            QComboBox, QPushButton, QGroupBox {
                background-color: #34495e; 
                color: #ecf0f1; 
                border: 1px solid #7f8c8d;
                padding: 5px;
                border-radius: 4px;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #34405e;
                color: #ecf0f1;
                selection-background-color: #3d566e;
                border: 1px solid #7f8c8d;
                font-size: 12px;
            }
            QGroupBox { 
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title { color: #1abc9c; }
            QPushButton:hover { background-color: #3d566e; }
            QPushButton:disabled { background-color: #2c3e50; color: #7f8c8d; }
        """)

        self.port_name = ""
        self.baud_rate = 9600
        self.lora_config = {
            'frequency': '868',
            'spread_factor': '7',
            'bandwidth': '125',
            'txpr': '8',
            'rxpr': '8',
            'power': '14',
            'crc': 'ON',
            'iq': 'OFF',
            'net': 'OFF',
        }
        self.is_config_selected = False

        layout = QVBoxLayout()

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port COM:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("Odśwież")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)
        layout.addLayout(port_layout)

        baud_layout = QHBoxLayout()
        baud_layout.addWidget(
            QLabel("Prędkość transmisji:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(
            ["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        baud_layout.addWidget(self.baud_combo)
        layout.addLayout(baud_layout)

        lora_group = QGroupBox("Konfiguracja LoRa")
        lora_layout = QVBoxLayout()

        freq_layout = QHBoxLayout()
        freq_layout.addWidget(
            QLabel("Częstotliwość (F) (MHz):"))
        self.freq_combo = QComboBox()
        self.freq_combo.addItems(["433", "868", "915"])
        self.freq_combo.setCurrentText("868")
        freq_layout.addWidget(self.freq_combo)
        lora_layout.addLayout(freq_layout)

        sf_layout = QHBoxLayout()
        sf_layout.addWidget(
            QLabel("Spreading factor (SF):"))
        self.sf_combo = QComboBox()
        self.sf_combo.addItems(["7", "8", "9", "10", "11", "12"])
        self.sf_combo.setCurrentText("7")
        sf_layout.addWidget(self.sf_combo)
        lora_layout.addLayout(sf_layout)

        bw_layout = QHBoxLayout()
        bw_layout.addWidget(
            QLabel("Szerokość pasma (BW) (kHz):"))
        self.bw_combo = QComboBox()
        self.bw_combo.addItems(["125", "250", "500"])
        self.bw_combo.setCurrentText("250")
        bw_layout.addWidget(self.bw_combo)
        lora_layout.addLayout(bw_layout)

        txpr_layout = QHBoxLayout()
        txpr_layout.addWidget(QLabel("Preamble nadawania (TXPR):"))
        self.txpr_combo = QComboBox()
        self.txpr_combo.addItems(
            ["7", "8", "9", "10", "11", "12"])
        self.txpr_combo.setCurrentText("8")
        txpr_layout.addWidget(self.txpr_combo)
        lora_layout.addLayout(txpr_layout)

        rxpr_layout = QHBoxLayout()
        rxpr_layout.addWidget(QLabel("Preamble odbierania (RXPR):"))
        self.rxpr_combo = QComboBox()
        self.rxpr_combo.addItems(["7", "8", "9", "10", "11", "12"])
        self.rxpr_combo.setCurrentText("8")
        rxpr_layout.addWidget(self.rxpr_combo)
        lora_layout.addLayout(rxpr_layout)

        pow_layout = QHBoxLayout()
        pow_layout.addWidget(QLabel("Moc nadawania (POW) (dBm):"))
        self.pow_combo = QComboBox()
        self.pow_combo.addItems(
            ["2", "5", "8", "11", "14", "17", "20"])
        self.pow_combo.setCurrentText("14")
        pow_layout.addWidget(self.pow_combo)
        lora_layout.addLayout(pow_layout)

        crc_layout = QHBoxLayout()
        crc_layout.addWidget(QLabel("Suma kontrolna (CRC):"))
        self.crc_combo = QComboBox()
        self.crc_combo.addItems(
            ["ON", "OFF"])
        self.crc_combo.setCurrentText("ON")
        crc_layout.addWidget(self.crc_combo)
        lora_layout.addLayout(crc_layout)

        iq_layout = QHBoxLayout()
        iq_layout.addWidget(QLabel("Odwrócenie bitu (IQ):"))
        self.iq_combo = QComboBox()
        self.iq_combo.addItems(
            ["ON", "OFF"])
        self.iq_combo.setCurrentText("OFF")
        iq_layout.addWidget(self.iq_combo)
        lora_layout.addLayout(iq_layout)

        net_layout = QHBoxLayout()
        net_layout.addWidget(QLabel("Tryb LoRaWAN (NET):"))
        self.net_combo = QComboBox()
        self.net_combo.addItems(
            ["ON", "OFF"])
        self.net_combo.setCurrentText("OFF")
        net_layout.addWidget(self.net_combo)
        lora_layout.addLayout(net_layout)

        lora_group.setLayout(lora_layout)
        layout.addWidget(lora_group)

        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("Połącz i konfiguruj")
        connect_btn.clicked.connect(self.accept)
        connect_btn.setStyleSheet(
            "background-color: #27ae60;")

        connect_no_lora_btn = QPushButton(
            "Połącz bez konfiguracji")
        connect_no_lora_btn.clicked.connect(
            self.accept_no_lora)
        connect_no_lora_btn.setStyleSheet(
            "background-color: #2980b9;")

        cancel_btn = QPushButton("Kontynuuj bez portu")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "background-color: #e74c3c;")

        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(connect_no_lora_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        if ports:
            for port in ports:
                self.port_combo.addItem(port.device)
        else:
            self.port_combo.addItem(
                "Brak dostępnych portów")
        self.logger.debug(
            f"Dostępne porty: {[p.device for p in ports]}")

    def accept(self):
        self._get_settings()
        self.logger.info(
            f"Wybrano konfigurację: port={self.port_name}, baudrate={self.baud_rate}, lora={self.lora_config}")
        self.is_config_selected = True
        super().accept()

    def accept_no_lora(self):
        self.lora_config = None
        self._get_settings()
        self.logger.info(
            f"Wybrano konfigurację bez LoRa: port={self.port_name}, baudrate={self.baud_rate}")
        self.is_config_selected = False
        super().accept()

    def _get_settings(self):
        if self.port_combo.currentText() == "Brak dostępnych portów":
            self.port_name = ""
        else:
            self.port_name = self.port_combo.currentText()
        self.baud_rate = int(self.baud_combo.currentText())
        if self.lora_config is not None:
            self.lora_config = {
                'frequency': self.freq_combo.currentText(),
                'spread_factor': self.sf_combo.currentText(),
                'bandwidth': self.bw_combo.currentText(),
                'txpr': self.txpr_combo.currentText(),
                'rxpr': self.rxpr_combo.currentText(),
                'power': self.pow_combo.currentText(),
                'crc': self.crc_combo.currentText(),
                'iq': self.iq_combo.currentText(),
                'net': self.net_combo.currentText(),
            }

    def get_settings(self):
        return {
            'port': self.port_name,
            'baudrate': self.baud_rate,
            'lora_config': self.lora_config,
            'is_config_selected': self.is_config_selected
        }