import logging
import time
import pyqtgraph as pg
from collections import deque
from pyqtgraph.exporters import ImageExporter, SVGExporter
pg.setConfigOptions(useOpenGL=True)
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QColor


class LivePlot(QWidget):
    def __init__(self, title="Wykres", max_points=300, color='y', time_window=30):
        super().__init__()
        self.logger = logging.getLogger('HORUS_FAS.live_plot')
        self.max_points = max_points
        self.time_window = time_window
        self.data = deque(maxlen=max_points)
        self.timestamps = deque(maxlen=max_points)
        self.plot_start_time = None  # Będzie ustawione przy pierwszym pomiarze

        self.plot_widget = pg.PlotWidget(title=title)
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setBackground(QColor(32, 36, 44))
        self.plot_widget.setLabel('left', 'Wartość')
        self.plot_widget.setLabel('bottom', 'Czas', units='s')
        self.plot_widget.setXRange(0, time_window)  # Wymuszamy start od zera

        pen = pg.mkPen(color=color, width=2)
        self.curve = self.plot_widget.plot(pen=pen)

        layout = QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

    def reset_time(self):
        """Resetuje timer przy rozpoczęciu nowego pomiaru"""
        self.plot_start_time = time.time()
        self.data.clear()
        self.timestamps.clear()
        self.plot_widget.setXRange(0, self.time_window)

    def update_plot(self, new_value: float):
        if self.plot_start_time is None:
            self.reset_time()  # Inicjalizacja przy pierwszym pomiarze

        current_time = time.time() - self.plot_start_time
        self.data.append(new_value)
        self.timestamps.append(current_time)

        # Przewijanie wykresu po przekroczeniu okna czasowego
        if current_time > self.time_window:
            self.plot_widget.setXRange(current_time - self.time_window, current_time)

        self.curve.setData(list(self.timestamps), list(self.data))

    def export_to_png(self, filename):
        exporter = ImageExporter(self.plot_widget.plotItem)
        exporter.parameters()['width'] = 1920
        exporter.export(filename)

    def export_to_svg(self, filename):
        exporter = SVGExporter(self.plot_widget.plotItem)
        exporter.export(filename)

