import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from PyQt5.QtGui import QColor, QPen
from datetime import datetime

from pyqtgraph.exporters import ImageExporter, SVGExporter


class LivePlot(QWidget):
	def __init__(self, title="Plot", timespan=30, parent=None, color='#1f77b4'):
		super().__init__(parent)

		self.plot_widget = pg.PlotWidget(title=title)
		self.plot_widget.setBackground(QColor(32, 36, 44))
		self.plot_widget.setLabel('left', 'Value')
		self.plot_widget.setLabel('bottom', 'Time')
		self.plot_widget.setAxisItems({'bottom': pg.DateAxisItem()})
		self.plot_widget.setMouseEnabled(x=True, y=True)
		self.plot_widget.setMenuEnabled(False)
		self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

		self.line_color = color
		self.line_style = 'Solid'
		self.line_width = 2
		self.data_markers_visible = True
		self.grid_visible = True
		self.legend_visible = True
		self.auto_zoom_enabled = True

		self.curve = self.plot_widget.plot(
			pen=self.create_pen(),
			symbol='o' if self.data_markers_visible else None,
			symbolSize=4,
			symbolBrush=self.line_color,
			name='Data Stream',
		)

		if self.legend_visible:
			self.plot_widget.addLegend()

		self.timestamps = np.array([], dtype=np.float64)
		self.values = np.array([], dtype=np.float64)

		self.min_time = None
		self.min_value = float('inf')
		self.max_value = float('-inf')
		self.timespan = timespan

		layout = QVBoxLayout()
		layout.addWidget(self.plot_widget)
		self.setLayout(layout)

		self.crosshair_visible = False
		self.crosshair_v = pg.InfiniteLine(angle=90, movable=False,
										   pen=pg.mkPen('w', width=1))
		self.crosshair_h = pg.InfiniteLine(angle=0, movable=False,
										   pen=pg.mkPen('w', width=1))
		self.coord_label = pg.TextItem(anchor=(0, 1), color='w', fill=pg.mkColor(0, 0, 0, 150))

		self.toggle_crosshair(False)

		self.plot_widget.scene().sigMouseMoved.connect(self.mouse_moved)

	def create_pen(self):
		return pg.mkPen(
			color=self.line_color,
			width=self.line_width,
		)

	def update_pen(self):
		self.curve.setPen(self.create_pen())
		if self.data_markers_visible:
			self.curve.setSymbol('o')
			self.curve.setSymbolSize(4)
			self.curve.setSymbolBrush(self.line_color)
		else:
			self.curve.setSymbol(None)

		self.plot_widget.showGrid(x=self.grid_visible, y=self.grid_visible, alpha=0.3)

		if self.legend_visible:
			self.plot_widget.addLegend()
		else:
			self.plot_widget.plotItem.legend.setParent(None)
			self.plot_widget.plotItem.legend = None

	def update_timespan(self, timespan):
		self.timespan = timespan
		self.zoom_to_data()

	def set_x_label(self, label):
		self.plot_widget.setLabel('bottom', label)

	def set_y_label(self, label):
		self.plot_widget.setLabel('left', label)

	def add_point(self, timestamp, value):
		if isinstance(timestamp, datetime):
			ts = timestamp.timestamp()
		elif isinstance(timestamp, float):
			ts = timestamp
		else:
			ts = timestamp

		self.timestamps = np.append(self.timestamps, ts)
		self.values = np.append(self.values, value)

		if value < self.min_value:
			self.min_value = value
		if value > self.max_value:
			self.max_value = value

		if len(self.timestamps) > 1000:
			self.timestamps = self.timestamps[-1000:]
			self.values = self.values[-1000:]

		self.curve.setData(self.timestamps, self.values)
		if self.auto_zoom_enabled:
			self.zoom_to_data()

	def zoom_to_data(self):
		if len(self.timestamps) == 0:
			return

		current_time = datetime.now().timestamp()
		min_time = current_time - self.timespan
		max_time = current_time

		visible_indices = (self.timestamps >= min_time) & (self.timestamps <= max_time)
		visible_values = self.values[visible_indices]

		if len(visible_values) == 0:
			return

		min_value = np.min(visible_values)
		max_value = np.max(visible_values)
		value_range = max_value - min_value
		padding = value_range * 0.1 if value_range > 0 else 1.0

		self.plot_widget.setXRange(min_time, max_time)
		self.plot_widget.setYRange(min_value - padding, max_value + padding)

	def toggle_auto_zoom(self, enable=None):
		if enable is None:
			self.auto_zoom_enabled = not self.auto_zoom_enabled
		else:
			self.auto_zoom_enabled = enable

	def set_data(self, timestamps, values):
		if isinstance(timestamps[0], datetime):
			self.timestamps = np.array([t.timestamp() for t in timestamps])
		else:
			self.timestamps = np.array(timestamps)

		self.values = np.array(values)

		if len(self.timestamps) > 0:
			self.min_time = np.min(self.timestamps)
			self.max_value = np.max(self.values)
			self.min_value = np.min(self.values)
		else:
			self.min_time = None
			self.min_value = float('inf')
			self.max_value = float('-inf')

		self.curve.setData(self.timestamps, self.values)
		self.zoom_to_data()

	def update_plot(self):
		self.curve.setData(self.timestamps, self.values)
		self.zoom_to_data()

	def reset_view(self):
		if len(self.timestamps) == 0:
			return

		min_time = np.min(self.timestamps)
		max_time = np.max(self.timestamps)
		time_span = max_time - min_time
		padding = time_span * 0.05

		value_span = self.max_value - self.min_value
		value_padding = value_span * 0.1 if value_span > 0 else abs(self.min_value) * 0.1

		self.plot_widget.setXRange(min_time - padding, max_time + padding)
		self.plot_widget.setYRange(self.min_value - value_padding, self.max_value + value_padding)

	def mouse_moved(self, pos):
		if not self.crosshair_visible:
			return

		if self.plot_widget.sceneBoundingRect().contains(pos):
			mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
			x_val = mouse_point.x()
			y_val = mouse_point.y()

			self.crosshair_v.setPos(x_val)
			self.crosshair_h.setPos(y_val)

			if len(self.timestamps) > 0:
				dt = datetime.fromtimestamp(x_val)
				ms = int(dt.microsecond / 1000)
				self.coord_label.setText(
					f"Time: {dt.strftime('%H:%M:%S')}.{ms:03d}\nValue: {y_val:.4f}"
				)
				view_range = self.plot_widget.viewRange()
				x_pos = view_range[0][0] + (view_range[0][1] - view_range[0][0]) * 0.01
				y_pos = view_range[1][0] - (view_range[1][0] - view_range[1][1]) * 0.7
				self.coord_label.setPos(x_pos, y_pos)

	def toggle_crosshair(self, visible=None):
		if visible is None:
			self.crosshair_visible = not self.crosshair_visible
		else:
			self.crosshair_visible = visible

		if self.crosshair_visible:
			self.plot_widget.addItem(self.crosshair_v)
			self.plot_widget.addItem(self.crosshair_h)
			self.plot_widget.addItem(self.coord_label)
		else:
			self.plot_widget.removeItem(self.crosshair_v)
			self.plot_widget.removeItem(self.crosshair_h)
			self.plot_widget.removeItem(self.coord_label)

	def clear_data(self):
		self.timestamps = np.array([], dtype=np.float64)
		self.values = np.array([], dtype=np.float64)
		self.min_value = float('inf')
		self.max_value = float('-inf')
		self.curve.setData([], [])

	def toggle_data_markers(self, visible):
		self.data_markers_visible = visible
		self.update_pen()

	def set_line_color(self, color):
		if isinstance(color, QColor):
			self.line_color = color.name()
		elif isinstance(color, str):
			self.line_color = color
		else:
			self.line_color = '#1f77b4'

		self.update_pen()

	# def set_line_style(self, style):
	# 	self.line_style = style
	# 	self.update_pen()

	def toggle_grid(self, visible):
		self.grid_visible = visible
		self.plot_widget.showGrid(x=visible, y=visible, alpha=0.3)

	def toggle_legend(self, visible):
		self.legend_visible = visible
		if visible:
			self.plot_widget.addLegend()
		else:
			self.plot_widget.plotItem.legend.setParent(None)
			self.plot_widget.plotItem.legend = None

	def export_to_png(self, filename):
		exporter = ImageExporter(self.plot_widget.plotItem)
		exporter.parameters()['width'] = 1920
		exporter.export(filename)

	def export_to_svg(self, filename):
		exporter = SVGExporter(self.plot_widget.plotItem)
		exporter.export(filename)

	def get_data_values(self):
		return self.values.copy()