import logging
import pyqtgraph as pg
pg.setConfigOptions(useOpenGL=True)
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QColor

class LivePlot(QWidget):
    def __init__(self, title="Wykres", max_points=100, color='y'):
        super().__init__()
        self.logger = logging.getLogger('HORUS_FAS.live_plot')
        self.max_points = max_points
        self.data = []

        self.logger.info(f"Tworzenie wykresu: tytuł='{title}', max_points={max_points}, kolor='{color}'")
        self.setStyleSheet(
            open(r'gui/darkstyle.qss').read())

        self.plot_widget = pg.PlotWidget(title=title)
        self.plot_widget.showGrid(x=True, y=True)
        bg_color = QColor(32,36,44)
        self.plot_widget.setBackground(bg_color)
        pen = pg.mkPen(color=color, width=2)
        self.curve = self.plot_widget.plot(pen=pen)

        layout = QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

    def update_plot(self, new_value: float):
        self.logger.debug(f"Nowa wartość dodana do wykresu: {new_value}")
        self.data.append(new_value)
        if len(self.data) > self.max_points:
            removed = self.data.pop(0)
            self.logger.debug(f"Usunięto najstarszy punkt: {removed}")
        self.curve.setData(self.data)
