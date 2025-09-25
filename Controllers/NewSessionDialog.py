from ui.CreateNewSessionWindow_v9 import Ui_Dialog as Ui_NewSessionWindow
from PyQt6.QtWidgets import QDialog, QLineEdit, QComboBox, QFileDialog, QTableWidgetItem, QVBoxLayout, QWidget
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QKeyEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from pathlib import Path
import numpy as np
import json
from main_v2.file_managerv2 import FileManager
from main_v2.supplementary_classes import DatasetConstraints, QueryMethodConfig, GridConfig, InputManager



class NewSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__()
        self.ui = Ui_NewSessionWindow()
        self.ui.setupUi(self)
        self.show()

        # These fields are instantiated here for reference. They are compiled elsewhere.
        self.dataset_constraints = None
        self.query_method_config = None
        self.grid_config = None
        self.file_manager = None
        self.hash_str = None

        "Get relevant paths"
        # Get root directories
        self.settings = QSettings("PythonProjects","QueryApp")
        self.app_dir = Path(__file__).resolve().parent.parent
        self.data_dir = Path(self.settings.value("data_directory", str(Path.home() / "turb_data")))

        # Auto-populate saved data directory into line edit
        self.populate_data_directory()

        # Get JHU Datasets metadata directory
        self.datasets_dir_path = (Path(__file__).resolve()).parents[1] / "JHUTDDatasets"

        "Initial Settings"
        self.all_fields_filled = False
        self.ui.comboBox_Input_Variable.setEnabled(False)
        self.update_dataset_info_display_panel(True)
        self.inputs_are_enabled = False
        self.set_grid_inputs_status(enable=False)

        "Remove after development. Only for testing"
        self.ui.comboBox_Input_DatasetTitle.addItem("Channel")
        # self.ui.comboBox_Input_Variable.addItem("pressure")
        self.ui.comboBox_Input_SpatialMethod.addItem("Lag8")
        self.ui.comboBox_Input_SpatialOperator.addItem("Field")
        self.ui.comboBox_Input_TemporalMethod.addItem("None")

        "Unique pushbutton behaviors"
        # Enable variable combo box once dataset is selected
        self.ui.comboBox_Input_DatasetTitle.currentIndexChanged.connect(self._on_index_change_dataset_title_combobox)

        # Open file explorer for "browse" pushbutton
        self.ui.pushButton.clicked.connect(self.browse_directory)

        # Close dialog with "cancel" pushbutton
        self.ui.pushButton_Cancel.clicked.connect(self.accept)

        # Create new session pushbutton
        self.ui.pushButton_CreateSession.clicked.connect(self._create_button_pressed)


    """
    Dispatcher functions -----------------------------------------------------------------------------------------------
    """
    def _on_index_change_dataset_title_combobox(self):
        if self.ui.comboBox_Input_DatasetTitle.currentIndex() <= 0:
            placeholder_is_selected = True
            self.inputs_are_enabled = False
        else:
            placeholder_is_selected = False
            self.inputs_are_enabled = True

        self.update_input_fields(placeholder_is_selected)
        self._init_input_manager(placeholder_is_selected)
        self.update_input_signals(placeholder_is_selected)
        self.update_dataset_info_display_panel(placeholder_is_selected)

        self.update_create_button()
        self.init_3D_viewer(placeholder_is_selected=placeholder_is_selected,
            x_range=(self.input_manager.limits["start_x"], self.input_manager.limits["end_x"]),
            y_range=(self.input_manager.limits["start_y"], self.input_manager.limits["end_y"]),
            z_range=(self.input_manager.limits["start_z"], self.input_manager.limits["end_z"])
        )


    def _create_button_pressed(self):
        # Create the config classes needed to instantiate FileManager
        self.create_config_classes()

        self.hash_str = FileManager.generate_hash(
            self.dataset_constraints, self.query_method_config,self.grid_config)

        # Instantiate file manager
        self.init_file_manager()

        # Check existence of hash
        if self.hash_is_unique():
            self._finalize_creation()
        else:
            self.ui.label_InputFeedback.setText("That volume series already exists.")


    def _finalize_creation(self):
        # Finalize file manager
        # self.file_manager.init_series_paths(self.ui.comboBox_Input_Variable.currentText().lower())
        self.file_manager.set_custom_tag(self.ui.lineEdit_CustomName.text().lower())
        self.file_manager.set_dataset_metadata_path(self.dataset_metadata_path)

        self.file_manager.init_files_for_all_variables()
        # self.file_manager.paths.generate_variable_dependent_paths(
        #     self.hash_str, self.ui.comboBox_Input_Variable.currentText().lower())
        # self.file_manager.generate_directories()
        # self.file_manager.generate_files()
        # Get new entry for hash log

        new_entry = self.file_manager.get_new_hash_log_entry()
        hash_log_path = self.file_manager.paths.files.hash_log_path

        # Load existing hash log if it exists
        hash_log = self.file_manager.load_hash_log(self.data_dir)

        # Add new entry to hash log
        hash_log[self.file_manager.hash_str] = new_entry

        # Write updated hash_log back to file
        with open(hash_log_path, "w") as f:
            json.dump(hash_log, f, indent=4)

        # Save data directory to QSettings
        self.settings.setValue("data_directory", self.data_dir)

        # Close the window under the 'accept' flag
        self.accept()


    """
    Update environment functions ---------------------------------------------------------------------------------------
    """
    def populate_data_directory(self):
        if self.data_dir == "" or self.data_dir is None:
            current_root = str(Path.cwd().parent)
            self.ui.lineEdit_Input_RootDirectory.setText(current_root)
            self.data_dir = Path(current_root)
        else:
            self.ui.lineEdit_Input_RootDirectory.setText(str(self.data_dir))


    def update_input_fields(self, placeholder_is_selected):
        if placeholder_is_selected:
            # 1. Clear all items and add pretext to variable combo box
            self.ui.comboBox_Input_Variable.clear()
            self.ui.comboBox_Input_Variable.addItem("Select...")

            # 2. Clear all grid input
            self.clear_grid_input_widgets()

            # 2. Disable variable combo box and all grid inputs
            self.ui.comboBox_Input_Variable.setEnabled(False)
            self.set_grid_inputs_status(enable=False)

        else:
            # 1. Clear all grid inputs and variable combo box
            self.ui.comboBox_Input_Variable.clear()
            self.clear_grid_input_widgets()

            # 2. Re-attach variable combo box pretext
            self.ui.comboBox_Input_Variable.addItem("Select...")

            # 3. Load dataset metadata json
            index = self.ui.comboBox_Input_DatasetTitle.currentIndex()
            dataset_selected = self.ui.comboBox_Input_DatasetTitle.itemText(index)
            self.dataset_metadata_path = self.datasets_dir_path / dataset_selected / (dataset_selected + "_metadata.json")

            with open(self.dataset_metadata_path, "r") as f:
                self.metadata = json.load(f)

            # 4. Add variables to variable combo box
            for var in self.metadata["display"]["variables"]:
                self.ui.comboBox_Input_Variable.addItem(var.capitalize())

            # 5. Enable variable combo box and all grid inputs
            self.ui.comboBox_Input_Variable.setEnabled(True)
            self.set_grid_inputs_status(enable=True)


    def update_dataset_info_display_panel(self, placeholder_is_selected):
        if placeholder_is_selected:
            self.ui.tableWidget_DatasetSelectionVariables.clear()
            self.ui.label_DatasetSelectionValue.clear()
            self.ui.label_DomainXValue.clear()
            self.ui.label_DomainYValue.clear()
            self.ui.label_DomainZValue.clear()
            self.ui.label_DomainTValue.clear()
            self.ui.label_NodesXValue.clear()
            self.ui.label_NodesYValue.clear()
            self.ui.label_NodesZValue.clear()
            self.ui.label_NodesTValue.clear()

        else:
            # 1. Update table widget items
            self.ui.tableWidget_DatasetSelectionVariables.clear()
            for i in range(len(self.metadata["display"]["variables"])):
                var = QTableWidgetItem(self.metadata["display"]["variables"][i].capitalize())
                self.ui.tableWidget_DatasetSelectionVariables.setItem(i, 0, var)

            # 2. Update labels
            self.ui.label_DatasetSelectionValue.setText(self.metadata["display"]["dataset_title"].capitalize())
            self.ui.label_DomainXValue.setText(f"[{self.metadata["display"]["start_x"]}, {self.metadata["display"]["end_x"]}]")
            self.ui.label_DomainYValue.setText(f"[{self.metadata["display"]["start_y"]}, {self.metadata["display"]["end_y"]}]")
            self.ui.label_DomainZValue.setText(f"[{self.metadata["display"]["start_z"]}, {self.metadata["display"]["end_z"]}]")
            self.ui.label_DomainTValue.setText(f"[{self.metadata["display"]["start_t"]}, {self.metadata["display"]["end_t"]}]")
            self.ui.label_NodesXValue.setText(self.metadata["display"]["nodes_x"])
            self.ui.label_NodesYValue.setText(self.metadata["display"]["nodes_y"])
            self.ui.label_NodesZValue.setText(self.metadata["display"]["nodes_z"])
            self.ui.label_NodesTValue.setText(self.metadata["display"]["nodes_t"])


    def update_create_button(self):
        errors = []

        # Auto-set a top-priority error message to begging of errors list
        if not self.input_manager.all_fields_filled():
            errors.append("Incomplete fields detected")

        # Validate all grid inputs and append to errors list
        grid_errors = self.input_manager.validate_grid_inputs()
        errors.extend(grid_errors)

        # Plot user's subvolume once all grid inputs are valid
        if len(grid_errors) == 0:
            self.input_manager.get_user_bounds()
            self.viewer3d.plot_user_volume(
                limits=self.input_manager.limits,
                x_range=(self.input_manager.user_bounds["x"][0], self.input_manager.user_bounds["x"][1]),
                y_range=(self.input_manager.user_bounds["y"][0], self.input_manager.user_bounds["y"][1]),
                z_range=(self.input_manager.user_bounds["z"][0], self.input_manager.user_bounds["z"][1]),
                color="red",
                alpha=1.0,
                lw=2
            )

        # Update create session pushbutton and feedback label
        if len(errors) == 0:
            self.ui.pushButton_CreateSession.setEnabled(True)
            self.ui.label_InputFeedback.setText("")
        else:
            self.ui.pushButton_CreateSession.setEnabled(False)
            self.ui.label_InputFeedback.setText(errors[0])


    def init_3D_viewer(self, x_range, y_range, z_range, placeholder_is_selected=True):
        "3D Viewer"
        if not hasattr(self, "viewer3d"):
            self.viewer3d = Matplotlib3DViewer(self, x_range, y_range, z_range)
            layout = QVBoxLayout(self.ui.widget_3DViewerWidgetPlaceholder)
            layout.addWidget(self.viewer3d)

        if placeholder_is_selected:
            self.viewer3d.clear_view()
        else:
            self.viewer3d.clear_view()
            self.viewer3d.plot_box_edges(x_range, y_range, z_range, color="black", lw=2)


    """
    Other functions ----------------------------------------------------------------------------------------------------
    """
    def update_input_signals(self, placeholder_is_selected=False):
        if placeholder_is_selected:
            return
        else:
            # Connect all input signals for every new input manager instance
            for field in self.input_manager._fields.values():
                if isinstance(field['widget'], QLineEdit):
                    field['widget'].textChanged.connect(self.update_create_button)
                elif isinstance(field['widget'], QComboBox):
                    field['widget'].currentIndexChanged.connect(self.update_create_button)


    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Data Directory",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.ui.lineEdit_Input_RootDirectory.setText(directory)
            self.data_dir = Path(directory)


    def _init_input_manager(self, placeholder_is_selected):
        if placeholder_is_selected:
            return
        else:
            limits = self.metadata["raw"]
            self.input_manager = NewSessionInputManager(
                comboBox_Input_DatasetTitle={"widget":self.ui.comboBox_Input_DatasetTitle,
                                             "type": "combo", "container":"method"},
                comboBox_Input_Variable={"widget":self.ui.comboBox_Input_Variable,
                                         "type": "combo", "container":"method"},
                comboBox_Input_SpatialMethod={"widget":self.ui.comboBox_Input_SpatialMethod,
                                              "type": "combo", "container":"method"},
                comboBox_Input_SpatialOperator={"widget":self.ui.comboBox_Input_SpatialOperator,
                                                "type": "combo", "container":"method"},
                comboBox_Input_TemporalMethod={"widget":self.ui.comboBox_Input_TemporalMethod,
                                               "type": "combo", "container":"method"},
                # lineEdit_CustomName={"widget":self.ui.lineEdit_CustomName,
                #                      "type": "str", "container":"method"},
                lineEdit_Input_RootDirectory={"widget":self.ui.lineEdit_Input_RootDirectory,
                                              "type":"path", "container":"method"},
                lineEdit_Input_Nx={"widget":self.ui.lineEdit_Input_Nx,
                                   "type": "int", "container":"grid", "min":1, "max":limits["nodes_x"]},
                lineEdit_Input_Ny={"widget":self.ui.lineEdit_Input_Ny,
                                   "type": "int", "container":"grid", "min":1, "max":limits["nodes_y"]},
                lineEdit_Input_Nz={"widget":self.ui.lineEdit_Input_Nz,
                                   "type": "int", "container":"grid", "min":1, "max":limits["nodes_z"]},
                lineEdit_Input_Nt={"widget":self.ui.lineEdit_Input_Nt,
                                   "type": "int", "container":"grid", "min":1, "max":limits["nodes_t"]},
                lineEdit_Input_StartX={"widget":self.ui.lineEdit_Input_StartX,
                                       "type": "float", "container":"grid", "min":limits["start_x"], "max":limits["end_x"]},
                lineEdit_Input_EndX={"widget":self.ui.lineEdit_Input_EndX,
                                     "type": "float", "container":"grid", "min":limits["start_x"], "max":limits["end_x"]},
                lineEdit_Input_StartY={"widget":self.ui.lineEdit_Input_StartY,
                                       "type": "float", "container":"grid", "min":limits["start_y"], "max":limits["end_y"]},
                lineEdit_Input_EndY={"widget":self.ui.lineEdit_Input_EndY,
                                     "type": "float", "container":"grid", "min":limits["start_y"], "max":limits["end_y"]},
                lineEdit_Input_StartZ={"widget":self.ui.lineEdit_Input_StartZ,
                                       "type": "float", "container":"grid", "min":limits["start_z"], "max":limits["end_z"]},
                lineEdit_Input_EndZ={"widget":self.ui.lineEdit_Input_EndZ,
                                     "type": "float", "container":"grid", "min":limits["start_z"], "max":limits["end_z"]},
                lineEdit_Input_StartT={"widget":self.ui.lineEdit_Input_StartT,
                                       "type": "float", "container":"grid", "min":limits["start_t"], "max":limits["end_t"]},
                lineEdit_Input_EndT={"widget":self.ui.lineEdit_Input_EndT,
                                     "type": "float", "container":"grid", "min":limits["start_t"], "max":limits["end_t"]}
            )
            self.input_manager.set_limits(limits)
            self.input_manager.attach_validators()
            # self.update_create_button()


    def set_grid_inputs_status(self, enable=False):
        "Allows togglability to all grid input widgets"
        self.ui.lineEdit_Input_Nx.setEnabled(enable)
        self.ui.lineEdit_Input_Ny.setEnabled(enable)
        self.ui.lineEdit_Input_Nz.setEnabled(enable)
        self.ui.lineEdit_Input_Nt.setEnabled(enable)
        self.ui.lineEdit_Input_StartX.setEnabled(enable)
        self.ui.lineEdit_Input_StartY.setEnabled(enable)
        self.ui.lineEdit_Input_StartZ.setEnabled(enable)
        self.ui.lineEdit_Input_StartT.setEnabled(enable)
        self.ui.lineEdit_Input_EndX.setEnabled(enable)
        self.ui.lineEdit_Input_EndY.setEnabled(enable)
        self.ui.lineEdit_Input_EndZ.setEnabled(enable)
        self.ui.lineEdit_Input_EndT.setEnabled(enable)


    def clear_grid_input_widgets(self):
        "Clears all grid input widgets"
        self.ui.lineEdit_Input_Nx.clear()
        self.ui.lineEdit_Input_Ny.clear()
        self.ui.lineEdit_Input_Nz.clear()
        self.ui.lineEdit_Input_Nt.clear()
        self.ui.lineEdit_Input_StartX.clear()
        self.ui.lineEdit_Input_StartY.clear()
        self.ui.lineEdit_Input_StartZ.clear()
        self.ui.lineEdit_Input_StartT.clear()
        self.ui.lineEdit_Input_EndX.clear()
        self.ui.lineEdit_Input_EndY.clear()
        self.ui.lineEdit_Input_EndZ.clear()
        self.ui.lineEdit_Input_EndT.clear()


    def keyPressEvent(self, event:QKeyEvent):
        "Disables Enter key from closing dialog"
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.ignore()
            return
        super().keyPressEvent(event)


    def create_config_classes(self):
        dataset_constraints = dict()
        query_method_config = dict()
        grid_config = dict()

        self.input_manager.get_user_bounds()
        dataset_constraints["min_dt"] = self.input_manager.limits["min_dt"]
        dataset_constraints["domain_x"] = (self.input_manager.limits["start_x"], self.input_manager.limits["end_x"])
        dataset_constraints["domain_y"] = (self.input_manager.limits["start_y"], self.input_manager.limits["end_y"])
        dataset_constraints["domain_z"] = (self.input_manager.limits["start_z"], self.input_manager.limits["end_z"])
        dataset_constraints["domain_t"] = (self.input_manager.limits["start_t"], self.input_manager.limits["end_t"])
        dataset_constraints["max_res_x"] = self.input_manager.limits["nodes_x"]
        dataset_constraints["max_res_y"] = self.input_manager.limits["nodes_y"]
        dataset_constraints["max_res_z"] = self.input_manager.limits["nodes_z"]
        dataset_constraints["max_res_z"] = self.input_manager.limits["nodes_t"]
        dataset_constraints["dataset_variables"] = self.input_manager.limits["variables"]
        dataset_constraints["variable_components"] = self.input_manager.limits["variable_components"]

        query_method_config["dataset_title"] = self.ui.comboBox_Input_DatasetTitle.currentText()
        query_method_config["temporal_method"] = self.ui.comboBox_Input_TemporalMethod.currentText()
        query_method_config["spatial_method"] = self.ui.comboBox_Input_SpatialMethod.currentText()
        query_method_config["spatial_operator"] = self.ui.comboBox_Input_SpatialOperator.currentText()

        grid_config["nx"] = int(self.ui.lineEdit_Input_Nx.text())
        grid_config["ny"] = int(self.ui.lineEdit_Input_Ny.text())
        grid_config["nz"] = int(self.ui.lineEdit_Input_Nz.text())
        grid_config["nt"] = int(self.ui.lineEdit_Input_Nt.text())
        grid_config["x_bounds"] = self.input_manager.user_bounds["x"]
        grid_config["y_bounds"] = self.input_manager.user_bounds["y"]
        grid_config["z_bounds"] = self.input_manager.user_bounds["z"]
        grid_config["t_bounds"] = self.input_manager.user_bounds["t"]

        self.dataset_constraints = DatasetConstraints(dataset_constraints)
        self.query_method_config = QueryMethodConfig(query_method_config)
        self.grid_config = GridConfig(grid_config)


    def init_file_manager(self):

        self.file_manager = FileManager(
            variable=self.ui.comboBox_Input_Variable.currentText().lower(),
            data_dir=self.data_dir,
            app_dir=self.app_dir,
            hash_str=self.hash_str,
            dataset_constraints=self.dataset_constraints,
            query_method_config=self.query_method_config,
            grid_config=self.grid_config
        )
        self.file_manager.paths.yvals_filepath = self.metadata["raw"]["yvals_filepath"]


    def hash_is_unique(self):
        hash_log = FileManager.load_hash_log(self.data_dir)

        return not FileManager.hash_exists(self.hash_str, hash_log)

"""
INPUT MANAGER ----------------------------------------------------------------------------------------------------------
"""
class NewSessionInputManager(InputManager):
    def __init__(self, **fields):
        super().__init__(**fields)

    def set_limits(self, limits):
        self.limits = limits

    def get_user_bounds(self):
        "Build x/y/z/t bounds dict from dialog fields"
        return {
            "x": (float(self._fields["lineEdit_Input_StartX"]["widget"].text()),
                  float(self._fields["lineEdit_Input_EndX"]["widget"].text())),
            "y": (float(self._fields["lineEdit_Input_StartY"]["widget"].text()),
                  float(self._fields["lineEdit_Input_EndY"]["widget"].text())),
            "z": (float(self._fields["lineEdit_Input_StartZ"]["widget"].text()),
                  float(self._fields["lineEdit_Input_EndZ"]["widget"].text())),
            "t": (float(self._fields["lineEdit_Input_StartT"]["widget"].text()),
                  float(self._fields["lineEdit_Input_EndT"]["widget"].text()))
        }

    def get_user_bounds(self):
        start_x = float(self._fields["lineEdit_Input_StartX"]["widget"].text())
        end_x = float(self._fields["lineEdit_Input_EndX"]["widget"].text())
        start_y = float(self._fields["lineEdit_Input_StartY"]["widget"].text())
        end_y = float(self._fields["lineEdit_Input_EndY"]["widget"].text())
        start_z = float(self._fields["lineEdit_Input_StartZ"]["widget"].text())
        end_z = float(self._fields["lineEdit_Input_EndZ"]["widget"].text())
        start_t = float(self._fields["lineEdit_Input_StartT"]["widget"].text())
        end_t = float(self._fields["lineEdit_Input_EndT"]["widget"].text())

        self.user_bounds = {}
        self.user_bounds["x"] = (start_x, end_x)
        self.user_bounds["y"] = (start_y, end_y)
        self.user_bounds["z"] = (start_z, end_z)
        self.user_bounds["t"] = (start_t, end_t)

    def validate_grid_inputs(self):
        "Override with grid-specific logic like Nx, Ny, Nz"
        range_pairs = [
            (self._fields["lineEdit_Input_StartX"], self._fields["lineEdit_Input_EndX"],
             self._fields["lineEdit_Input_Nx"], "x"),
            (self._fields["lineEdit_Input_StartY"], self._fields["lineEdit_Input_EndY"],
             self._fields["lineEdit_Input_Ny"], "y"),
            (self._fields["lineEdit_Input_StartZ"], self._fields["lineEdit_Input_EndZ"],
             self._fields["lineEdit_Input_Nz"], "z"),
            (self._fields["lineEdit_Input_StartT"], self._fields["lineEdit_Input_EndT"],
             self._fields["lineEdit_Input_Nt"], "t")
        ]
        errors = []

        for start, end, nodes, axis in range_pairs:
            start_text = start["widget"].text().strip()
            end_text = end["widget"].text().strip()
            nodes_text = nodes["widget"].text().strip()
            if not start_text or not end_text:
                errors.append("Incomplete range field detected")
                break
            if not nodes_text:
                errors.append("Incomplete node field detected")

            start_val = float(start_text)
            end_val = float(end_text)
            nodes_val = int(nodes_text)

            # Validate start/end values
            if ((start_val > end_val) or
                    (start_val < start["min"] or start_val > start["max"]) or
                    (end_val < end["min"] or end_val > end["max"])):
                errors.append("Invalid range field detected")

            # Validate node values
            if nodes_val < nodes["min"] or nodes_val > nodes["max"]:
                errors.append("Invalid node field detected")

            # Validated start/end values with node values
            if ((nodes_val == 1 and start_val != end_val) or
                    (nodes_val != 1 and start_val == end_val)):
                errors.append("Invalid range/node field detected")

        return errors


"""
Helper classes ---------------------------------------------------------------------------------------------------------
"""
# class InputManager:
#     def __init__(self, **kwargs):
#         self.user_bounds = {}
#         self._fields = {}
#         for key, entry in kwargs.items():
#             self._fields[key] = entry
#
    # def set_limits(self, limits):
    #     self.limits = limits
#
#
    # def get_user_bounds(self):
    #     start_x = float(self._fields["lineEdit_Input_StartX"]["widget"].text())
    #     end_x = float(self._fields["lineEdit_Input_EndX"]["widget"].text())
    #     start_y = float(self._fields["lineEdit_Input_StartY"]["widget"].text())
    #     end_y = float(self._fields["lineEdit_Input_EndY"]["widget"].text())
    #     start_z = float(self._fields["lineEdit_Input_StartZ"]["widget"].text())
    #     end_z = float(self._fields["lineEdit_Input_EndZ"]["widget"].text())
    #     start_t = float(self._fields["lineEdit_Input_StartT"]["widget"].text())
    #     end_t = float(self._fields["lineEdit_Input_EndT"]["widget"].text())
    #
    #     self.user_bounds = {}
    #     self.user_bounds["x"] = (start_x, end_x)
    #     self.user_bounds["y"] = (start_y, end_y)
    #     self.user_bounds["z"] = (start_z, end_z)
    #     self.user_bounds["t"] = (start_t, end_t)
#
#
#     def all_fields_filled(self):
#         "Returns True if all inputted fields are NOT empty. Else, it returns False"
#         for entry in self._fields.values():
#             if isinstance(entry["widget"], QLineEdit):
#                 if not entry["widget"].text().strip():
#                     return False
#
#             elif isinstance(entry["widget"], QComboBox):
#                 if entry["widget"].currentIndex() < 0:
#                     return False
#
#         return True
#
#
#     def attach_validators(self):
#         "Attaches QValidator objects to widgets"
#         for ent in self._fields.values():
#             widget = ent["widget"]
#             if ent["type"] == "int":
#                 validator = QIntValidator(ent["min"], ent["max"], widget)
#                 widget.setValidator(validator)
#
#             if ent["type"] == "float":
#                 validator = QDoubleValidator(ent["min"], ent["max"], 4, widget)
#                 validator.setNotation(QDoubleValidator.Notation.StandardNotation)
#                 widget.setValidator(validator)
#
#
    # def validate_grid_inputs(self):
    #     range_pairs = [
    #         (self._fields["lineEdit_Input_StartX"], self._fields["lineEdit_Input_EndX"], self._fields["lineEdit_Input_Nx"], "x"),
    #         (self._fields["lineEdit_Input_StartY"], self._fields["lineEdit_Input_EndY"], self._fields["lineEdit_Input_Ny"], "y"),
    #         (self._fields["lineEdit_Input_StartZ"], self._fields["lineEdit_Input_EndZ"], self._fields["lineEdit_Input_Nz"], "z"),
    #         (self._fields["lineEdit_Input_StartT"], self._fields["lineEdit_Input_EndT"], self._fields["lineEdit_Input_Nt"], "t")
    #     ]
    #     errors = []
    #
    #     for start, end, nodes, axis in range_pairs:
    #         start_text = start["widget"].text().strip()
    #         end_text = end["widget"].text().strip()
    #         nodes_text = nodes["widget"].text().strip()
    #         if not start_text or not end_text:
    #             errors.append("Incomplete range field detected")
    #             break
    #         if not nodes_text:
    #             errors.append("Incomplete node field detected")
    #
    #         start_val = float(start_text)
    #         end_val = float(end_text)
    #         nodes_val = int(nodes_text)
    #
    #         # Validate start/end values
    #         if ((start_val > end_val) or
    #                 (start_val < start["min"] or start_val > start["max"]) or
    #                 (end_val < end["min"] or end_val > end["max"])):
    #             errors.append("Invalid range field detected")
    #
    #         # Validate node values
    #         if nodes_val < nodes["min"] or nodes_val > nodes["max"]:
    #             errors.append("Invalid node field detected")
    #
    #         # Validated start/end values with node values
    #         if ((nodes_val == 1 and start_val != end_val) or
    #                 (nodes_val != 1 and start_val == end_val)):
    #             errors.append("Invalid range/node field detected")
    #
    #
    #     return errors


"""
3D Viewer Widget -------------------------------------------------------------------------------------------------------
"""
class Matplotlib3DViewer(QWidget):
    def __init__(self, parent=None, x_range=(0,1), y_range=(0,1), z_range=(0,1)):
        super().__init__(parent)

        # Setup figure and canvas
        self.figure = Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111, projection='3d')

        # Add canvas into a layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

        # Draw initial volume box
        self.plot_box_edges(x_range, y_range, z_range)


    def plot_box_edges(self, x_range, y_range, z_range, color="black", alpha=1.0, lw=1.5):
        x_min, x_max = x_range
        y_min, y_max = y_range
        z_min, z_max = z_range

        corners = [
            (x_min, y_min, z_min),
            (x_max, y_min, z_min),
            (x_max, y_max, z_min),
            (x_min, y_max, z_min),
            (x_min, y_min, z_max),
            (x_max, y_min, z_max),
            (x_max, y_max, z_max),
            (x_min, y_max, z_max)
        ]

        edges = [
            (0,1),(1,2),(2,3),(3,0),
            (4,5),(5,6),(6,7),(7,4),
            (0,4),(1,5),(2,6),(3,7)
        ]

        for i, j in edges:
            x = [corners[i][0], corners[j][0]]
            y = [corners[i][1], corners[j][1]]
            z = [corners[i][2], corners[j][2]]
            self.ax.plot(x, y, z, color=color, lw=lw)

        dx = x_max - x_min
        dy = y_max - y_min
        dz = z_max - z_min

        self.ax.set_box_aspect([dx, dy, dz])
        self.canvas.draw()

    def plot_user_volume(self, limits, x_range, y_range, z_range, color="red", alpha=0.3, lw=1.0):
        # Clear user volume but not dataset edges
        self.ax.clear()

        # Re-plot dataset edges in black
        self.plot_box_edges(
            (limits["start_x"], limits["end_x"]),
            (limits["start_y"], limits["end_y"]),
            (limits["start_z"], limits["end_z"]),
            color="black",
            lw=1.5
        )

        # Now draw user-selected subvolume as filled faces
        x_min, x_max = x_range
        y_min, y_max = y_range
        z_min, z_max = z_range

        # Faces parallel to XY
        xx, yy = np.meshgrid([x_min, x_max], [y_min, y_max])
        self.ax.plot_surface(xx, yy, np.full_like(xx, z_min), color=color, alpha=alpha)  # bottom
        self.ax.plot_surface(xx, yy, np.full_like(xx, z_max), color=color, alpha=alpha)  # top

        # Faces parallel to XZ
        xx, zz = np.meshgrid([x_min, x_max], [z_min, z_max])
        self.ax.plot_surface(xx, np.full_like(xx, y_min), zz, color=color, alpha=alpha)  # front
        self.ax.plot_surface(xx, np.full_like(xx, y_max), zz, color=color, alpha=alpha)  # back

        # Faces parallel to YZ
        yy, zz = np.meshgrid([y_min, y_max], [z_min, z_max])
        self.ax.plot_surface(np.full_like(yy, x_min), yy, zz, color=color, alpha=alpha)  # left
        self.ax.plot_surface(np.full_like(yy, x_max), yy, zz, color=color, alpha=alpha)  # right

        # Keep aspect ratio correct
        dx = limits["end_x"] - limits["start_x"]
        dy = limits["end_y"] - limits["start_y"]
        dz = limits["end_z"] - limits["start_z"]
        self.ax.set_box_aspect([dx, dy, dz])

        self.canvas.draw()

    def clear_view(self):
        self.figure.clf()
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_box_aspect([1,1,1])
        self.canvas.draw()



















