import sys
import os
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QFileDialog, QComboBox, QLabel, QSlider, QDateTimeEdit, QDialog
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, Qt, QDateTime
import folium
from matplotlib import colors, pyplot as plt
from matplotlib import colormaps
from branca.colormap import LinearColormap
import plotly.express as px


class TimePlotWindow(QDialog):
    def __init__(self, data, metric):
        super().__init__()
        self.setWindowTitle(f"{metric} vs Time")
        self.setGeometry(200, 200, 800, 600)

        # Set up the layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create a QWebEngineView widget
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Generate and display the Plotly plot
        self.plot_data(data, metric)

    def plot_data(self, data, metric):
        # Create a Plotly time-series plot
        fig = px.line(data, x="Time", y=metric, title=f"{metric} vs Time", labels={"Time": "Time", metric: metric})
        fig.update_layout(xaxis_title="Time", yaxis_title=metric)

        # Save the plot as an HTML file
        plot_file = os.path.join(os.getcwd(), "time_plot.html")
        fig.write_html(plot_file)

        # Load the HTML file into the QWebEngineView
        self.web_view.setUrl(QUrl.fromLocalFile(plot_file))


class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RadiaCode Track Viewer")
        self.setGeometry(100, 100, 1200, 800)

        # Default settings
        self.current_colormap_name = "viridis"
        self.loaded_data = None  # To store currently loaded data
        self.filtered_data = None  # To store currently shown data
        self.map_file = None
        self.start_time = None
        self.stop_time  = None
        self.min_time = None
        self.max_time = None
        self.min_doseRate = None
        self.max_doseRate = None
        self.min_countRate = None
        self.max_countRate = None
        self.range_doseRate = None
        self.range_countRate = None
        self.metricUnits = {"DoseRate":"µSv/h", "CountRate":"cps"}
        self.metricSelected = "DoseRate"
        
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Set up main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Create a QWebEngineView for map display
        self.map_view = QWebEngineView()
        main_layout.addWidget(self.map_view)

        # Add control layout 
        control_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)

        # Dropdown for field and colormap
        self.display_field_dropdown = QComboBox()
        self.display_field_dropdown.addItems(["DoseRate", "CountRate"])
        control_layout.addWidget(QLabel("Select Metric:"))
        control_layout.addWidget(self.display_field_dropdown)
        
        self.display_field_dropdown.currentTextChanged.connect(self.update_display)

        # Dropdown for colormap selection
        self.colormap_dropdown = QComboBox()
        self.colormap_dropdown.addItems(sorted(colormaps.keys()))
        self.colormap_dropdown.setCurrentText(self.current_colormap_name)
        control_layout.addWidget(QLabel("Select Colormap:"))
        control_layout.addWidget(self.colormap_dropdown)
        
        self.colormap_dropdown.currentTextChanged.connect(self.update_display)

        # Add a button for file selection
        self.select_file_button = QPushButton("Select .rctrk File")
        control_layout.addWidget(self.select_file_button)
        
        self.select_file_button.clicked.connect(self.select_file)
        
        # Add a clear button
        self.clear_button = QPushButton("Clear data")
        control_layout.addWidget(self.clear_button)
        
        self.clear_button.clicked.connect(self.clear_data)

        # Add an Export button
        self.export_button = QPushButton("Export HTML File")
        control_layout.addWidget(self.export_button)
        self.export_button.setEnabled(False)
        
        self.export_button.clicked.connect(self.export_html)

        # Add a Time Plot button
        self.time_plot_button = QPushButton("Time Plot")
        control_layout.addWidget(self.time_plot_button)
        self.time_plot_button.setEnabled(False)

        self.time_plot_button.clicked.connect(self.show_time_plot)

        # Add time range controls
        time_layout = QHBoxLayout()
        main_layout.addLayout(time_layout)

        time_layout.addWidget(QLabel("Start Time:"))
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setCalendarPopup(True)
        time_layout.addWidget(self.start_time_edit)

        time_layout.addWidget(QLabel("Stop Time:"))
        self.stop_time_edit = QDateTimeEdit()
        self.stop_time_edit.setCalendarPopup(True)
        time_layout.addWidget(self.stop_time_edit)

        self.start_time_edit.dateTimeChanged.connect(self.update_display)
        self.stop_time_edit.dateTimeChanged.connect(self.update_display)        
        
        # Create a second row of controls for min/max sliders
        slider_layout = QHBoxLayout()
        main_layout.addLayout(slider_layout)

        # Minimum value slider
        self.color_min_slider = QSlider(Qt.Horizontal)
        self.color_min_slider.setRange(0, 100)  
        self.color_min_slider.setValue(0)  
        self.color_min_slider_label = QLabel(f"Min: 0 {self.metricUnits[self.metricSelected]}")
        slider_layout.addWidget(self.color_min_slider_label)
        slider_layout.addWidget(self.color_min_slider)

        # Maximum value slider
        self.color_max_slider = QSlider(Qt.Horizontal)
        self.color_max_slider.setRange(0, 100)  
        self.color_max_slider.setValue(100)  
        self.color_max_slider_label = QLabel(f"Max: 100 {self.metricUnits[self.metricSelected]}")
        slider_layout.addWidget(self.color_max_slider_label)
        slider_layout.addWidget(self.color_max_slider)
        
        self.color_min_slider.valueChanged.connect(self.update_display)
        self.color_max_slider.valueChanged.connect(self.update_display)

        # Load the initial basemap
        self.load_map()

    def load_map(self, lat=0, lon=0, zoom=2, data=None, metric="DoseRate", color_range=None, color_map=None):
        """
        Generate and display the map with optional data plotted.
        Parameters:
        - lat: Latitude for map center.
        - lon: Longitude for map center.
        - zoom: Zoom level for the map.
        - data: DataFrame containing data to plot.
        - metric: The selected metric to display ("DoseRate" or "CountRate").
        - color_range: Tuple with (min, max) values for the color scale. If None, use data range.
        - color_map: Name of the intended color map
        """
        # Generate a Folium map
        map_object = folium.Map(location=[lat, lon], zoom_start=zoom)

        if data is not None:
            # Determine min and max values for the color scale
            if color_range is None:
                metric_min = data[metric].min()
                metric_max = data[metric].max()
            else:
                metric_min, metric_max = color_range

            if metric_min >= metric_max:
                print("Error: Minimum color value must be less than the maximum.")
                return

            # Create a linear colormap directly scaled to the selected metric range
            norm = colors.Normalize(vmin=metric_min, vmax=metric_max)
            colormap = colormaps[self.current_colormap_name]
            linear_colormap = LinearColormap(
                [colors.rgb2hex(colormap(norm(value))) for value in np.linspace(metric_min, metric_max, 256)],
                vmin=metric_min, vmax=metric_max, caption=f"{self.metricSelected} [{self.metricUnits[self.metricSelected]}]"
            )

            # Add color-coded markers
            for _, row in data.iterrows():
                value = row[metric]
                color = linear_colormap(value)  # Get color directly from colormap

                folium.CircleMarker(
                    location=[row["Latitude"], row["Longitude"]],
                    radius=5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    popup=folium.Popup(f"{metric}: {value:.2f}<br>Time: {row['Time']}", max_width="200")
                ).add_to(map_object)

            # Add colorbar to the map
            linear_colormap.add_to(map_object)

        # Save and display the map
        self.map_file = os.path.join(os.getcwd(), "map.html")
        map_object.save(self.map_file)
        self.map_view.setUrl(QUrl.fromLocalFile(self.map_file))
        
        # Enable buttons
        self.time_plot_button.setEnabled(True)
        self.export_button.setEnabled(True)
        

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select .rctrk File", "", "RCTRK Files (*.rctrk);;All Files (*)")
        if file_path:
            data = self.parse_rctrk_file(file_path)
            if data is not None:
                if self.loaded_data is None:
                    self.loaded_data = data
                else:
                    self.loaded_data = pd.concat([self.loaded_data, data], ignore_index=True)

                self.min_time = pd.to_datetime(self.loaded_data["Time"]).min()
                self.max_time = pd.to_datetime(self.loaded_data["Time"]).max()
                self.min_doseRate = self.loaded_data["DoseRate"].min()
                self.max_doseRate = self.loaded_data["DoseRate"].max()
                self.min_countRate = self.loaded_data["CountRate"].min()
                self.max_countRate = self.loaded_data["CountRate"].max()
                self.range_doseRate = (self.max_doseRate-self.min_doseRate)
                self.range_countRate = (self.max_countRate-self.min_countRate)
                
                if self.metricSelected == "DoseRate":
                    self.setAbsoluteMin = self.min_doseRate
                    self.setAbsoluteMax = self.max_doseRate
                    self.setAbsoluteRange = self.range_doseRate
                else:
                    self.setAbsoluteMin = self.min_countRate
                    self.setAbsoluteMax = self.max_countRate
                    self.setAbsoluteRange = self.range_countRate
                self.color_min_slider_label.setText("Min: {:.1f} {:s}".format(self.setAbsoluteMin, self.metricUnits[self.metricSelected]))
                self.color_max_slider_label.setText("Max: {:.1f} {:s}".format(self.setAbsoluteMax, self.metricUnits[self.metricSelected]))
                
                self.start_time_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(self.min_time.timestamp())))
                self.stop_time_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(self.max_time.timestamp())))
                
                print("DEBUG: self.min_time", self.min_time.timestamp())
                print("DEBUG: self.max_time", self.max_time.timestamp())
                print("DEBUG: self.min_time", QDateTime.fromSecsSinceEpoch(int(self.min_time.timestamp())))
                print("DEBUG: self.max_time", QDateTime.fromSecsSinceEpoch(int(self.max_time.timestamp())))
                
                self.update_display()

    def parse_rctrk_file(self, file_path):
        try:
            data = pd.read_csv(file_path, sep="\t", skiprows=1)
            data = data[["Time", "Latitude", "Longitude", "DoseRate", "CountRate"]]
            data.dropna(inplace=True)
            data["Time"] = pd.to_datetime(data["Time"])
            return data
        except Exception as e:
            print(f"Error parsing file: {e}")
            return None

    def update_display(self):
        """Update the map based on selected display field, time range, and color scale."""
        if self.loaded_data is not None:
            # Get selected metric
            self.metricSelected = self.display_field_dropdown.currentText()
            self.current_colormap_name = self.colormap_dropdown.currentText()

            # Get slider values for the color range
            min_value_relative = self.color_min_slider.value()
            max_value_relative = self.color_max_slider.value()

            # Ensure min < max
            if min_value_relative >= max_value_relative:
                print("Error: Minimum color value must be less than the maximum.")
                return

            slider_min_absolute = (min_value_relative / 100) * self.setAbsoluteRange + self.setAbsoluteMin
            slider_max_absolute = (max_value_relative / 100) * self.setAbsoluteRange + self.setAbsoluteMin

            # Update slider labels
            self.color_min_slider_label.setText(f"Min: {slider_min_absolute:.1f} {self.metricUnits[self.metricSelected]}")
            self.color_max_slider_label.setText(f"Max: {slider_max_absolute:.1f} {self.metricUnits[self.metricSelected]}")

            # Filter data by time
            self.start_time = self.start_time_edit.dateTime().toPyDateTime()
            self.stop_time = self.stop_time_edit.dateTime().toPyDateTime()
            print("DEBUG: self.start_time", self.start_time.timestamp())
            print("DEBUG: self.stop_time", self.stop_time.timestamp())
            print("DEBUG: self.start_time", QDateTime.fromSecsSinceEpoch(int(self.start_time.timestamp())))
            print("DEBUG: self.stop_time", QDateTime.fromSecsSinceEpoch(int(self.stop_time.timestamp())))

            self.filtered_data = self.loaded_data[
                (pd.to_datetime(self.loaded_data["Time"]) >= self.start_time) & (pd.to_datetime(self.loaded_data["Time"]) <= self.stop_time)
            ]

            if self.filtered_data.empty:
                print("No data available for the selected time range.")
                return

            # Reload the map with updated filters
            self.load_map(
                lat=self.filtered_data["Latitude"].mean(),
                lon=self.filtered_data["Longitude"].mean(),
                zoom=12,
                data=self.filtered_data,
                metric=self.metricSelected,
                color_range=(slider_min_absolute, slider_max_absolute),
                color_map=self.current_colormap_name,
            )


    def clear_data(self):
        self.loaded_data = None
        self.start_time_edit.setDateTime(QDateTime.currentDateTime())
        self.stop_time_edit.setDateTime(QDateTime.currentDateTime())
        self.load_map()

    def export_html(self):
        if self.map_file:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Map as HTML", "", "HTML Files (*.html)")
            if file_path:
                os.rename(self.map_file, file_path)

    def show_time_plot(self):
        if self.loaded_data is not None:
            # Filter data within the selected time range
            start_time = self.start_time_edit.dateTime().toPyDateTime()
            stop_time = self.stop_time_edit.dateTime().toPyDateTime()
            filtered_data = self.loaded_data[
                (self.loaded_data["Time"] >= start_time) & (self.loaded_data["Time"] <= stop_time)
            ]

            if filtered_data.empty:
                print("No data available for the selected time range.")
                return

            # Open a new window for the time plot
            self.time_plot_window = TimePlotWindow(filtered_data, self.metricSelected)
            self.time_plot_window.show()
           

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MapWindow()
    window.show()
    sys.exit(app.exec_())