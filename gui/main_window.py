import os
import platform
import subprocess
import logging
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QMainWindow,
                             QWidget, QSizePolicy,
                             QHBoxLayout, QLabel,
                             QGridLayout, QVBoxLayout, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5 import QtCore
import folium
from core.network_handler import NetworkTransmitter
from core.serial_reader import SerialReader
from gui.live_plot import LivePlot
from datetime import datetime
from core.process_data import ProcessData
from core.csv_handler import CsvHandler
import random


class MainWindow(QMainWindow):
    def __init__(self, config, transmitter):
        super().__init__()
        self.transmitter = transmitter

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
        # self.setStyleSheet("""
        #     background-color: black;
        #     color: white;
        # """)
        self.setWindowIcon(QIcon(r'gui/white_icon.png'))
        self.setStyleSheet(
            open(r'gui/resources/themes/dark_blue.qss').read())

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
        self.alt_plot = LivePlot(title="Altitude", color='b', time_window=30, max_points=50000)
        self.ver_velocity_plot = LivePlot(title="Ver Velocity", color='r', time_window=30, max_points=50000)
        self.ver_accel_plot = LivePlot(title="Ver Acceleration", color='c', time_window=30, max_points=50000)
        self.pitch_plot = LivePlot(title="Pitch", color='y', time_window=30, max_points=50000)
        self.roll_plot = LivePlot(title="Roll", color='g', time_window=30, max_points=50000)
        self.yaw_plot = LivePlot(title="Yaw", color='w', time_window=30, max_points=50000)

        # Mapa
        self.initialize_map()
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding  # Pionowe rozciąganie
        )
        # self.map_view.setStyleSheet("""
        #     QWebEngineView {
        #         background-color: black;
        #         border: 1px solid #444;
        #         border-radius: 3px;
        #     }
        # """)
        self.update_map_view()

        # Główny układ (QGridLayout)
        central = QWidget()
        main_layout = QGridLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Lewa kolumna - altitude i velocity
        left_plots_column = QVBoxLayout()
        left_plots_column.setContentsMargins(0, 0, 0, 0)
        left_plots_column.setSpacing(5)
        left_plots_column.addWidget(self.alt_plot, 1)
        left_plots_column.addWidget(self.ver_velocity_plot, 1)
        left_plots_column.addWidget(self.ver_accel_plot, 1)

        # Środkowa kolumna - pitch i roll
        middle_plots_column = QVBoxLayout()
        middle_plots_column.setContentsMargins(0, 0, 0, 0)
        middle_plots_column.setSpacing(5)
        middle_plots_column.addWidget(self.pitch_plot, 1)
        middle_plots_column.addWidget(self.roll_plot, 1)
        middle_plots_column.addWidget(self.yaw_plot, 1)

        # Panel boczny
        right_panel = self.create_right_panel()

        # Ustawienie elementów w siatce
        main_layout.addLayout(left_plots_column, 0, 0)
        main_layout.addLayout(middle_plots_column, 0, 1)
        main_layout.addWidget(right_panel, 0, 2)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.serial.start_reading()

        # Testing
        QtCore.QTimer.singleShot(1000, lambda: self.start_random_test(30))

        self.setup_status_bar()
        self.declare_menus()

    def create_right_panel(self):
        """Tworzy dolny panel z danymi i mapą"""
        panel = QWidget()
        main_layout = QVBoxLayout()  # Główny układ poziomy (dwie kolumny)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        data_labels = QWidget()
        data_layout = QVBoxLayout()
        data_layout.setContentsMargins(5, 5, 5, 5)
        data_layout.setSpacing(10)

        # Prawa kolumna - mapa
        map_widget = QWidget()
        map_layout = QVBoxLayout()
        map_layout.setContentsMargins(0, 0, 0, 0)

        # Ustawienie stałej szerokości mapy (możesz dostosować)
        self.map_view.setFixedWidth(self.alt_plot.width()//2)
        # self.map_view.setFixedHeight(200)
        map_layout.addWidget(self.map_view)
        map_widget.setLayout(map_layout)

        row = QVBoxLayout()
        self.altitude_label = QLabel(f"Altitude: {self.current_data['altitude']:.2f} m")
        self.velocity_label = QLabel(f"Velocity: {self.current_data['ver_velocity']:.2f} m/s")
        self.accel_label = QLabel(f"Acceleration: {self.current_data['ver_accel']:.2f} m/s²")
        self.pitch_label = QLabel(f"Pitch: {self.current_data['pitch']:.2f}°")
        self.roll_label = QLabel(f"Roll: {self.current_data['roll']:.2f}°")
        self.yaw_label = QLabel(f"Yaw: {self.current_data['yaw']:.2f}°")
        self.position_label = QLabel(f"Pos: {self.current_data['latitude']:.6f}° N, {self.current_data['longitude']:.6f}° E")

        for label in [self.altitude_label, self.velocity_label, self.accel_label, self.pitch_label,
                      self.roll_label, self.yaw_label, self.position_label]:
            label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
            row.addWidget(label, alignment=Qt.AlignLeft)

        # Dodanie wierszy do kolumny danych
        data_layout.addLayout(row)
        # data_layout.addSpacing(10)  # Dodatkowy odstęp po pierwszym wierszu
        data_labels.setLayout(data_layout)

        main_layout.addWidget(map_widget, 30)
        main_layout.addWidget(data_labels, 70)
        panel.setLayout(main_layout)
        panel.setMinimumHeight(200)
        return panel

    def setup_status_bar(self):
        self.status_bar_visible = True
        self.status_logo = QLabel()
        self.status_logo.setFixedSize(24, 24)
        self.status_logo.setScaledContents(True)
        logo_pixmap = QPixmap(r"gui/resources/black_icon_without_background.png").scaled(30, 30)
        self.status_logo.setStyleSheet("background: transparent;")
        self.status_logo.setPixmap(logo_pixmap)
        self.statusBar().addWidget(self.status_logo)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.status_packet_label = QLabel(f"Last received packet: {current_time} s")
        self.status_packet_label.setStyleSheet("background: transparent; font-size: 14px;")
        self.statusBar().addWidget(self.status_packet_label)

        spacer1 = QLabel()
        spacer1.setStyleSheet("background: transparent;")
        self.statusBar().addWidget(spacer1, 1)

        self.status_title_label = QLabel("HORUS Flight Analysis Station  \t\t\t")
        self.status_title_label.setStyleSheet("background: transparent; font-size: 14px; font-weight: bold;")
        self.statusBar().addWidget(self.status_title_label)

        spacer2 = QLabel()
        spacer2.setStyleSheet("background: transparent;")
        self.statusBar().addWidget(spacer2, 1)

        self.heartbeat_placeholder = QLabel("●")
        self.heartbeat_placeholder.setStyleSheet("background: transparent; color: transparent; font-size: 14px;")
        self.statusBar().addPermanentWidget(self.heartbeat_placeholder)

        self.setup_heartbeat()

    def setup_heartbeat(self):
        if not hasattr(self, 'heartbeat_timer'):
            self.heartbeat_timer = QTimer()
            self.heartbeat_timer.timeout.connect(self.blink_heartbeat)
            self.heartbeat_state = True

        self.heartbeat_active = True
        self.heartbeat_timer.start(500)

    def blink_heartbeat(self):
        if hasattr(self, 'heartbeat_active') and self.heartbeat_active:
            self.heartbeat_state = not self.heartbeat_state
            color = "red" if self.heartbeat_state else "transparent"
            self.heartbeat_placeholder.setStyleSheet(f"color: {color}; font-size: 14px;")


    def initialize_map(self):
        """Inicjalizuje mapę z dynamicznym rozmiarem"""
        self.map = folium.Map(
            location=[self.current_lat, self.current_lng],
            zoom_start=15,
            control_scale=True,
            tiles='OpenStreetMap'
        )

        folium.Marker(
            [self.current_lat, self.current_lng],
            popup=f"LOTUS: {self.current_lat:.6f}, {self.current_lng:.6f}",
            icon=folium.Icon(color="green", icon="flag", prefix='LT')
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

    def declare_menus(self):
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.view_menu = self.menu.addMenu("View")
        self.theme_menu = self.view_menu.addMenu("Themes")
        # self.timespan_menu = self.view_menu.addMenu("Timespan")
        # self.tools_menu = self.menu.addMenu("Tools")
        # self.test_menu = self.menu.addMenu("Test")
        self.help_menu = self.menu.addMenu("Help")

        self.file_menu.addAction("Exit", self.close)
        self.file_menu.addAction("Open Session Directory", self.open_session_directory)
        self.file_menu.addAction("Show Session Path", self.show_session_directory_path)
        self.file_menu.addSeparator()
        self.file_menu.addAction("Export Plots as PNG", lambda: self.export_plots("png"))
        self.file_menu.addAction("Export Plots as SVG", lambda: self.export_plots("svg"))

        self.view_menu.addAction("Toggle Fullscreen", self.toggle_fullscreen)

        self.status_bar_action = self.view_menu.addAction("Status Bar")
        self.status_bar_action.setCheckable(True)
        self.status_bar_action.setChecked(True)
        self.status_bar_action.triggered.connect(self.toggle_status_bar)

        self.heartbeat_action = self.view_menu.addAction("Heartbeat")
        self.heartbeat_action.setCheckable(True)
        self.heartbeat_action.setChecked(True)
        self.heartbeat_action.triggered.connect(self.toggle_heartbeat)

        self.view_menu.addSeparator()

        # self.crosshair_action = self.view_menu.addAction("Crosshair")
        # self.crosshair_action.setCheckable(True)
        # self.crosshair_action.setChecked(False)
        # # self.crosshair_action.triggered.connect(self.toggle_crosshairs)
        #
        # self.auto_zoom_action = self.view_menu.addAction("Auto-Zoom")
        # self.auto_zoom_action.setCheckable(True)
        # self.auto_zoom_action.setChecked(True)
        # # self.auto_zoom_action.triggered.connect(self.toggle_auto_zoom)
        #
        # self.data_markers_action = self.view_menu.addAction("Data Markers")
        # self.data_markers_action.setCheckable(True)
        # self.data_markers_action.setChecked(True)
        # # self.data_markers_action.triggered.connect(self.toggle_data_markers)
        #
        # self.grid_action = self.view_menu.addAction("Grid")
        # self.grid_action.setCheckable(True)
        # self.grid_action.setChecked(True)
        # # self.grid_action.triggered.connect(self.toggle_plot_grid)

        # self.view_menu.addSeparator()
        # self.view_menu.addAction("Clear Plots", self.clear_plots)
        # self.view_menu.addAction("Clear All", self.clear_all)

        self.help_menu.addAction("About application", self.show_about_app_dialog)
        self.help_menu.addAction("About KNS LiK", self.show_about_kns_dialog)

        # self.test_menu.addAction("Start Plot Simulation", self.start_plot_simulation)
        # self.test_menu.addAction("Stop Plot Simulation", self.stop_plot_simulation)
        # self.plot_speed_menu = self.test_menu.addMenu("Plot Simulation Speed")
        # self.test_menu.addAction("Start Map Simulation", self.start_map_simulation)
        # self.test_menu.addAction("Stop Map Simulation", self.stop_map_simulation)

        self.themes = {
            "Dark Blue": "dark_blue.qss",
            "Gray": "gray.qss",
            "Marble": "marble.qss",
            "Slick Dark": "slick_dark.qss",
            "Uniform Dark": "unform_dark.qss"
        }

        self.theme_actions = {}
        for theme_name, theme_file in self.themes.items():
            action = self.theme_menu.addAction(theme_name)
            action.triggered.connect(lambda _, t=theme_file: self.apply_theme(t))
            self.theme_actions[theme_name] = action

        # self.timespan_menu.addAction("30 seconds", lambda: self.change_plot_timespans(30))
        # self.timespan_menu.addAction("60 seconds", lambda: self.change_plot_timespans(60))
        # self.timespan_menu.addAction("90 seconds", lambda: self.change_plot_timespans(90))
        # self.timespan_menu.addAction("120 seconds", lambda: self.change_plot_timespans(120))
        #
        # serial_menu = self.tools_menu.addMenu("Serial Configuration")
        # serial_menu.addAction("Scan Ports", self.scan_serial_ports)
        # serial_menu.addAction("Change Baud Rate", self.change_baud_rate)
        # serial_menu.addAction("Reconnect Serial", self.reconnect_serial)
        # self.tools_menu.addAction("Configure Filters", self.configure_filters)
        # self.tools_menu.addSeparator()
        # self.tools_menu.addAction("Calculate Statistics", self.calculate_statistics)

        # self.plot_speed_actions = {}
        #
        # speeds = {
        #     "Fast (250 ms)": 250,
        #     "Normal (500 ms)": 500,
        #     "Slow (1000 ms)": 1000,
        #     "Very Slow (2000 ms)": 2000,
        # }
        #
        # for label, interval in speeds.items():
        #     action = self.plot_speed_menu.addAction(label)
        #     action.setCheckable(True)
        #     action.triggered.connect(lambda checked, i=interval: self.set_plot_sim_speed(i))
        #     self.plot_speed_actions[label] = action

        # self.plot_speed_actions["Normal (500 ms)"].setChecked(True)
        # self.plot_sim_interval = 500

    def apply_theme(self, theme_file):
        try:
            theme_path = os.path.join("gui", "resources", "themes", theme_file)
            with open(theme_path, "r") as file:
                self.setStyleSheet(file.read())
            self.logger.info(f"Theme changed to: {theme_file}")
        except Exception as e:
            self.logger.error(f"Error loading theme {theme_file}: {str(e)}")

    def toggle_status_bar(self):
        state = self.status_bar_action.isChecked()
        if state:
            self.statusBar().show()
        else:
            self.statusBar().hide()
        self.status_bar_visible = state

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.logger.info(f"Status bar toggled to {status}")

    def export_plots(self, format):
        try:
            session_dir = self.csv_handler.session_dir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            plots = {
                "altitude": self.alt_plot,
                "vertical_velocity": self.ver_velocity_plot,
                "vertical_acceleration": self.ver_accel_plot,
                "pitch_plot": self.pitch_plot,
                "roll_plot": self.roll_plot,
                "yaw_plot": self.yaw_plot
            }

            for name, plot in plots.items():
                filename = os.path.join(session_dir, f"{name}_plot_{timestamp}.{format}")
                if format == "png":
                    plot.export_to_png(filename)
                elif format == "svg":
                    plot.export_to_svg(filename)

            self.logger.info(f"Exported plots as {format.upper()} files")
        except Exception as e:
            self.logger.error(f"Error exporting plots: {str(e)}")
            QMessageBox.critical(self, "Export Error", f"Failed to export plots: {str(e)}")

    def update_map_view(self):
        """Aktualizuje widok mapy z uwzględnieniem skalowania"""
        with open('map.html', 'r') as f:
            html = f.read()
            # Dodaj meta tag dla responsywności
            html = html.replace('<head>',
                                '<head><meta name="viewport" content="width=device-width, initial-scale=1.0">')
            self.map_view.setHtml(html)

    def handle_processed_data(self, data):
        try:
            # 1. Aktualizacja bieżących danych
            self.current_data = data

            # 2. Aktualizacja GUI
            self.update_data()

            # 3. Zapis do CSV
            self.csv_handler.write_row(data)

            print(f"DEBUG: Przetworzono dane do wysłania: {data}")

            # 4. Wysyłanie do Stacji 2
            transmit_data = {
                'timestamp': datetime.now().isoformat(),
                'telemetry': {
                    'velocity': data.get('ver_velocity', 0),
                    'altitude': data.get('altitude', 0),
                    'latitude': data.get('latitude', 0),
                    'longitude': data.get('longitude', 0),
                    'pitch': data.get('pitch', 0),
                    'roll': data.get('roll', 0),
                    'yaw': data.get('yaw', 0)
                },
                'transmission': {
                    'rssi': data.get('rssi', 0),
                    'snr': data.get('snr', 0)
                }
            }

            print(f"DEBUG: Dane przed wysłaniem: {transmit_data}")

            self.transmitter.send_data(transmit_data)

        except Exception as e:
            self.logger.error(f"Błąd w handle_processed_data: {e}")

    def show_about_app_dialog(self):
        about_text = """
        <div style="text-align: justify;">
            <h2>HOURS Flight Analysis Station</h2>
            <p><b>Version:</b> 0.1.0</p>
            <p><b>Description:</b> The ground station is responsible for processing and displaying data regarding 
            the flight of a sounding rocket. It is a subcomponent of a HOURS project, which is also as a part of a 
            larger LOTUS ONE project Scientific Association of Aviation and Astronautics Students of MUT.</p>
            <p><b>Authors:</b> Adrian Panasiewicz, Filip Sudak</p>
            <p><b>Copyright:</b> © 2025 KNS LiK </p>
        </div>
        """

        QMessageBox.about(self, "About HORUS-CSS", about_text)

    def show_about_kns_dialog(self):
        about_text = """
        <div style="text-align: justify;">
            <h2>Scientific Association of Aviation and Astronautics Students of MUT</h2>
            <p><b>Description:</b> The Scientific Circle of Aviation and Astronautics (KNS) brings together the best 
            civilian and military students studying Aviation and Astronautics, as well as students from other fields 
            present at the Faculty of Mechatronics, Armament, and Aviation, who deepen their knowledge in collaboration 
            with university staff.</p>
            <p>The main objectives of the Scientific Circle of Aviation and Astronautics Students are:</p>
            <ul>
                <li>Developing engineering skills in designing and building UAVs and other flying structures;</li>
                <li>Fostering students' interests in building and developing UAVs, model rockets, and topics related to 
                aviation technologies;</li>
                <li>Enhancing skills in using market-available software related to engineering work;</li>
                <li>Developing soft skills in project management, teamwork, and team communication.</li>
            </ul>
            The Circle plans to develop the existing skills of its members, improve their soft and technical 
            competencies, and, above all, undertake projects characterized by a higher level of complexity and 
            advanced technical and technological sophistication.
        </div>
        """
        QMessageBox.about(self, "About KNS LiK", about_text)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def open_session_directory(self):

        session_path = self.csv_handler.session_dir

        if not os.path.exists(session_path):
            QMessageBox.warning(
                self,
                "Directory Not Found",
                f"Session directory not found:\n{session_path}"
            )
            return

        try:
            if platform.system() == "Windows":
                os.startfile(session_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", session_path])
            else:
                subprocess.Popen(["xdg-open", session_path])
        except Exception as e:
            self.logger.error(f"Error opening session directory: {str(e)}")
            QMessageBox.critical(
                self,
                "Error Opening Directory",
                f"Could not open session directory:\n{str(e)}"
            )

    def show_session_directory_path(self):
        session_path = self.csv_handler.session_dir
        QMessageBox.information(
            self,
            "Session Directory Path",
            f"Current session files are stored at:\n{session_path}"
        )

    def toggle_heartbeat(self):
        state = self.heartbeat_action.isChecked()
        if state:
            self.heartbeat_timer.start(500)
            self.heartbeat_active = True
        else:
            self.heartbeat_timer.stop()
            self.heartbeat_placeholder.setStyleSheet("color: transparent; font-size: 14px;")
            self.heartbeat_active = False

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        # self.terminal_output.append(
        #     f">{current_time}: <span style='color: lightblue;'>Heartbeat turned {status}</span>")
        self.logger.info(f"Heartbeat toggled to {status}")

    def update_data(self):
        """Aktualizacja danych na interfejsie"""
        # Aktualizacja wykresów
        self.alt_plot.update_plot(self.current_data['altitude'])
        self.ver_velocity_plot.update_plot(self.current_data['ver_velocity'])
        self.ver_accel_plot.update_plot(self.current_data['ver_accel'])
        self.pitch_plot.update_plot(self.current_data['pitch'])
        self.roll_plot.update_plot(self.current_data['roll'])
        self.yaw_plot.update_plot(self.current_data['yaw'])

        self.altitude_label.setText(f"Altitude: {self.current_data['altitude']:.2f} m")
        self.velocity_label.setText(f"Velocity: {self.current_data['ver_velocity']:.2f} m/s")
        self.accel_label.setText(f"Acceleration: {self.current_data['ver_accel']:.2f} m/s²")
        self.pitch_label.setText(f"Pitch: {self.current_data['pitch']:.2f}°")
        self.roll_label.setText(f"Roll: {self.current_data['roll']:.2f}°")
        self.yaw_label.setText(f"Yaw: {self.current_data['yaw']:.2f}°")
        self.position_label.setText(f"Pos: {self.current_data['latitude']:.6f}° N, {self.current_data['longitude']:.6f}° E")

        '''
        self.label_info.setText(
            f"Pitch: {self.current_data['pitch']:.2f}°, Roll: {self.current_data['roll']:.2f}°\n"
            f"V: {self.current_data['ver_velocity']:.2f} m/s, H: {self.current_data['altitude']:.2f} m"
        )
        self.label_pos.setText(
            f"LON:\t{self.current_data['longitude']:.6f}° N \nLAT:\t{self.current_data['latitude']:.6f}° E"
        )
        '''

        self.now_str = datetime.now().strftime("%H:%M:%S")
        msg = (
            f"{self.current_data['ver_velocity']};{self.current_data['altitude']};"
            f"{self.current_data['pitch']};{self.current_data['roll']};"
            f"{self.current_data['status']};{self.current_data['latitude']};"
            f"{self.current_data['longitude']}"
        )
        self.logger.debug(f"Odebrano dane: {msg}")

        status = self.current_data['status']

    def start_random_test(self, duration=30):
        """Rozpoczyna test z losowymi wartościami na wszystkich wykresach"""
        # 1. Reset wszystkich wykresów
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]

        for plot in plots:
            plot.reset_time()  # Reset czasu i danych

        # 2. Inicjalizacja timera
        if hasattr(self, 'test_timer') and self.test_timer:
            self.test_timer.stop()  # Bezpieczne zatrzymanie istniejącego timera

        self.test_timer = QtCore.QTimer()
        self.test_timer.setTimerType(QtCore.Qt.PreciseTimer)  # Dokładniejszy timer
        self.test_timer.timeout.connect(self._generate_test_data)

        # 3. Ustawienie interwału (100ms = 0.1s)
        self.test_timer.start(1000)

        # 4. Automatyczne zatrzymanie po zadanym czasie
        QtCore.QTimer.singleShot(
            duration * 1000,  # Konwersja na milisekundy
            lambda: self.stop_random_test() or self.logger.info("Test zakończony")
        )

        self.logger.info(f"Rozpoczęto test na {duration} sekund")

    def stop_random_test(self):
        """Zatrzymuje test losowych wartości"""
        if hasattr(self, 'test_timer') and self.test_timer:
            self.test_timer.stop()

    def _generate_test_data(self):
        """Generuje losowe dane testowe"""
        test_data = {
            'ver_velocity': random.uniform(-10, 10),
            'ver_accel': random.uniform(-2, 2),
            'altitude': random.uniform(0, 1000),
            'pitch': random.uniform(-90, 90),
            'roll': random.uniform(-90, 90),
            'yaw': random.uniform(0, 360),
            'status': random.randint(0, 3),
            'latitude': 52.2549 + random.uniform(-0.01, 0.01),
            'longitude': 20.9004 + random.uniform(-0.01, 0.01),
            'len': 0,
            'rssi': random.randint(-120, -50),
            'snr': random.uniform(-10, 10)
        }
        self.handle_processed_data(test_data)
        self.current_data = test_data  # Zaktualizuj current_data
        self.update_data()  # Wywołaj aktualizację interfejsu

    def closeEvent(self, event):
        """Zamykanie aplikacji"""
        self.serial.stop_reading()
        self.csv_handler.close_file()
        if hasattr(self, 'test_timer') and self.test_timer:
            self.test_timer.stop()
        super().closeEvent(event)