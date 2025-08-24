import sys
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QDialog,
                             QVBoxLayout, QHBoxLayout,
                             QLabel,
                             QComboBox, QPushButton,
                             QGroupBox, QLineEdit, QGridLayout)
from PyQt5.QtGui import QIcon
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
        self.setWindowIcon(QIcon(r'gui/resources/white_icon.png'))
        self.setWindowFlags(self.windowFlags() |
                            Qt.WindowType.WindowContextHelpButtonHint)

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

        # --- Port Group ---
        port_group = QGroupBox("Konfiguracja portu")
        port_layout = QGridLayout()

        port_layout.addWidget(QLabel("Port COM:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setFixedWidth(220)
        self.refresh_ports()
        port_layout.addWidget(self.port_combo, 0, 2)

        refresh_btn = QPushButton("Odśwież")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn, 0, 1)

        port_layout.addWidget(QLabel("Prędkość transmisji:"), 1, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        self.port_combo.setFixedWidth(220)
        port_layout.addWidget(self.baud_combo, 1, 2)

        port_group.setLayout(port_layout)
        layout.addWidget(port_group)

        # --- Server Group ---
        server_group = QGroupBox("Konfiguracja serwera")
        server_layout = QGridLayout()

        server_layout.addWidget(QLabel("Adres IP serwera:"), 0, 0)
        self.ip_input = QLineEdit()
        self.ip_input.setText("192.168.236.1")
        self.ip_input.setFixedWidth(220)
        server_layout.addWidget(self.ip_input, 0, 1, alignment=Qt.AlignRight)

        server_layout.addWidget(QLabel("Port serwera:"), 1, 0)
        self.port_input = QLineEdit()
        self.port_input.setText("65432")
        self.port_input.setFixedWidth(220)
        server_layout.addWidget(self.port_input, 1, 1,  alignment=Qt.AlignRight)

        server_group.setLayout(server_layout)
        layout.addWidget(server_group)

        # --- LoRa Group ---
        lora_group = QGroupBox("Konfiguracja LoRa")
        lora_layout = QGridLayout()

        lora_layout.addWidget(QLabel("Częstotliwość (F) (MHz):"), 0, 0)
        self.freq_combo = QComboBox()
        self.freq_combo.addItems(["433", "868", "915"])
        self.freq_combo.setCurrentText("868")
        lora_layout.addWidget(self.freq_combo, 0, 1)

        lora_layout.addWidget(QLabel("Spreading factor (SF):"), 1, 0)
        self.sf_combo = QComboBox()
        self.sf_combo.addItems(["7", "8", "9", "10", "11", "12"])
        self.sf_combo.setCurrentText("7")
        lora_layout.addWidget(self.sf_combo, 1, 1)

        lora_layout.addWidget(QLabel("Szerokość pasma (BW) (kHz):"), 2, 0)
        self.bw_combo = QComboBox()
        self.bw_combo.addItems(["125", "250", "500"])
        self.bw_combo.setCurrentText("250")
        lora_layout.addWidget(self.bw_combo, 2, 1)

        lora_layout.addWidget(QLabel("Preamble nadawania (TXPR):"), 3, 0)
        self.txpr_combo = QComboBox()
        self.txpr_combo.addItems(["7", "8", "9", "10", "11", "12"])
        self.txpr_combo.setCurrentText("8")
        lora_layout.addWidget(self.txpr_combo, 3, 1)

        lora_layout.addWidget(QLabel("Preamble odbierania (RXPR):"), 4, 0)
        self.rxpr_combo = QComboBox()
        self.rxpr_combo.addItems(["7", "8", "9", "10", "11", "12"])
        self.rxpr_combo.setCurrentText("8")
        lora_layout.addWidget(self.rxpr_combo, 4, 1)

        lora_layout.addWidget(QLabel("Moc nadawania (POW) (dBm):"), 5, 0)
        self.pow_combo = QComboBox()
        self.pow_combo.addItems(["2", "5", "8", "11", "14", "17", "20"])
        self.pow_combo.setCurrentText("14")
        lora_layout.addWidget(self.pow_combo, 5, 1)

        lora_layout.addWidget(QLabel("Suma kontrolna (CRC):"), 6, 0)
        self.crc_combo = QComboBox()
        self.crc_combo.addItems(["ON", "OFF"])
        self.crc_combo.setCurrentText("ON")
        lora_layout.addWidget(self.crc_combo, 6, 1)

        lora_layout.addWidget(QLabel("Odwrócenie bitu (IQ):"), 7, 0)
        self.iq_combo = QComboBox()
        self.iq_combo.addItems(["ON", "OFF"])
        self.iq_combo.setCurrentText("OFF")
        lora_layout.addWidget(self.iq_combo, 7, 1)

        lora_layout.addWidget(QLabel("Tryb LoRaWAN (NET):"), 8, 0)
        self.net_combo = QComboBox()
        self.net_combo.addItems(["ON", "OFF"])
        self.net_combo.setCurrentText("OFF")
        lora_layout.addWidget(self.net_combo, 8, 1)

        lora_group.setLayout(lora_layout)
        layout.addWidget(lora_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("Połącz i konfiguruj")
        connect_btn.clicked.connect(self.accept)
        connect_btn.setStyleSheet("background-color: #27ae60;")

        connect_no_lora_btn = QPushButton("Połącz bez konfiguracji")
        connect_no_lora_btn.clicked.connect(self.accept_no_lora)
        connect_no_lora_btn.setStyleSheet("background-color: #2980b9;")

        cancel_btn = QPushButton("Kontynuuj bez portu")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("background-color: #e74c3c;")

        btn_layout.addWidget(connect_btn)
        btn_layout.addWidget(connect_no_lora_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self.ip_input.setWhatsThis("Sprawdź adres IP komputera używając 'ipconfig' (Windows) lub 'ifconfig' / 'ip addr' (Linux/Mac) w terminalu.")
        self.port_input.setWhatsThis("Ustaw wysoką wartość, aby nic nie kolidowało.")
        self.port_combo.setWhatsThis("Wybierz port COM, do którego podłączony jest moduł.")
        refresh_btn.setWhatsThis("Kliknij, aby odświeżyć listę dostępnych portów szeregowych.")
        self.baud_combo.setWhatsThis("Wybierz prędkość transmisji (baud rate) dla komunikacji szeregowej.")
        self.freq_combo.setWhatsThis("Wybierz częstotliwość pracy LoRa (MHz).")
        self.sf_combo.setWhatsThis(
            "Wybierz spreading factor (SF) - im większa wartość, tym większy zasięg i mniejsza przepustowość.")
        self.bw_combo.setWhatsThis("Wybierz szerokość pasma LoRa (BW) w kHz.")
        self.txpr_combo.setWhatsThis("Wybierz długość preambuły nadawczej (TXPR).")
        self.rxpr_combo.setWhatsThis("Wybierz długość preambuły odbiorczej (RXPR).")
        self.pow_combo.setWhatsThis("Ustaw moc nadawania LoRa (w dBm).")
        self.crc_combo.setWhatsThis("Włącz lub wyłącz sumę kontrolną CRC.")
        self.iq_combo.setWhatsThis("Ustawienie odwrócenia bitów IQ (ON/OFF).")
        self.net_combo.setWhatsThis("Wybierz tryb LoRaWAN (ON - aktywny, OFF - klasyczny tryb LoRa).")
        connect_btn.setWhatsThis("Połącz z portem szeregowym i skonfiguruj moduł LoRa według ustawień.")
        connect_no_lora_btn.setWhatsThis("Połącz tylko z portem szeregowym bez konfiguracji LoRa.")
        cancel_btn.setWhatsThis("Zamknij okno i kontynuuj bez połączenia z portem szeregowym.")

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
            f"Wybrano konfigurację: port={self.port_name}, baudrate={self.baud_rate}, lora={self.lora_config}, network={self.network_config}")
        self.is_config_selected = True
        super().accept()

    def accept_no_lora(self):
        self.lora_config = None
        self._get_settings()
        self.logger.info(
            f"Wybrano konfigurację bez LoRa: port={self.port_name}, baudrate={self.baud_rate},  network={self.network_config}")
        self.is_config_selected = False
        super().accept()

    def _get_settings(self):
        if self.port_combo.currentText() == "Brak dostępnych portów":
            self.port_name = ""
        else:
            self.port_name = self.port_combo.currentText()
        self.baud_rate = int(self.baud_combo.currentText())
        self.network_config = {
            'ip_address': self.ip_input.currentText(),
            'port': self.ip_port.currentText()
        }
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
            'network': self.network_config,
            'lora_config': self.lora_config,
            'is_config_selected': self.is_config_selected
        }