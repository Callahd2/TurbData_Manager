from ui.LoadSessionWindow_v7 import Ui_Dialog as Ui_LoadSessionWindow
from PyQt6.QtWidgets import QDialog, QLineEdit, QTableWidgetItem, QDateEdit
from PyQt6.QtCore import QSettings
from pathlib import Path
import pandas as pd
from main_v2.file_managerv2 import FileManager
from main_v2.supplementary_classes import DatasetConstraints, QueryMethodConfig, GridConfig

# ...turb_data\datasets\channel\channel__xs=0_xe=8_nx=20__ys=0_ye=1_ny=6__zs=0_ze=3_nz=9__ts=1_te=10_nt=2__hash=d7991bc8

class LoadSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__()
        self.ui = Ui_LoadSessionWindow()
        self.ui.setupUi(self)
        self.show()

        "Get items from QSettings"
        # Get data directory
        self.settings = QSettings("PythonProjects", "QueryApp")
        self.data_dir = Path(self.settings.value("data_directory"))
        self.app_dir = Path(__file__).resolve().parent.parent
        self.ui.lineEdit_RootDirectory.setText(str(self.data_dir))
        self.ui.lineEdit_RootDirectory.setEnabled(True)

        # Instantiate input and search managers
        self.init_input_manager()
        self.search_manager = SearchManager(data_dir=self.data_dir)
        # self.search_manager.format_search_results()

        # Auto-populate saved data directory into line edit
        # self.populate_data_directory()

        "Instantiate relevant settings and fields"
        # Force initial settings on UI
        self.ui.dateEdit_Created.setEnabled(False)
        self.ui.dateEdit_LastModified.setEnabled(False)
        # self.input_manager.toggle_secondary_inputs(set_enable=False)

        # Initial settings for table widget
        self.filtered_results = self.search_manager.filter_search_results()
        self.ui.tableWidget_SearchResultsTable.setHorizontalHeaderLabels(
            ["Custom Tag", "Hash", "Dataset", "Variable", "Grid", "Date Created", "Date Last Modified"]
        )
        self.update_display_table()

        "Signals"
        self.ui.lineEdit_RootDirectory.textChanged.connect(self.root_dir_updated)
        self.ui.checkBox_CreatedToggle.checkStateChanged.connect(self.date_created_checkbox_updated)
        self.ui.checkBox_LastLoadedToggle.checkStateChanged.connect(self.date_last_loaded_checkbox_updated)

        self.ui.tableWidget_SearchResultsTable.cellClicked.connect(self.cell_was_clicked)

        self.ui.pushButton_LoadSession.clicked.connect(self.load_session_button_clicked)

        # Connect all input signals for every new input manager instance
        for widget in self.input_manager.widgets.values():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.search_params_updated)

            if isinstance(widget, QDateEdit):
                widget.dateChanged.connect(self.search_params_updated)

    """
    Dispatcher Functions ---------------------------------------------------------------------------------------------------
    """
    def root_dir_updated(self):
        print(self.filtered_results)
        root_dir = Path(self.ui.lineEdit_RootDirectory.text())
        if Path.is_dir(root_dir):
            self.data_dir = root_dir
            self.init_input_manager()
            self.search_manager = SearchManager(data_dir=self.data_dir)
            self.ui.tableWidget_SearchResultsTable.setRowCount(0)
            # self.update_display_table()



    def search_params_updated(self):
        self.input_manager.update_input_parameters(
            date_created_enabled=self.ui.checkBox_CreatedToggle.isChecked(),
            date_opened_enabled=self.ui.checkBox_LastLoadedToggle.isChecked()
        )
        self.filtered_results = self.search_manager.filter_search_results(self.input_manager.search_params)
        self.update_display_table()


    def date_created_checkbox_updated(self):
        self.search_params_updated()

        if self.ui.checkBox_CreatedToggle.isChecked():
            self.ui.dateEdit_Created.setEnabled(True)
        else:
            self.ui.dateEdit_Created.setEnabled(False)


    def date_last_loaded_checkbox_updated(self):
        self.search_params_updated()

        if self.ui.checkBox_LastLoadedToggle.isChecked():
            self.ui.dateEdit_LastModified.setEnabled(True)
        else:
            self.ui.dateEdit_LastModified.setEnabled(False)


    def cell_was_clicked(self, row, col):
        # Selected entry inside of table
        self.selected_entry = self.filtered_results[row]

        # Series dir belonging to selected entry
        selected_series_dir = self.selected_entry["series_dir"]
        # self.variable = self.selected_entry["variable"]

        # Populate series dir into line edit for verification
        self.ui.lineEdit_SeriesDirectory.setText(selected_series_dir)


    def load_session_button_clicked(self):
        self.init_file_manager(selected_entry=self.selected_entry)

        hash_log = FileManager.load_hash_log(self.data_dir)

        if self.file_manager.hash_str in hash_log:
            md_path = hash_log[self.file_manager.hash_str]["dataset_metadata_filepath"]
            self.file_manager.set_dataset_metadata_path(md_path)
        else:
            print(f"Warning: no metadata path for hash {self.file_manager.hash_str}")

        self.accept()




    """
    Update Environment Functions ---------------------------------------------------------------------------------------
    """
    def update_display_table(self):
        table = self.ui.tableWidget_SearchResultsTable

        # Clear all previous entries
        table.setRowCount(0)

        # Set number of rows
        table.setRowCount(len(self.filtered_results))

        for ind in range(len(self.filtered_results)):
            result = self.filtered_results[ind]

            table.setItem(ind, 0, QTableWidgetItem(result["custom_tag"]))
            table.setItem(ind, 1, QTableWidgetItem(result["hash"]))
            table.setItem(ind, 2, QTableWidgetItem(result["dataset"]))
            table.setItem(ind, 3, QTableWidgetItem(result["variable"]))
            table.setItem(ind, 4, QTableWidgetItem(f"({result['nx']}x{result['ny']}x{result['nz']})x{result['nt']}"))
            table.setItem(ind, 5, QTableWidgetItem(result["created"]))
            table.setItem(ind, 6, QTableWidgetItem(result["last_loaded"]))




    # def populate_data_directory(self):
        # if self.data_dir == "" or self.data_dir is None:
        #     current_root = Path.cwd().parent
        #     self.ui.lineEdit_RootDirectory.setText(str(current_root))
        #     self.data_dir = current_root
        # else:
        # if self.valid_data_dir(self.data_dir):
        #     self.ui.lineEdit_RootDirectory.setText(str(self.data_dir))
        #     self.input_manager.toggle_secondary_inputs(set_enable=True)
        # else:
        #     self.input_manager.toggle_secondary_inputs(set_enable=False)



    """
    Other Functions ----------------------------------------------------------------------------------------------------
    """

    def valid_data_dir(self, data_dir:Path):
        if data_dir.is_dir():
            return True
        else:
            return False


    def set_table_options(self, data):
        pass


    def get_session_data(self):
        pass


    def init_input_manager(self):
        self.input_manager = InputManager(
            lineEdit_RootDirectory=self.ui.lineEdit_RootDirectory,
            lineEdit_Name=self.ui.lineEdit_Name,
            lineEdit_Hash=self.ui.lineEdit_Hash,
            lineEdit_DatasetTitle=self.ui.lineEdit_DatasetTitle,
            lineEdit_Variable=self.ui.lineEdit_Variable,
            dateEdit_Created=self.ui.dateEdit_Created,
            dateEdit_LastModified=self.ui.dateEdit_LastModified,
            lineEdit_nx=self.ui.lineEdit_nx,
            lineEdit_ny=self.ui.lineEdit_ny,
            lineEdit_nz=self.ui.lineEdit_nz,
            lineEdit_nt=self.ui.lineEdit_nt
        )
    #

    def init_file_manager(self, selected_entry):
        configs = selected_entry["configs"]

        dataset_constraints = DatasetConstraints(configs["dataset_constraints"])
        query_method_config = QueryMethodConfig(configs["query_method_config"])
        grid_config = GridConfig(configs["grid_config"])

        try:
            self.file_manager = FileManager(
                variable=selected_entry["variable"],
                data_dir=self.data_dir,
                app_dir=self.app_dir,
                hash_str=selected_entry["hash"],
                dataset_constraints=dataset_constraints,
                query_method_config=query_method_config,
                grid_config=grid_config
            )
            self.file_manager.set_dataset_metadata_path(selected_entry["dataset_metadata_filepath"])
        except Exception as e:
            print(e)



class InputManager:
    def __init__(self, **kwargs):
        self.search_params = None
        self.widgets = {}
        for key, entry in kwargs.items():
            self.widgets[key] = entry

    def update_input_parameters(self, date_created_enabled, date_opened_enabled):

        search_params = {
            "data_dir" : self.widgets["lineEdit_RootDirectory"].text(),
            "hash": self.widgets["lineEdit_Hash"].text().lower(),
            "custom_tag": self.widgets["lineEdit_Name"].text().lower(),
            "dataset": self.widgets["lineEdit_DatasetTitle"].text().lower(),
            "variable": self.widgets["lineEdit_Variable"].text().lower(),
            "last_loaded": self.widgets["dateEdit_LastModified"].text(),
            "created": self.widgets["dateEdit_Created"].text(),
            "nx": self.widgets["lineEdit_nx"].text(),
            "ny": self.widgets["lineEdit_ny"].text(),
            "nz": self.widgets["lineEdit_nz"].text(),
            "nt": self.widgets["lineEdit_nt"].text()
        }

        if not date_created_enabled:
            search_params["created"] = ""

        if not date_opened_enabled:
            search_params["last_loaded"] = ""

        self.search_params = search_params

    # def toggle_secondary_inputs(self, set_enable=False):
    #     secondary_input_widgets = [
    #     self.widgets["lineEdit_Hash"],
    #     self.widgets["lineEdit_Name"],
    #     self.widgets["lineEdit_DatasetTitle"],
    #     self.widgets["lineEdit_Variable"],
    #     self.widgets["dateEdit_LastModified"],
    #     self.widgets["dateEdit_Created"],
    #     self.widgets["lineEdit_nx"],
    #     self.widgets["lineEdit_ny"],
    #     self.widgets["lineEdit_nz"],
    #     self.widgets["lineEdit_nt"]
    #     ]
    #
    #     for widget in secondary_input_widgets:
    #         widget.setEnabled(set_enable)


class SearchManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

        self.hash_log = FileManager.load_hash_log(self.data_dir)
        # self.get_hash_log()

        self.all_series_data = []
        self.format_search_results()



    def format_search_results(self):
        self.all_series_data = []
        for hash_ in self.hash_log.keys():

            series_data = self.hash_log[hash_]

            last_loaded_dict = series_data["last_loaded"]

            for variable, last_loaded in last_loaded_dict.items():

                data = {
                    "data_dir" : series_data["data_directory"],
                    "hash" : hash_,
                    "custom_tag" : series_data["custom_tag"].lower(),
                    "dataset" : series_data["dataset"].lower(),
                    "variable" : variable.lower(),
                    "last_loaded" : last_loaded,
                    "created" : series_data["created"],
                    "nx" : series_data["config"]["grid_config"]["nx"],
                    "ny" : series_data["config"]["grid_config"]["ny"],
                    "nz" : series_data["config"]["grid_config"]["nz"],
                    "nt" : series_data["config"]["grid_config"]["nt"],
                    "series_dir" : series_data["series_directory"],
                    "configs" : series_data["config"]
                }

                self.all_series_data.append(data)


    def filter_search_results(self, search_params=None):
        # search_params = {
        #     "hash": "", "custom_tag": "", "dataset": "", "variable": "", "last_loaded": "", "created": "", "nx": "",
        #     "ny": "", "nz": "", "nt": ""
        # }

        if search_params is None:
            return self.all_series_data

        elif all([v in (None, "") for v in search_params.values()]):
            return self.all_series_data

        else:
            df = pd.DataFrame(self.all_series_data)
            mask = pd.Series([True] * len(df))

            # String-based filters
            for key in ["hash", "custom_tag", "dataset", "variable", "last_loaded", "created"]:
                value = search_params.get(key)
                if value not in (None, ""):
                    mask &= df[key].astype(str).str.contains(value, na=False)

            # Numeric-based filters
            for key in ["nx", "ny", "nz", "nt"]:
                value = search_params.get(key)
                if value not in (None, ""):
                    try:
                        mask &= df[key] == int(value)
                    except ValueError:
                        mask &= df[key].astype(str).str.contains(value, na=False)

            return df[mask].to_dict(orient="records")








