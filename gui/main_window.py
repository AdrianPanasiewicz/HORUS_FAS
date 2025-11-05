import io
import os
import platform
import subprocess
import logging

import numpy as np
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (QMainWindow,
                             QWidget, QSizePolicy,
                             QHBoxLayout, QLabel,
                             QGridLayout, QVBoxLayout, QMessageBox, QInputDialog, QColorDialog, QDialog, QTextBrowser,
                             QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QColor
from gpiozero.pins.mock import MockFactory
from PyQt5 import QtCore
from serial.tools import list_ports
import folium
from core.serial_reader import SerialReader
from gui.live_plot import LivePlot
from datetime import datetime
from core.process_data import ProcessData
from core.csv_handler import CsvHandler
import random


class MainWindow(QMainWindow):
    def __init__(self, config, transmitter, gpio_reader, csv_handler):
        super().__init__()
        self.transmitter = transmitter
        self.is_partner_connected = False

        self.logger = logging.getLogger('HORUS_FAS.main_window')
        self.logger.info("Inicjalizacja głównego okna")

        self.now_str = ""

        self.current_data = {
            'ver_velocity': 0.0,
            # 'ver_accel': 0.0,
            'altitude': 0.0,
            'pitch': 0.0,
            'roll': 0.0,
            'yaw': 0.0,
            'status': 0,
            'latitude': 52.2549,
            'longitude': 20.9004,
            'rbs': 0,
            # 'snr': 0
        }

        self.default_lat = 52.2549
        self.default_lng = 20.9004
        self.current_lat = self.current_data['latitude']
        self.current_lng = self.current_data['longitude']
        self.map = None
        self.map_view = None
        self.mission_aborted = False

        self.csv_handler = csv_handler
        self.logger.info(
            f"CSV handler zainicjalizowany w sesji: {self.csv_handler.session_dir}")

        self.setWindowTitle("HORUS_FAS")
        self.setWindowIcon(QIcon(r'gui/white_icon.png'))
        self.setStyleSheet(
            open(r'gui/resources/themes/dark_blue.qss').read())
        self.showMaximized()

        self.serial = SerialReader(config['port'], config['baudrate'])
        self.logger.info(f"SerialReader zainicjalizowany na porcie {config['port']} z baudrate {config['baudrate']}")
        self.processor = ProcessData(csv_handler)
        self.logger.info(
            f"Singleton ProcessData zainicjalizowany")

        if config['lora_config']:
            self.serial.LoraSet(config['lora_config'], config['is_config_selected'])
            self.logger.info(f"Konfiguracja LoRa ustawiona: {config['lora_config']}")

        self.serial.telemetry_received.connect(self.processor.handle_telemetry)
        self.serial.auxiliary_received.connect(self.processor.handle_telemetry)
        self.serial.transmission_info_received.connect(self.processor.handle_transmission_info)
        self.processor.processed_data_ready.connect(self.handle_processed_data)

        self.transmitter.data_received_signal.connect(self.abort_mission_pressed)

        self.gpio_reader = gpio_reader
        self.gpio_reader.held.connect(self.abort_mission_pressed)

        # Wykresy
        self.alt_plot = LivePlot(title="Altitude", color='b', timespan=30)
        self.ver_velocity_plot = LivePlot(title="Vertical Velocity", color='r', timespan=30)
        self.ver_accel_plot = LivePlot(title="Vertical Acceleration", color='c', timespan=30)
        self.pitch_plot = LivePlot(title="Pitch", color='y', timespan=30)
        self.roll_plot = LivePlot(title="Roll", color='g', timespan=30)
        self.yaw_plot = LivePlot(title="Yaw", color='w', timespan=30)

        self.alt_plot.set_x_label("Time [s]")
        self.alt_plot.set_y_label("Height [m]")

        self.ver_velocity_plot.set_x_label("Time [s]")
        self.ver_velocity_plot.set_y_label("Vertical Velocity [m/s]")

        self.ver_accel_plot.set_x_label("Time [s]")
        self.ver_accel_plot.set_y_label("Vertical Acceleration [m/s²]")

        self.pitch_plot.set_x_label("Time [s]")
        self.pitch_plot.set_y_label("Pitch [°]")

        self.roll_plot.set_x_label("Time [s]")
        self.roll_plot.set_y_label("Roll [°]")

        self.yaw_plot.set_x_label("Time [s]")
        self.yaw_plot.set_y_label("Yaw [°]")

        # Mapa
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.set_map(lat=self.default_lat, lng=self.default_lng)
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

        right_panel = self.create_right_panel()

        main_layout.addLayout(left_plots_column, 0, 0, 1, 40)
        main_layout.addLayout(middle_plots_column, 0, 41, 1, 40)
        main_layout.addWidget(right_panel, 0, 81, 1, 20)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.serial.start_reading()

        self.setup_status_bar()
        self.declare_menus()

    def create_right_panel(self):
        """Tworzy dolny panel z danymi i mapą"""
        panel = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(5)

        data_labels = QWidget()
        data_layout = QVBoxLayout()
        data_layout.setContentsMargins(5, 5, 5, 5)
        data_layout.setSpacing(10)

        # Prawa kolumna - mapa
        map_widget = QWidget()
        map_layout = QVBoxLayout()
        map_layout.setContentsMargins(0, 0, 0, 0)

        map_layout.addWidget(self.map_view)
        map_widget.setLayout(map_layout)

        self.table = QTableWidget()
        self.table.setRowCount(7)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Parameter", "Value"])

        parameters = ["Altitude", "Velocity", "Acceleration", "Pitch", "Roll", "Yaw", "Latitude", "Longitude"]
        values = [
            f"{self.current_data['altitude']:.2f} m",
            f"{self.current_data['ver_velocity']:.2f} m/s",
            #f"{self.current_data['ver_accel']:.2f} m/s²",
            f"{self.current_data['pitch']:.2f}°",
            f"{self.current_data['roll']:.2f}°",
            f"{self.current_data['yaw']:.2f}°",
            f"{self.current_data['latitude']:.6f}° N",
            f"{self.current_data['longitude']:.6f}° E"
        ]

        for i, (param, value) in enumerate(zip(parameters, values)):
            self.table.setItem(i, 0, QTableWidgetItem(param))
            self.table.setItem(i, 1, QTableWidgetItem(value))

        self.table.setStyleSheet("font-size: 20px;")
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        row = QVBoxLayout()
        row.addWidget(self.table)

        # Dodanie wierszy do kolumny danych
        data_layout.addLayout(row)
        data_labels.setLayout(data_layout)

        main_layout.addWidget(map_widget, 50)
        main_layout.addWidget(data_labels, 50)
        panel.setLayout(main_layout)
        return panel

    def setup_status_bar(self):
        self.status_bar_visible = True

        status_container = QWidget()
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(20)
        status_container.setLayout(status_layout)
        status_container.setStyleSheet("background: transparent")

        left_container = QWidget()
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_container.setLayout(left_layout)

        self.status_logo = QLabel()
        self.status_logo.setFixedSize(24, 24)
        self.status_logo.setScaledContents(True)
        logo_pixmap = QPixmap(r"gui/resources/black_icon_without_background.png").scaled(30, 30)
        self.status_logo.setPixmap(logo_pixmap)
        left_layout.addWidget(self.status_logo)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.status_packet_label = QLabel(f"Last received packet: {current_time} s")
        self.status_packet_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        left_layout.addWidget(self.status_packet_label)

        status_layout.addWidget(left_container, 0, alignment=Qt.AlignLeft)

        self.status_title_label = QLabel("HORUS Flight Analysis Station")
        self.status_title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self.status_title_label, 1, alignment=Qt.AlignHCenter)

        right_container = QWidget()
        right_layout = QHBoxLayout()
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(10)
        right_container.setLayout(right_layout)

        self.connection_label = QLabel("HORUS CSS disconnected")
        self.connection_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        right_layout.addWidget(self.connection_label)

        self.heartbeat_placeholder = QLabel("●")
        self.heartbeat_placeholder.setStyleSheet("background: transparent; color: transparent; font-size: 14px;")
        right_layout.addWidget(self.heartbeat_placeholder)

        status_layout.addWidget(right_container, 0, alignment=Qt.AlignRight)

        self.statusBar().addWidget(status_container, 1)

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


    def set_map(self, lat, lng):
        figure = folium.Figure(width="100%", height="100%")

        self.map = folium.Map(
            location=[lat, lng],
            zoom_start=15,
            control_scale=True,
            tiles='OpenStreetMap'
        )

        figure.add_child(self.map)

        folium.Marker(
            [lat, lng],
            popup=f"LOTUS: {lat:.6f}, {lng:.6f}",
            icon=folium.Icon(color="green", icon="flag", prefix='fa')
        ).add_to(self.map)

        data = io.BytesIO()
        self.map.save(data, close_file=False)
        html = data.getvalue().decode()

        responsive_meta = '''
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                html, body {
                    width: 100%;
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }
                #map {
                    width: 100%;
                    height: 100%;
                }
                .folium-map {
                    width: 100% !important;
                    height: 100% !important;
                }
            </style>
            '''

        html = html.replace('</head>', responsive_meta + '</head>')
        self.map_view.setHtml(html, QUrl(''))

    def resizeEvent(self, event):
        """Obsługa zmiany rozmiaru okna"""
        super().resizeEvent(event)
        QTimer.singleShot(100, self.update_map_view)

    def update_map_view(self):
        """Update the map view with current HTML"""
        if hasattr(self, 'map') and self.map:
            # Regenerate the HTML with current dimensions
            data = io.BytesIO()
            self.map.save(data, close_file=False)
            html = data.getvalue().decode()

            # Add responsive styling
            responsive_meta = '''
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                html, body {
                    width: 100%;
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }
                #map {
                    width: 100%;
                    height: 100%;
                }
                .folium-map {
                    width: 100% !important;
                    height: 100% !important;
                }
            </style>
            '''

            html = html.replace('</head>', responsive_meta + '</head>')
            self.map_view.setHtml(html, QUrl(''))

    def declare_menus(self):
        self.menu = self.menuBar()
        self.menu.setStyleSheet("""
        QMenu {
            background-color: #1e1e1e;
            color: white;
            border: 1px solid #444;
        }

        QMenu::item {
            padding: 5px 25px 5px 25px;
        }

        QMenu::item:selected {
            background-color: #555;
        }

        QMenu::indicator {
            width: 14px;
            height: 14px;
            border-radius: 7px;  /* makes it circular */
            border: 1px solid #888;
            background-color: #2e2e2e;
        }

        QMenu::indicator:checked {
            background-color: #4caf50;  /* nicer green */
            border: 1px solid #4caf50;
            box-shadow: 0px 0px 2px black; /* subtle shadow */
        }
        """)
        self.file_menu = self.menu.addMenu("File")
        self.view_menu = self.menu.addMenu("View")
        self.theme_menu = self.view_menu.addMenu("Themes")
        self.timespan_menu = self.view_menu.addMenu("Timespan")
        self.tools_menu = self.menu.addMenu("Tools")
        self.test_menu = self.menu.addMenu("Test")
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

        self.crosshair_action = self.view_menu.addAction("Crosshair")
        self.crosshair_action.setCheckable(True)
        self.crosshair_action.setChecked(False)
        self.crosshair_action.triggered.connect(self.toggle_crosshairs)

        self.auto_zoom_action = self.view_menu.addAction("Auto-Zoom")
        self.auto_zoom_action.setCheckable(True)
        self.auto_zoom_action.setChecked(True)
        self.auto_zoom_action.triggered.connect(self.toggle_auto_zoom)

        self.data_markers_action = self.view_menu.addAction("Data Markers")
        self.data_markers_action.setCheckable(True)
        self.data_markers_action.setChecked(True)
        self.data_markers_action.triggered.connect(self.toggle_data_markers)

        self.grid_action = self.view_menu.addAction("Grid")
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)
        self.grid_action.triggered.connect(self.toggle_plot_grid)

        self.color_action = self.view_menu.addAction("Plot color")
        self.color_action.triggered.connect(self.change_line_colors)


        self.view_menu.addSeparator()
        self.view_menu.addAction("Clear Plots", self.clear_plots)
        self.view_menu.addAction("Clear All", self.clear_all)

        self.help_menu.addAction("About application", self.show_about_app_dialog)
        self.help_menu.addAction("About KNS LiK", self.show_about_kns_dialog)

        self.test_menu.addAction("Start Plot Simulation", self.start_random_test)
        self.test_menu.addAction("Stop Plot Simulation", self.stop_random_test)
        self.test_menu.addSeparator()
        self.test_menu.addAction("Start Map Simulation", self.start_map_simulation)
        self.test_menu.addAction("Stop Map Simulation", self.stop_map_simulation)

        self.test_menu.addSeparator()

        self.abort_button_sim = self.test_menu.addAction("Simulate Abort Switch Toggle")
        self.abort_button_sim.setCheckable(True)
        self.abort_button_sim.setChecked(False)
        self.abort_button_sim.triggered.connect(self.simulate_button_held)

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

        self.timespan_menu.addAction("30 seconds", lambda: self.change_plot_timespans(30))
        self.timespan_menu.addAction("60 seconds", lambda: self.change_plot_timespans(60))
        self.timespan_menu.addAction("90 seconds", lambda: self.change_plot_timespans(90))
        self.timespan_menu.addAction("120 seconds", lambda: self.change_plot_timespans(120))

        serial_menu = self.tools_menu.addMenu("Serial Configuration")
        serial_menu.addAction("Scan Ports", self.scan_serial_ports)
        serial_menu.addAction("Change Baud Rate", self.change_baud_rate)
        serial_menu.addAction("Reconnect Serial", self.reconnect_serial)
        self.tools_menu.addAction("Configure Filters", self.configure_filters)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction("Calculate Statistics", self.calculate_statistics)


    def toggle_crosshairs(self):
        state = self.crosshair_action.isChecked()
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]

        for plot in plots:
            plot.toggle_crosshair(state)

        status = "ON" if state else "OFF"
        self.logger.info(f"Crosshair toggled to {status}")

    def toggle_auto_zoom(self):
        state = self.auto_zoom_action.isChecked()
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]

        for plot in plots:
            plot.toggle_auto_zoom(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.logger.info(f"Auto-zoom toggled to {status}")

    def change_plot_timespans(self, timespan):
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]
        for plot in plots:
            plot.update_timespan(timespan)


    def toggle_data_markers(self):
        state = self.data_markers_action.isChecked()
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]

        for plot in plots:
            plot.toggle_data_markers(state)

        current_time = datetime.now().strftime("%H:%M:%S")
        status = "ON" if state else "OFF"
        self.logger.info(f"Data markers toggled to {status}")

    def toggle_plot_grid(self):
        state = self.grid_action.isChecked()
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]

        for plot in plots:
            plot.toggle_grid(state)

    def change_line_colors(self):
        plots = {
            "Altitude": self.alt_plot,
            "Vertical velocity": self.ver_velocity_plot,
            "Vertical acceleration": self.ver_accel_plot,
            "Pitch plot": self.pitch_plot,
            "Roll plot": self.roll_plot,
            "Yaw plot": self.yaw_plot
        }

        plot_name, ok = QInputDialog.getItem(
            self, "Select Plot", "Choose plot to change color:", list(plots.keys()), 0, False
        )

        if not ok:
            return

        current_color = plots[plot_name].line_color
        current_qcolor = QColor(current_color)

        color = QColorDialog.getColor(current_qcolor, self, "Select Line Color")

        if color.isValid():
            plots[plot_name].set_line_color(color)

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: {color.name()};'>Plot '{plot_name}' line color changed</span>"
            )
            self.logger.info(f"Plot '{plot_name}' line color changed to {color.name()}")

    def clear_plots(self):
        plots = [
            self.alt_plot,
            self.ver_velocity_plot,
            self.ver_accel_plot,
            self.pitch_plot,
            self.roll_plot,
            self.yaw_plot
        ]

        for plot in plots:
            plot.clear_data()

        self.altitude_label.setText("Altitude: 0.00 m")
        self.velocity_label.setText("Velocity: 0.00 m/s")
        self.accel_label.setText("Acceleration: 0.00 m/s²")
        self.pitch_label.setText("Pitch: 0.00°")
        self.roll_label.setText("Roll: 0.00°")
        self.yaw_label.setText("Yaw: 0.00°")
        self.position_label.setText("Pos: 0.000000° N, 0.000000° E")

        self.logger.info("Plots cleared")

    def clear_all(self):
        self.clear_plots()
        self.set_map(self.default_lat, self.default_lng)
        self.logger.debug(f"Cleared all")

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

    def abort_mission_pressed(self):
        current_time = datetime.now().strftime("%H:%M:%S")

        self.connection_label.setText("               Mission aborted")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")

        self.logger.info(f"Abort mission button pressed.")
        self.mission_aborted = True

    def simulate_button_held(self):
        try:
            pin_factory = type(self.gpio_reader.button.pin.factory)
            if pin_factory is not MockFactory:
                self.logger.warning("Cannot simulate button press: real GPIO backend in use.")
                return

            pin = self.gpio_reader.button.pin

            if pin.state:
                pin.drive_low()  # press
                self.logger.info("Simulated button press (drive_low).")
            else:
                pin.drive_high()
                self.logger.info("Simulated button release (drive_high).")

        except Exception as e:
            self.logger.error(f"Failed to simulate button press: {e}")

    def update_map_view(self):
        pass
        """Aktualizuje widok mapy z uwzględnieniem skalowania"""
        with open('map.html', 'r') as f:
            html = f.read()
            html = html.replace('<head>',
                                '<head><meta name="viewport" content="width=device-width, initial-scale=1.0">')
            self.map_view.setHtml(html,)

    def scan_serial_ports(self):
        try:
            ports = [port.device for port in list_ports.comports()]

            if not ports:
                QMessageBox.warning(self, "Serial Ports", "No serial ports found")
                return

            message = "Available ports:\n" + "\n".join([f"• {port}" for port in ports])
            QMessageBox.information(self, "Serial Ports", message)

            self.logger.info(f"Scanned serial ports: {ports}")

        except Exception as e:
            self.logger.error(f"Error scanning serial ports: {str(e)}")
            QMessageBox.critical(self, "Serial Ports Error", f"Error scanning ports: {str(e)}")

    def change_baud_rate(self):
        current_baud = self.serial.baudrate
        baud_rates = ["9600", "19200", "38400", "57600", "115200"]

        choice, ok = QInputDialog.getItem(
            self, "Select Baud Rate", "Choose a baud rate:",
            baud_rates, baud_rates.index(str(current_baud)), False
        )

        if ok and choice:
            try:
                new_baud = int(choice)
                self.serial.set_baudrate(new_baud)

                QMessageBox.information(
                    self, "Baud Rate Changed", f"Baud rate successfully changed to {new_baud}"
                )
                self.logger.info(f"Baud rate changed to {new_baud}")

            except Exception as e:
                self.logger.error(f"Error changing baud rate: {str(e)}")
                QMessageBox.critical(
                    self, "Error", f"Error changing baud rate: {str(e)}"
                )

    def reconnect_serial(self):
        try:
            self.serial.reconnect()

            if self.serial.is_connected():
                QMessageBox.information(
                    self, "Serial Connection", "Serial reconnected successfully"
                )
                self.logger.info("Serial reconnected successfully")
            else:
                QMessageBox.warning(
                    self, "Serial Connection", "Serial reconnection failed"
                )
                self.logger.warning("Serial reconnection failed")

        except Exception as e:
            self.logger.error(f"Error reconnecting serial: {str(e)}")
            QMessageBox.critical(
                self, "Serial Connection Error", f"Error reconnecting serial: {str(e)}"
            )

    def configure_filters(self):
        QMessageBox.information(
            self,
            "Configure Filters",
            "This feature is under development. It will allow you to configure "
            "data filtering algorithms for noise reduction."
        )

    def calculate_statistics(self):
        """Calculate and display statistics for plot data"""
        try:
            stats = []

            plots = {
                "Altitude": self.alt_plot,
                "Vertical velocity": self.ver_velocity_plot,
                "Vertical acceleration": self.ver_accel_plot,
                "Pitch plot": self.pitch_plot,
                "Roll plot": self.roll_plot,
                "Yaw plot": self.yaw_plot
            }

            for name, plot in plots.items():
                if plot.values.any():
                    values = np.array(plot.values)
                    stats.append(f"<b>{name}:</b>")
                    stats.append(f"  Min: {np.min(values):.2f}")
                    stats.append(f"  Max: {np.max(values):.2f}")
                    stats.append(f"  Mean: {np.mean(values):.2f}")
                    stats.append(f"  Std Dev: {np.std(values):.2f}")
                    stats.append("")

            if not stats:
                raise ValueError("No data available for statistics")

            stats_html = "<br>".join(stats)

            # Show in dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Data Statistics")
            dialog.resize(200, 400)
            layout = QVBoxLayout()

            text_browser = QTextBrowser()
            text_browser.setHtml(stats_html)
            layout.addWidget(text_browser)

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)

            dialog.setLayout(layout)
            dialog.exec()

            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: lightgreen;'>Calculated data statistics</span>")
            self.logger.info("Calculated data statistics")

        except Exception as e:
            self.logger.error(f"Error calculating statistics: {str(e)}")
            current_time = datetime.now().strftime("%H:%M:%S")
            self.terminal_output.append(
                f">{current_time}: <span style='color: red;'>Error calculating statistics: {str(e)}</span>")


    def handle_processed_data(self, data):
        try:
            if 'latitude' not in data or 'longitude' not in data:
                self.logger.warning("Brak danych GPS w pakiecie – pomijam aktualizację mapy.")
                data.setdefault('latitude', self.current_data.get('latitude', 52.2549))
                data.setdefault('longitude', self.current_data.get('longitude', 20.9004))

            if 'status' not in data:
                self.logger.warning("Brak pola 'status' w pakiecie – ustawiam domyślny.")
                data['status'] = self.current_data.get('status', 'OK')

            self.current_data = data
            self.update_data()
            self.csv_handler.write_row(data)
            self.logger.debug(f"Przetworzono dane do wysłania: {data}")

            transmit_data = {
                'timestamp': datetime.now().isoformat(),
                'telemetry': {
                    'velocity': data.get('ver_velocity', 0),
                    'altitude': data.get('altitude', 0),
                    'latitude': data.get('latitude', 0),
                    'longitude': data.get('longitude', 0),
                    'pitch': data.get('pitch', 0),
                    'roll': data.get('roll', 0),
                    'yaw': data.get('yaw', 0),
                    'status': data.get('status', 0),
                    'rbs': data.get('bcs', 0)
                    # 'bay_pressure': data.get('bay_pressure',0.0),
                    # 'bay_temperature': data.get('bay_temperature',0.0)
                },
                'transmission': {
                    'rssi': data.get('rssi', 0),
                    'snr': data.get('snr', 0)
                }
            }

            if self.is_partner_connected:
                self.transmitter.send_data(transmit_data) # To powinno być w process_data
                self.logger.debug(f"The following data has been send to partner: {transmit_data}")
            else:
                self.logger.error("No partner connected")

        except Exception as e:
            self.logger.error(f"Błąd w handle_processed_data: {e}")

    def show_about_app_dialog(self):
        about_text = """
        <div style="text-align: justify;">
            <h2>HORUS Flight Analysis Station</h2>
            <p><b>Version:</b> 0.1.0</p>
            <p><b>Description:</b> The ground station is responsible for processing and displaying data regarding 
            the flight of a sounding rocket. It is a subcomponent of a HORUS project, which is also as a part of a 
            larger LOTUS ONE project Scientific Association of Aviation and Astronautics Students of MUT.</p>
            <p><b>Authors:</b> Adrian Panasiewicz, Filip Sudak</p>
            <p><b>Copyright:</b> © 2025 KNS LiK </p>
        </div>
        """

        QMessageBox.about(self, "About HORUS-FAS", about_text)

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
        timestamp = datetime.now()

        if not hasattr(self, 'previous_data'):
            self.previous_data = {}

        if self.current_data['altitude'] != self.previous_data.get('altitude'):
            self.alt_plot.add_point(timestamp, self.current_data['altitude'])

        if self.current_data['ver_velocity'] != self.previous_data.get('ver_velocity'):
            self.ver_velocity_plot.add_point(timestamp, self.current_data['ver_velocity'])
            ts, vel = self.ver_velocity_plot.get_data_points()
            if len(ts) < 2:
                acc = 0.0
            else:
                dt = ts[-1] - ts[-2]
                if dt == 0:
                    acc = 0.0
                else:
                    acc = (vel[-1] - vel[-2]) / dt
                self.ver_accel_plot.add_point(timestamp,acc)

        if self.current_data['pitch'] != self.previous_data.get('pitch'):
            self.pitch_plot.add_point(timestamp, self.current_data['pitch'])

        if self.current_data['roll'] != self.previous_data.get('roll'):
            self.roll_plot.add_point(timestamp, self.current_data['roll'])

        if self.current_data['yaw'] != self.previous_data.get('yaw'):
            self.yaw_plot.add_point(timestamp, self.current_data['yaw'])

        values = [
            f"{self.current_data['altitude']:.2f} m",
            f"{self.current_data['ver_velocity']:.2f} m/s",
            f"{self.current_data['pitch']:.2f}°",
            f"{self.current_data['roll']:.2f}°",
            f"{self.current_data['yaw']:.2f}°",
            f"{self.current_data['latitude']:.6f}° N",
            f"{self.current_data['longitude']:.6f}° E"
        ]

        parameters = ["Altitude", "Velocity", "Pitch", "Roll", "Yaw", "Latitude", "Longitude"]

        for i, (param, value) in enumerate(zip(parameters, values)):
            current_value_item = self.table.item(i, 1)

            if current_value_item is None or current_value_item.text() != value:
                self.table.setItem(i, 0, QTableWidgetItem(param))
                self.table.setItem(i, 1, QTableWidgetItem(value))



        self.now_str = datetime.now().strftime("%H:%M:%S")
        msg = (
            f"{self.current_data['ver_velocity']};{self.current_data['altitude']};"
            f"{self.current_data['pitch']};{self.current_data['roll']};"
            f"{self.current_data['status']};{self.current_data['latitude']};"
            f"{self.current_data['longitude']}"
        )

        self.previous_data = self.current_data.copy()

    def start_random_test(self, duration=120):
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

        # 2. Inicjalizacja timera
        if hasattr(self, 'test_timer') and self.test_timer:
            self.test_timer.stop()  # Bezpieczne zatrzymanie istniejącego timera

        self.test_timer = QtCore.QTimer()
        self.test_timer.setTimerType(QtCore.Qt.PreciseTimer)  # Dokładniejszy timer
        self.test_timer.timeout.connect(self._generate_test_data)
        #self.transmitter.send_data(self._generate_test_data)  # Dodałem do testów

        self.test_timer.start(10)

        QtCore.QTimer.singleShot(
            duration * 1000,
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
            'altitude': random.uniform(0, 1000),
            'pitch': random.uniform(-90, 90),
            'roll': random.uniform(-90, 90),
            'yaw': random.uniform(0, 360),
            'status': random.randint(0, 5),
            'latitude': 52.2549 + random.uniform(-0.01, 0.01),
            'longitude': 20.9004 + random.uniform(-0.01, 0.01),
            'rbs': random.randint(0, 1)
        }
        self.handle_processed_data(test_data)
        self.current_data = test_data
        self.update_data()

    def start_map_simulation(self, duration=120):
        if hasattr(self, 'test_map_timer') and self.test_map_timer:
            self.test_map_timer.stop()

        self.test_lat = 52.2549
        self.test_lng = 20.9004

        self.test_map_timer = QtCore.QTimer()
        self.test_map_timer.setTimerType(QtCore.Qt.PreciseTimer)  # Dokładniejszy timer
        self.test_map_timer.timeout.connect(self._generate_test_map_data)

        self.test_map_timer.start(1000)

        QtCore.QTimer.singleShot(
            duration * 1000,
            lambda: self.stop_map_simulation() or self.logger.info("Test zakończony")
        )

        self.logger.info(f"Rozpoczęto test mapy na {duration} sekund")

    def stop_map_simulation(self):
        if hasattr(self, 'test_map_timer') and self.test_map_timer:
            self.test_map_timer.stop()

    def _generate_test_map_data(self):
        """Generuje losowe dane testowe"""
        self.test_lat += random.uniform(0, 0.001)
        self.test_lng += random.uniform(0, 0.001)
        self.set_map(self.test_lat,self.test_lng)

    def on_partner_connected(self):
        if hasattr(self, "connection_label") and self.connection_label is not None:
            self.logger.info("HORUS CSS connected to HORUS FAS")
            self.connection_label.setText("   HORUS CSS connected")
            self.connection_label.setStyleSheet("color: #66FF00; font-weight: bold;")
            self.is_partner_connected = True

    def on_partner_disconnected(self):
        if hasattr(self, "connection_label") and self.connection_label is not None:
            self.logger.info("HORUS CSS disconnected from HORUS FAS")
            self.connection_label.setText("HORUS CSS disconnected")
            self.connection_label.setStyleSheet("color: red; font-weight: bold;")
            self.is_partner_connected = False

    def closeEvent(self, event):
        """Zamykanie aplikacji"""
        self.serial.stop_reading()
        self.csv_handler.close_file()
        if hasattr(self, 'test_timer') and self.test_timer:
            self.test_timer.stop()
        if hasattr(self, 'transmitter'):
            self.transmitter.unsubscribe_on_partner_connected(self.on_partner_connected)
            self.transmitter.unsubscribe_on_partner_disconnected(self.on_partner_disconnected)
        super().closeEvent(event)