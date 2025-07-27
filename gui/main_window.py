import logging
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QMainWindow,
                             QWidget, QSizePolicy,
                             QHBoxLayout, QLabel,
                             QGridLayout, QVBoxLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5 import QtCore
import folium
from core.serial_reader import SerialReader
from gui.live_plot import LivePlot
from datetime import datetime
from core.process_data import ProcessData
from core.csv_handler import CsvHandler


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.logger = logging.getLogger('HORUS_FAS.main_window')
        self.logger.info("Inicjalizacja głównego okna")

        self.now_str = ""

        self.current_data = {
            'ver_velocity': 0.0,
            'ver_accel': 0.0,
            'altitude': 0.0,
            'pitch': 0.0,
            'roll': 0.0,
            'yaw': 0.0,
            'status': 0,
            'latitude': 52.2549,
            'longitude': 20.9004,
            'len': 0,
            'rssi': 0,
            'snr': 0
        }

        # Inicjalizacja mapy
        self.current_lat = self.current_data['latitude']
        self.current_lng = self.current_data['longitude']
        self.map = None
        self.map_view = None

        self.csv_handler = CsvHandler()
        self.logger.info(
            f"CSV handler zainicjalizowany w sesji: {self.csv_handler.session_dir}")

        self.setWindowTitle("HORUS_FAS")
        self.setStyleSheet("""
            background-color: black; 
            color: white;
        """)
        self.setWindowIcon(QIcon(r'gui/white_icon.png'))
        self.setStyleSheet(
            open(r'gui/darkstyle.qss').read())

        self.serial = SerialReader(config['port'], config['baudrate'])
        self.logger.info(f"SerialReader zainicjalizowany na porcie {config['port']} z baudrate {config['baudrate']}")
        self.processor = ProcessData()
        self.logger.info(
            f"Singleton ProcessData zainicjalizowany")

        if config['lora_config']:
            self.serial.LoraSet(config['lora_config'], config['is_config_selected'])
            self.logger.info(f"Konfiguracja LoRa ustawiona: {config['lora_config']}")

        self.serial.telemetry_received.connect(self.processor.handle_telemetry)
        self.serial.transmission_info_received.connect(self.processor.handle_transmission_info)
        self.processor.processed_data_ready.connect(self.handle_processed_data)

        # Wykresy
        self.alt_plot = LivePlot(title="Altitude", color='b')
        self.ver_velocity_plot = LivePlot(title="Ver Velocity", color='r')
        self.ver_accel_plot = LivePlot(title="Ver Acceleration", color='c')
        self.pitch_plot = LivePlot(title="Pitch", color='y')
        self.roll_plot = LivePlot(title="Roll", color='g')
        self.yaw_plot = LivePlot(title="Yaw", color='g')

        # Mapa
        self.initialize_map()
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Expanding  # Pionowe rozciąganie
        )
        self.map_view.setStyleSheet("""
            QWebEngineView {
                background-color: black;
                border: 1px solid #444;
                border-radius: 3px;
            }
        """)
        self.update_map_view()

        # Główny układ (QGridLayout)
        central = QWidget()
        main_layout = QGridLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Górny wiersz - altitude i velocity
        top_plots_row = QHBoxLayout()
        top_plots_row.setContentsMargins(0, 0, 0, 0)
        top_plots_row.setSpacing(5)
        top_plots_row.addWidget(self.alt_plot, 1)
        top_plots_row.addWidget(self.ver_velocity_plot, 1)
        top_plots_row.addWidget(self.ver_accel_plot, 1)

        # Dolny wiersz - pitch i roll
        bottom_plots_row = QHBoxLayout()
        bottom_plots_row.setContentsMargins(0, 0, 0, 0)
        bottom_plots_row.setSpacing(5)
        bottom_plots_row.addWidget(self.pitch_plot, 1)
        bottom_plots_row.addWidget(self.roll_plot, 1)
        bottom_plots_row.addWidget(self.yaw_plot, 1)

        # Panel boczny
        lower_panel = self.create_lower_panel()

        # Ustawienie elementów w siatce
        main_layout.addLayout(top_plots_row, 0, 0)
        main_layout.addLayout(bottom_plots_row, 1, 0)
        main_layout.addWidget(lower_panel, 2, 0)

        main_layout.setRowStretch(0,4)
        main_layout.setRowStretch(1,4)
        main_layout.setRowStretch(2, 1)

        # Proporcje kolumn (80% wykresy, 20% panel boczny)
        main_layout.setColumnStretch(0, 1)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.serial.start_reading()

    def create_lower_panel(self):
        """Tworzy dolny panel z danymi i mapą"""
        panel = QWidget()
        main_layout = QHBoxLayout()  # Główny układ poziomy (dwie kolumny)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # Lewa kolumna - dane w 3 wierszach
        data_column = QWidget()
        data_layout = QVBoxLayout()
        data_layout.setContentsMargins(5, 5, 5, 5)
        data_layout.setSpacing(10)

        # Pierwszy wiersz - Altitude, Velocity, Acceleration
        row1 = QHBoxLayout()
        self.altitude_label = QLabel(f"Altitude: {self.current_data['altitude']:.2f} m")
        self.velocity_label = QLabel(f"Velocity: {self.current_data['ver_velocity']:.2f} m/s")
        self.accel_label = QLabel(f"Acceleration: {self.current_data['ver_accel']:.2f} m/s²")

        for label in [self.altitude_label, self.velocity_label, self.accel_label]:
            label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
            row1.addWidget(label, alignment=Qt.AlignLeft)

        # Drugi wiersz - Pitch, Roll, Yaw
        row2 = QHBoxLayout()
        self.pitch_label = QLabel(f"Pitch: {self.current_data['pitch']:.2f}°")
        self.roll_label = QLabel(f"Roll: {self.current_data['roll']:.2f}°")
        self.yaw_label = QLabel(f"Yaw: {self.current_data['yaw']:.2f}°")

        for label in [self.pitch_label, self.roll_label, self.yaw_label]:
            label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
            row2.addWidget(label, alignment=Qt.AlignLeft)

        # Trzeci wiersz - Position
        row3 = QHBoxLayout()
        self.position_label = QLabel(
            f"Pos: {self.current_data['latitude']:.6f}° N, {self.current_data['longitude']:.6f}° E")
        self.position_label.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        row3.addWidget(self.position_label, alignment=Qt.AlignLeft)

        # Dodanie wierszy do kolumny danych
        data_layout.addLayout(row1)
        data_layout.addSpacing(10)  # Dodatkowy odstęp po pierwszym wierszu
        data_layout.addLayout(row2)
        data_layout.addSpacing(10)  # Dodatkowy odstęp po drugim wierszu
        data_layout.addLayout(row3)
        data_layout.addStretch()  # Dodaje elastyczną przestrzeń na dole
        data_column.setLayout(data_layout)

        # Prawa kolumna - mapa
        map_column = QWidget()
        map_layout = QVBoxLayout()
        map_layout.setContentsMargins(0, 0, 0, 0)

        # Ustawienie stałej szerokości mapy (możesz dostosować)
        self.map_view.setFixedWidth(self.alt_plot.width()//2)
        self.map_view.setFixedHeight(200)
        map_layout.addWidget(self.map_view)
        map_column.setLayout(map_layout)

        # Podział przestrzeni - 60% dane, 40% mapa
        main_layout.addWidget(data_column, 70)
        main_layout.addWidget(map_column, 30)

        panel.setLayout(main_layout)
        panel.setMinimumHeight(200)
        return panel


    def initialize_map(self):
        """Inicjalizuje mapę z dynamicznym rozmiarem"""
        if hasattr(self, 'alt_plot') and self.alt_plot:
            plot_width = self.alt_plot.width() or 400
            map_width = max(plot_width - 15, 300)  # Nie mniej niż 300px
        else:
            map_width = 400

        map_height = 190 # Stała wysokość 180

        self.map = folium.Map(
            location=[self.current_lat, self.current_lng],
            zoom_start=15,
            width=map_width,
            height=map_height,
            control_scale=True,
            tiles='OpenStreetMap'
        )

        folium.Marker(
            [self.current_lat, self.current_lng],
            popup=f"LOTUS: {self.current_lat:.6f}, {self.current_lng:.6f}",
            icon=folium.Icon(color="green", icon="flag", prefix='fa')
        ).add_to(self.map)

        self.map.save('map.html')

    def resizeEvent(self, event):
        """Obsługa zmiany rozmiaru okna"""
        super().resizeEvent(event)
        # Poczekaj chwilę na aktualizację geometrii
        QtCore.QTimer.singleShot(50, self.adjust_map_width)

    def adjust_map_width(self):
        """Dostosowuje szerokość mapy do wykresów"""
        if hasattr(self, 'map_view') and self.map_view and hasattr(self, 'alt_plot'):
            # Pobierz rzeczywistą szerokość wykresu (po uwzględnieniu layoutu)
            plot_width = self.alt_plot.size().width()
            if plot_width > 100:  # Minimalna sensowna szerokość
                self.map_view.setFixedWidth(plot_width - 15)  # 10px mniej niż wykres
                self.update_map_size()

    def update_map_size(self):
        """Aktualizuje rozmiar mapy"""
        if self.map_view:
            # Pobierz aktualne rozmiary
            new_width = self.map_view.width()
            new_height = self.map_view.height()

            # Tylko jeśli rozmiar się zmienił
            if new_width > 0 and new_height > 0:
                self.initialize_map()
                self.update_map_view()

    def update_map_view(self):
        """Aktualizuje widok mapy z uwzględnieniem skalowania"""
        with open('map.html', 'r') as f:
            html = f.read()
            # Dodaj meta tag dla responsywności
            html = html.replace('<head>',
                                '<head><meta name="viewport" content="width=device-width, initial-scale=1.0">')
            self.map_view.setHtml(html)

    def handle_processed_data(self, data): #TODO to należy zintegrować z metodą poniżej
        self.logger.debug(
            f"Odebrano dane przetworzone: {data}")
        self.current_data = data
        try:
            self.update_data()
            self.csv_handler.write_row(data)

            if data['latitude'] != 0.0 and data[
                'longitude'] != 0.0:
                self.current_lat = data['latitude']
                self.current_lng = data['longitude']
                self.initialize_map()
                self.update_map_view()

        except Exception as e:
            self.logger.exception(
                f"Błąd w update_data(): {e}")

    def update_data(self):
        """Aktualizacja danych na interfejsie"""
        # Aktualizacja wykresów
        self.alt_plot.update_plot(self.current_data['altitude'])
        self.ver_velocity_plot.update_plot(self.current_data['ver_velocity'])
        self.ver_accel_plot.update_plot(self.current_data['ver_accel'])
        self.pitch_plot.update_plot(self.current_data['pitch'])
        self.roll_plot.update_plot(self.current_data['roll'])
        self.yaw_plot.update_plot(self.current_data['yaw'])

        self.label_info.setText(
            f"Pitch: {self.current_data['pitch']:.2f}°, Roll: {self.current_data['roll']:.2f}°\n"
            f"V: {self.current_data['ver_velocity']:.2f} m/s, H: {self.current_data['altitude']:.2f} m"
        )
        self.label_pos.setText(
            f"LON:\t{self.current_data['longitude']:.6f}° N \nLAT:\t{self.current_data['latitude']:.6f}° E"
        )

        self.now_str = datetime.now().strftime("%H:%M:%S")
        msg = (
            f"{self.current_data['ver_velocity']};{self.current_data['altitude']};"
            f"{self.current_data['pitch']};{self.current_data['roll']};"
            f"{self.current_data['status']};{self.current_data['latitude']};"
            f"{self.current_data['longitude']}"
        )
        self.logger.debug(f"Odebrano dane: {msg}")

        status = self.current_data['status']

    def closeEvent(self, event):
        """Zamykanie aplikacji"""
        self.serial.stop_reading()
        self.csv_handler.close_file()
        super().closeEvent(event)