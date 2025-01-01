import sys
import os
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QFileDialog, QComboBox, QLabel
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import folium
from matplotlib import colors
from matplotlib import colormaps
from branca.colormap import LinearColormap

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RadiaCode Track Viewer")
        self.setGeometry(100, 100, 1000, 700)
        
        # Default colormap
        self.current_colormap_name = "viridis"
        self.loaded_data = None  # To store currently loaded data
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Set up main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create a QWebEngineView for map display
        self.map_view = QWebEngineView()
        main_layout.addWidget(self.map_view)
        
        # Add control layout at the bottom
        control_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)
        
        # Dropdown menu for colormap selection
        self.colormap_dropdown = QComboBox()
        self.colormap_dropdown.addItems(sorted(colormaps.keys()))  # Add all matplotlib colormaps
        self.colormap_dropdown.setCurrentText(self.current_colormap_name)
        self.colormap_dropdown.currentTextChanged.connect(self.update_colormap)
        control_layout.addWidget(QLabel("Select Colormap:"))
        control_layout.addWidget(self.colormap_dropdown)
        
        # Add a button for file selection
        self.select_file_button = QPushButton("Select .rctrk File")
        self.select_file_button.clicked.connect(self.select_file)
        control_layout.addWidget(self.select_file_button)
        
        # Load the initial basemap
        self.load_map()
    
    def load_map(self, lat=0, lon=0, zoom=2, data=None):
        # Generate a Folium map
        map_object = folium.Map(location=[lat, lon], zoom_start=zoom)
        
        # If data is provided, plot it with color-coded markers
        if data is not None:
            min_dose = data["DoseRate"].min()
            max_dose = data["DoseRate"].max()
            
            # Normalize DoseRate for color mapping
            norm = colors.Normalize(vmin=min_dose, vmax=max_dose)
            colormap = colormaps[self.current_colormap_name]
            branca_colormap = LinearColormap(
                [colors.rgb2hex(colormap(norm(value))) for value in np.linspace(min_dose, max_dose, 256)],
                vmin=min_dose, vmax=max_dose, caption="Dose Rate [µSv/h]"
            )
            
            # Add color-coded markers
            for _, row in data.iterrows():
                rgba_color = colormap(norm(row["DoseRate"]))
                hex_color = colors.rgb2hex(rgba_color)
                
                folium.CircleMarker(
                    location=[row["Latitude"], row["Longitude"]],
                    radius=5,
                    color=hex_color,
                    fill=True,
                    fill_color=hex_color,
                    fill_opacity=0.7,
                    popup=folium.Popup(f"Dose rate: {row['DoseRate']} µSv/h<br>Count rate: {row['CountRate']} cps<br>Time: {row['Time']}", max_width="200")
                ).add_to(map_object)
            
            # Add colorbar to the map
            branca_colormap.add_to(map_object)
        
        # Save the map to an HTML file
        self.map_file = os.path.join(os.getcwd(), "map.html")
        map_object.save(self.map_file)
        
        # Load the HTML file in the QWebEngineView
        self.map_view.setUrl(QUrl.fromLocalFile(self.map_file))
    
    def select_file(self):
        # Open a file dialog to select the .rctrk file
        file_path, _ = QFileDialog.getOpenFileName(self, "Select .rctrk File", "", "RCTRK Files (*.rctrk);;All Files (*)")
        
        if file_path:
            # Parse the file and extract the data
            data = self.parse_rctrk_file(file_path)
            
            # If data is valid, reload the map with the plotted data
            if data is not None:
                self.loaded_data = data  # Save the loaded data
                self.load_map(lat=data["Latitude"].mean(), lon=data["Longitude"].mean(), zoom=15, data=data)
    
    def parse_rctrk_file(self, file_path):
        try:
            # Read the .rctrk file as a tab-delimited file
            data = pd.read_csv(file_path, sep="\t", skiprows=1)  # Skip the header row
            
            # Extract relevant columns
            data = data[["Time", "Latitude", "Longitude", "DoseRate", "CountRate"]]
            
            # Drop rows with missing values
            data.dropna(subset=["Time", "Latitude", "Longitude", "DoseRate", "CountRate"], inplace=True)
            
            return data
        except Exception as e:
            print(f"Error parsing file: {e}")
            return None
    
    def update_colormap(self, colormap_name):
        """Update the current colormap and reload the map with the loaded data."""
        self.current_colormap_name = colormap_name
        if self.loaded_data is not None:
            self.load_map(
                lat=self.loaded_data["Latitude"].mean(),
                lon=self.loaded_data["Longitude"].mean(),
                zoom=15,
                data=self.loaded_data
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MapWindow()
    window.show()
    sys.exit(app.exec_())