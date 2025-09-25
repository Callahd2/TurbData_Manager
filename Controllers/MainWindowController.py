
from ui.MainWindow_v9 import Ui_MainWindow
from PyQt6.QtWidgets import QMainWindow, QDialog, QApplication, QMenu, QDoubleSpinBox, QSpinBox, QLineEdit
from PyQt6.QtCore import QSettings, QThread, pyqtSlot, QTimer
import sys
import traceback
import qdarkstyle
import json
import time

from NewSessionDialog import NewSessionDialog
from LoadSessionDialog import LoadSessionDialog
from main_v2.query_manager import QueryManager


from main_v2.supplementary_classes import RuntimeConfig, InputManager, Flags, State



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        "Settings"
        self.settings = QSettings("PythonProjects","QueryApp")
        self.data_dir = self.settings.value("data_directory","")
        self.auth_token = self.settings.value("auth_token", "")
        self.ui.AuthTokenInputLineEdit.setText(self.auth_token)

        # Start app in dark mode
        QApplication.instance().setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt6"))
        self.ui.actionEnable_Dark_Mode.setChecked(True)

        # Hide dock widgets
        self.ui.AdvancedControlPanelDockWidget.hide()
        self.ui.SessionLogDockWidget.hide()
        self.ui.SessionMetricsDockWidget.hide()
        self.default_dock_layout = self.saveState()

        "FILE tab action"
        self.ui.actionNew_Session.triggered.connect(self.open_new_session_dialog)
        self.ui.actionOpen_Session.triggered.connect(self.open_load_session_dialog)

        self.ui.actionSave_Session.triggered.connect(self.save_session)

        self.ui.actionExit.triggered.connect(self.close_session)

        "VIEW tab action signals" # Also syncs input
        self.ui.actionAdvanced_Control_Panel.toggled.connect(self.ui.AdvancedControlPanelDockWidget.setVisible)
        self.ui.AdvancedControlPanelDockWidget.visibilityChanged.connect(self.ui.actionAdvanced_Control_Panel.setChecked)
        self.ui.actionSession_Log.toggled.connect(self.ui.SessionLogDockWidget.setVisible)
        self.ui.SessionLogDockWidget.visibilityChanged.connect(self.ui.actionSession_Log.setChecked)
        self.ui.actionSession_Metrics.toggled.connect(self.ui.SessionMetricsDockWidget.setVisible)
        self.ui.SessionMetricsDockWidget.visibilityChanged.connect(self.ui.actionSession_Metrics.setChecked)
        self.ui.actionEnable_Dark_Mode.toggled.connect(self.toggle_dark_stylesheet)

        # Restore dock layout to default
        self.ui.actionRestore_Layout.triggered.connect(self.restore_dock_layout)

        "Connect start button signal"
        self.ui.StartQueryPushButton.clicked.connect(self.start_session)

        "Connect pause button signal"
        self.ui.StopQueryPushButton.clicked.connect(self.pause_session)

        "Create class to allow togglability for fields dependent on query active state"
        self.field_manager = FieldActivityManager(
            AuthTokenInputLineEdit=self.ui.AuthTokenInputLineEdit,
            StartingQueryValueInputSpinBox = self.ui.StartingQueryValueInputSpinBox,

            StopQueryPushButton=self.ui.StopQueryPushButton,
            StartQueryPushButton=self.ui.StartQueryPushButton,

            actionSave_Session=self.ui.actionSave_Session,
            actionOpen_Session=self.ui.actionOpen_Session,
            actionNew_Session=self.ui.actionNew_Session,
            actionChange_Variable=self.ui.actionChange_Variable,

            MaxQueryLimitSpinBox=self.ui.MaxQueryLimitSpinBox,
            MinQueryLimitSpinBox=self.ui.MinQueryLimitSpinBox,
            QueryLimitUpdateFactorSpinBox=self.ui.QueryLimitUpdateFactorSpinBox,
            QueryLimitUpdateFactorSlider=self.ui.QueryLimitUpdateFactorSlider,
            QueryHistoryLengthSpinBox=self.ui.QueryHistoryLengthSpinBox,
            QueryHistoryLengthSlider=self.ui.QueryHistoryLengthSlider,

            MaxWaitDoubleSpinBox=self.ui.MaxWaitDoubleSpinBox,
            MinWaitDoubleSpinBox=self.ui.MinWaitDoubleSpinBox,
            WaitUpdateFactorSpinBox=self.ui.WaitUpdateFactorSpinBox,
            WaitUpdateFactorSlider=self.ui.WaitUpdateFactorSlider,
            waitUpdatePaddingSpinbox=self.ui.waitUpdatePaddingSpinbox,

            MaxConsecutiveFailsSpinBox=self.ui.MaxConsecutiveFailsSpinBox,
            MaxConsecutiveFailsSlider=self.ui.MaxConsecutiveFailsSlider,

            resetSettingsPushbutton=self.ui.resetSettingsPushbutton
        )


        self._update_session_grid_labels(clear=True)
        self._update_dataset_grid_labels(clear=True)

        "Force beginning state of specific widgets"
        # Disable until a session is loaded
        self.ui.actionSave_Session.setEnabled(False)
        self.ui.StartQueryPushButton.setEnabled(False)
        self.ui.actionChange_Variable.setEnabled(False)
        self.ui.SeriesProgressBar.setMaximum(0)
        self.ui.SnapshotProgressBar.setMaximum(0)

        "Instantiate flag field and set starting flags"
        self.flags = Flags()
        self.flags.session_is_loaded = False
        self.flags.session_ever_started = False

        "Initialized here but compiled elsewhere"
        self.runtime_config = None
        # self.auth_token = None
        self.variable = None
        self._qthread = None
        self._worker = None

    @property
    def auth_token_used(self):
        return self.auth_token

    @property
    def selected_variable(self):
        return self.variable

    """
    Signal dispatcher functions ----------------------------------------------------------------------------------------
    """
    def _input_field_changed(self):
        self.input_manager.force_within_range()

        abs = self.runtime_config.absolute
        self.refresh_input_manager_limits()
        self.input_manager.force_within_range()
        errors = self.input_manager.validate_advanced_panel(abs)

        self.update_tunable_settings()
        tune = self.runtime_config.tunable

        self.__set_central_widget_values(tune)



    """
    FILE tab dispatcher functions --------------------------------------------------------------------------------------
    """
    def open_new_session_dialog(self):
        dialog = NewSessionDialog()

        # If user closes window by completion then:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 1. Pass file_manager to main window
            self.file_manager = dialog.file_manager

            selected_var = self.file_manager.selected_variable
            print(selected_var)

            # 2. Load data to main window
            self.load_session()


    def open_load_session_dialog(self):
        dialog = LoadSessionDialog()

        # If user closes window by completion then:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 1. Pass file_manager to main window
            self.file_manager = dialog.file_manager

            selected_var = self.file_manager.selected_variable
            print(selected_var)

            # 2. Load data to mai
            self.load_session()

    """
    VIEW tab dispatcher functions --------------------------------------------------------------------------------------
    """
    def restore_dock_layout(self):
        self.restoreState(self.default_dock_layout)


    def toggle_dark_stylesheet(self):
        if self.ui.actionEnable_Dark_Mode.isChecked():
            QApplication.instance().setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt6"))
        else:
            QApplication.instance().setStyleSheet("")

    """
    CENTRAL WIDGET dispatcher functions --------------------------------------------------------------------------------
    """
    def start_button_pressed(self):
        try:
            self.start_session()
        except Exception as e:
            print(e)


    def pause_session(self):

        # add logic here that waits until whatever query event that's active has successfully stopped until toggling widgets

        self.field_manager.toggle_fields(query_is_active=False)


    """
    --------------------------------------------------------------------------------------------------------------------
    ---------------------------------------- START QUERYING sequence ---------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def start_session(self):
        print("Starting session")
        # 1. Lock UI controls while active
        self.field_manager.toggle_fields(query_is_active=True)

        self.auth_token = self.ui.AuthTokenInputLineEdit.text()

        self.update_tunable_settings()

        self._qthread = QThread(self)
        self._worker = QueryManager(
            file_manager=self.file_manager,
            runtime_config=self.runtime_config,
            auth_token=self.auth_token_used,
            variable=self.selected_variable
        )

        self._worker.moveToThread(self._qthread)

        self._worker.status.connect(self._on_status)
        self._worker.error.connect(self._on_error)
        self._worker.spatialProgress.connect(self._on_spatial_progress)
        self._worker.temporalProgress.connect(self._on_temporal_progress)
        self._worker.chunkSaved.connect(self._on_chunk_saved)
        self._worker.snapshotComplete.connect(self._on_snapshot_complete)
        self._worker.seriesComplete.connect(self._on_series_complete)

        self._worker.seriesComplete.connect(self._qthread.quit)
        self._qthread.finished.connect(self._worker.deleteLater)
        self._qthread.finished.connect(self._clear_worker_refs)

        self._qthread.started.connect(self._worker.start)

        self._qthread.start()

        self.save_session(session_ever_started=True)


    """
    --------------------------------------------------------------------------------------------------------------------
    ---------------------------------------- PAUSE QUERYING sequence ---------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def pause_session(self):
        if not self._worker:
            return
        if not self._worker.flags.paused:
            self._worker.pause()
            self.field_manager.toggle_fields(query_is_active=False)
            self._on_status("Paused")
            print("Pausing Session")
        else:
            self._worker.resume()
            self.field_manager.toggle_fields(query_is_active=True)
            self._on_status("Resumed")



    """
    --------------------------------------------------------------------------------------------------------------------
    ---------------------------------------- SAVE session sequence -----------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def save_session(self, session_ever_started):
        self._save_runtime_config()
        self._save_auth_token(session_ever_started)

        print("Session was saved")


    def _save_runtime_config(self):
        "Saves runtime config back to runtime_config.json"

        # get runtime configs as a dict and its path
        rtc_dict = self.runtime_config.to_dict()
        rtc_path = self.file_manager.paths.files.runtime_config_path

        with open(rtc_path, "w") as f:
            json.dump(rtc_dict, f, indent=4)


    def _save_auth_token(self, session_ever_started):
        if session_ever_started:
            self.settings.setValue("auth_token", self.auth_token)



    """
    --------------------------------------------------------------------------------------------------------------------
    ---------------------------------------- LOAD session sequence -----------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def load_session(self):

        # Update UI : FileManager contains much of the session initialization data
        self._update_signature_display(self.file_manager)
        self._update_session_grid_labels()

        # Load file containing display values
        metadata_path = self.file_manager.paths.files.dataset_metadata_path
        self._load_dataset_metadata(metadata_path)
        self._update_dataset_grid_labels()

        # Add 'change_variable' options to menu bar
        self._setup_variable_menu()

        # Load and fill most recent runtime settings from runtime config file
        self.runtime_config = self._load_runtime_config()
        self._update_runtime_settings()

        # Instantiate validators and input manager
        self.init_input_manager()
        self.variable = self.file_manager.selected_variable

        # Enable relevant fields
        self.ui.actionSave_Session.setEnabled(True)
        self.ui.StartQueryPushButton.setEnabled(True)
        self.ui.actionChange_Variable.setEnabled(True)

        # Update progress bar from state
        self._update_progress_bar()

        # Set relevant flags
        self.flags.session_is_loaded = True


        "All input field signals"
        for ent in self.input_manager._fields.values():
            widget = ent["widget"]
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._input_field_changed)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._input_field_changed)

    """
    1. Update UI labels on central widget
    """

    def _update_signature_display(self, file_manager):
        "Updates root directory, series directory, and series hash labels on main window."
        self.ui.RootDirectoryDisplayLabel.setText(str(file_manager.data_dir / "turb_data"))
        self.ui.SeriesDirectoryDisplayLabel.setText(str(file_manager.paths.dirs.series_dir))
        self.ui.SeriesHashDisplayLabel.setText(file_manager.hash_str)


    def _update_session_grid_labels(self, clear=False):
        "Updates main window to display user-selected grid and query configs"
        if clear:
            self.ui.DatasetTitleSelectionDisplayLabel.clear()
            self.ui.DatasetVariableSelectionDisplayLabel.clear()
            self.ui.DatasetSpatialMethodDisplayLabel.clear()
            self.ui.DatasetSpatialOperatorDisplayWidget.clear()
            self.ui.DatasetTemporalDisplayLabel.clear()
            self.ui.SpatialResolutionDisplayLabel.clear()
            self.ui.BoundsXDisplayLabel.clear()
            self.ui.BoundsYDisplayLabel.clear()
            self.ui.BoundsZDisplayLabel.clear()
            self.ui.BoundsTDisplayLabel.clear()

        else:
            fm = self.file_manager
            fm.qmc = self.file_manager.query_method_config
            fm.gc = self.file_manager.grid_config
            # md = self.metadata

            self.ui.DatasetTitleSelectionDisplayLabel.setText(fm.qmc.dataset_title)
            self.ui.DatasetVariableSelectionDisplayLabel.setText(fm.variable)
            self.ui.DatasetSpatialMethodDisplayLabel.setText(fm.qmc.spatial_method)
            self.ui.DatasetSpatialOperatorDisplayWidget.setText(fm.qmc.spatial_operator)
            self.ui.DatasetTemporalDisplayLabel.setText(fm.qmc.temporal_method)
            self.ui.SpatialResolutionDisplayLabel.setText(f"({fm.gc.nx}, {fm.gc.ny}, {fm.gc.nz}, {fm.gc.nt})")
            self.ui.BoundsXDisplayLabel.setText(f"[{fm.gc.x_bounds[0]}, {fm.gc.x_bounds[1]}]")
            self.ui.BoundsYDisplayLabel.setText(f"[{fm.gc.y_bounds[0]}, {fm.gc.y_bounds[1]}]")
            self.ui.BoundsZDisplayLabel.setText(f"[{fm.gc.z_bounds[0]}, {fm.gc.z_bounds[1]}]")
            self.ui.BoundsTDisplayLabel.setText(f"[{fm.gc.t_bounds[0]}, {fm.gc.t_bounds[1]}]")


    def _load_dataset_metadata(self, path):
        """Loads directly from config json file that contains absolute grid data of selected dataset.
        Contains pre-formatted labels for display"""
        with open(path, "r") as f:
            self.dataset_metadata = json.load(f)


    def _update_dataset_grid_labels(self, clear=False):
        "Updates dataset metadata onto main window"
        if clear:
            self.ui.DatasetNodesDisplayLabel.clear()
            self.ui.DatasetMinDtDisplayLabel.clear()
            self.ui.DatasetDomainXDisplayLabel.clear()
            self.ui.DatasetDomainYDisplayLabel.clear()
            self.ui.DatasetDomainZDisplayLabel.clear()
            self.ui.DatasetDomainTDisplayLabel.clear()
        else:
            md = self.dataset_metadata["display"]

            self.ui.DatasetNodesDisplayLabel.setText(
                f"({md['nodes_x']}, {md['nodes_y']}, {md['nodes_z']}, {md['nodes_t']})")
            self.ui.DatasetMinDtDisplayLabel.setText(md["min_dt"])
            self.ui.DatasetDomainXDisplayLabel.setText(f"[{md['start_x']}, {md['end_x']}]")
            self.ui.DatasetDomainYDisplayLabel.setText(f"[{md['start_y']}, {md['end_y']}]")
            self.ui.DatasetDomainZDisplayLabel.setText(f"[{md['start_z']}, {md['end_z']}]")
            self.ui.DatasetDomainTDisplayLabel.setText(f"[{md['start_t']}, {md['end_t']}]")


    def _update_progress_bar(self):
        state_path = self.file_manager.paths.files.state_path
        state = State.load_from_json(state_path=state_path)

        current_time_ind = state.resume_temporal_index
        total_time_ind = self.file_manager.grid_config.nt

        current_space_ind = state.resume_volume_index
        total_space_ind = self.file_manager.grid_config.nx * self.file_manager.grid_config.ny * self.file_manager.grid_config.nz

        self.ui.SnapshotProgressBar.setMaximum(total_space_ind)
        self.ui.SnapshotProgressBar.setValue(current_space_ind)
        self.ui.SeriesProgressBar.setMaximum(total_time_ind)
        self.ui.SeriesProgressBar.setValue(current_time_ind)

        if state.flags.series_is_complete:
            self.ui.SnapshotProgressBar.setValue(total_space_ind)
            self.ui.SeriesProgressBar.setValue(total_time_ind)
            self.ui.StartQueryPushButton.setEnabled(False)


    """
    2. Update navigation widgets
    """
    def _setup_variable_menu(self):
        "Creates a sub-menu with all dataset variables into the 'change variable' action in central menu"
        # Create sub-menu for variable selections
        variable_menu = QMenu("Change Variable", self)

        for var in self.file_manager.dataset_constraints.dataset_variables:
            action = variable_menu.addAction(var.capitalize())
            action.triggered.connect(lambda checked=False, v=var: self.__handle_variable_change(v))

        self.ui.actionChange_Variable.setMenu(variable_menu)

    # Helper function for '_setup_variable_menu'
    def __handle_variable_change(self, variable:str):
        "Updates file_manager 'variable' property and display for new variable"
        self.file_manager.set_new_variable(variable)
        self._update_session_grid_labels()
        self._update_signature_display(self.file_manager)
        self.runtime_config = self._load_runtime_config()



    """
    3. Load RuntimeConfig
    """
    # Runtime config is a class object that contains the live runtime-settings. It is saved to 'runtime_config.json'
    # and is saved every time a session starts. It is used to load the last-used runtime settings when a session
    # is loaded. Default runtime settings are loaded during the first-ever session from a user.

    def _load_runtime_config(self):
        "Load the actual RuntimeConfig object"
        rt_config_path = self.file_manager.paths.files.runtime_config_path
        with open(rt_config_path, "r") as f:
            rt_config = json.load(f)

        return RuntimeConfig.load_runtime_config(rt_config)


    """
    4. Update session with runtime settings
    """

    def _update_runtime_settings(self):
        "Launches a sequence to update widgets on the advanced control panel dock widget and the central widget"

        tune = self.runtime_config.tunable # condensed variable containing the MUTABLE parameters for querying behavior
        abs = self.runtime_config.absolute # condensed variable containing the IMMUTABLE parameters for querying behavior

        # a. Update values within the advance control panel
        self.__set_advanced_control_panel_values(abs, tune)

        # b. Update values within central widget
        self.__set_central_widget_values(tune)

        # c. Connect the reset-settings button
        self.ui.resetSettingsPushbutton.clicked.connect(self.__reset_runtime_settings)


    def __reset_runtime_settings(self):
        "Resets runtime settings to default when reset button is pressed"
        self.runtime_config = RuntimeConfig()
        self._update_runtime_settings()


    def __set_advanced_control_panel_values(self, abs, tune):
        "Sets absolute limits to widgets in Advanced Control Panel"
        # Query size settings
        self.ui.MinQueryLimitSpinBox.setRange(*abs.query_min_size_limits)
        self.ui.MaxQueryLimitSpinBox.setRange(*abs.query_max_size_limits)

        self.ui.MinQueryLimitSpinBox.setValue(tune.query_limit_range[0])
        self.ui.MaxQueryLimitSpinBox.setValue(tune.query_limit_range[1])

        self.___bind_spinbox_slider(
            spinbox=self.ui.QueryLimitUpdateFactorSpinBox,
            slider=self.ui.QueryLimitUpdateFactorSlider,
            min_val=abs.query_limit_update_factor_limits[0],
            max_val=abs.query_limit_update_factor_limits[1],
            step=0.01, decimals=2,
            initial=tune.query_limit_update_factor
        )
        self.___bind_spinbox_slider(
            spinbox=self.ui.QueryHistoryLengthSpinBox,
            slider=self.ui.QueryHistoryLengthSlider,
            min_val=abs.query_history_length_limits[0],
            max_val=abs.query_history_length_limits[1],
            step=1, decimals=0,
            initial=tune.query_history_length
        )

        # Wait settings
        self.ui.MaxWaitDoubleSpinBox.setRange(*abs.wait_max_limits)
        self.ui.MinWaitDoubleSpinBox.setRange(*abs.wait_min_limits)

        self.ui.MaxWaitDoubleSpinBox.setValue(tune.wait_range[1])
        self.ui.MinWaitDoubleSpinBox.setValue(tune.wait_range[0])

        self.ui.waitUpdatePaddingSpinbox.setRange(*abs.wait_update_padding_limits)

        self.ui.waitUpdatePaddingSpinbox.setValue(tune.wait_update_padding)

        self.___bind_spinbox_slider(
            spinbox=self.ui.WaitUpdateFactorSpinBox,
            slider=self.ui.WaitUpdateFactorSlider,
            min_val=abs.wait_time_update_factor_limits[0],
            max_val=abs.wait_time_update_factor_limits[1],
            step=0.01, decimals=2,
            initial=tune.query_limit_update_factor
        )

        self.___bind_spinbox_slider(
            spinbox=self.ui.MaxConsecutiveFailsSpinBox,
            slider=self.ui.MaxConsecutiveFailsSlider,
            min_val=abs.max_consecutive_fails_limits[0],
            max_val=abs.max_consecutive_fails_limits[1],
            step=1, decimals=0,
            initial=tune.max_consecutive_fails
        )

        # Sync range spin boxes with starting query limit spin box limits
        self.ui.MaxQueryLimitSpinBox.valueChanged.connect(
            lambda v: self.ui.StartingQueryValueInputSpinBox.setMaximum(v)
        )
        self.ui.MinQueryLimitSpinBox.valueChanged.connect(
            lambda v: self.ui.StartingQueryValueInputSpinBox.setMinimum(v)
        )

        self.ui.StartingQueryValueInputSpinBox.setRange(
            self.ui.MinQueryLimitSpinBox.value(), self.ui.MaxQueryLimitSpinBox.value()
        )


    # Helper function to '__set_advanced_control_panel_values' and '__set_central_widget_values'
    def ___bind_spinbox_slider(self, spinbox, slider, min_val, max_val, step=0.1, decimals=2, initial=None):
        """
        Sync QDoubleSpinBox and QSlider to match values and ranges.

        spinbox : QDoubleSpinBox
            spinbox widget
        slider : QSlider
            slider widget
        min_val, max_val : float
            range of values
        step : float
            step size for the spinbox
        decimals : int
            number of decimals to show in spinbox
        initial : float | int
            optional initial value for both widgets
        """
        scale = 1 / step

        # Configure spin box
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)

        if isinstance(spinbox, QDoubleSpinBox):
            spinbox.setDecimals(decimals)

        # Configure slider
        slider.setRange(int(min_val * scale), int(max_val * scale))

        # Sync both ways
        spinbox.valueChanged.connect(lambda v: slider.setValue(int(v * scale)))

        if isinstance(spinbox, QSpinBox):
            slider.valueChanged.connect(lambda v: spinbox.setValue(int(v / scale)))
        else:
            slider.valueChanged.connect(lambda v: spinbox.setValue(v / scale))

        # Optional: Set initial value
        if initial is not None:
            spinbox.setValue(initial)
            slider.setValue(int(initial * scale))


    # Helper function to '__set_central_widget_values'
    def _bind_spinbox_label(self, label, spinbox_min, spinbox_max, fmt="[{}, {}]"):
        "Binds a label to always display the range set by two spinboxes."
        def update_label():
            label.setText(fmt.format(spinbox_min.value(), spinbox_max.value()))
        spinbox_min.valueChanged.connect(lambda _: update_label())
        spinbox_max.valueChanged.connect(lambda _: update_label())
        update_label()


    def __set_central_widget_values(self, tune):
        "Sets all controller widgets in the advanced control panel dock widget"
        self._bind_spinbox_label(
            label=self.ui.QueryLimitsValues,
            spinbox_min=self.ui.MinQueryLimitSpinBox,
            spinbox_max=self.ui.MaxQueryLimitSpinBox,
        )
        # self.ui.StartingQueryValueInputSpinBox.setRange(*tune.query_limit_range)
        self.ui.StartingQueryValueInputSpinBox.setRange(
            self.ui.MinQueryLimitSpinBox.value(), self.ui.MaxQueryLimitSpinBox.value()
        )

        self.ui.StartingQueryValueInputSpinBox.setValue(tune.starting_query_limit)


    def set_remaining_signals(self):

        self.ui.AuthTokenInputLineEdit.textChanged.connect(lambda v: setattr(self, "auth_token", v))



    """
    5. Initialize input manager for the central widget
    """
    # The input manager sets forces valid inputs into all input fields

    def init_input_manager(self):
        "Sets up a MainWindowInputManager specialized class of InputManager from 'supplementary_classes.py'"
        tune = self.runtime_config.tunable
        abs = self.runtime_config.absolute

        self.input_manager = MainWindowInputManager(
            starting_query_size= {"widget":self.ui.StartingQueryValueInputSpinBox,
                                  "type":"int", "min":tune.query_limit_range[0], "max":tune.query_limit_range[1]},
            query_max={"widget":self.ui.MaxQueryLimitSpinBox,
                       "type":"int", "min":abs.query_max_size_limits[0], "max":abs.query_max_size_limits[1]},
            query_min={"widget":self.ui.MinQueryLimitSpinBox,
                       "type":"int", "min":abs.query_min_size_limits[0], "max":abs.query_min_size_limits[1]},
            query_update_factor={"widget":self.ui.QueryLimitUpdateFactorSpinBox,
                                 "type":"float", "min":abs.query_limit_update_factor_limits[0], "max":abs.query_limit_update_factor_limits[1]},
            query_history_length={"widget":self.ui.QueryHistoryLengthSpinBox,
                                  "type":"int", "min":abs.query_history_length_limits[0], "max":abs.query_history_length_limits[1]},
            wait_max={"widget":self.ui.MaxWaitDoubleSpinBox,
                      "type":"int", "min":abs.wait_max_limits[0], "max":abs.wait_max_limits[1]},
            wait_min={"widget":self.ui.MinWaitDoubleSpinBox,
                      "type":"int", "min":abs.wait_min_limits[0], "max":abs.wait_min_limits[1]},
            wait_padding={"widget":self.ui.waitUpdatePaddingSpinbox,
                          "type":"int", "min":abs.wait_update_padding_limits[0], "max":abs.wait_update_padding_limits[1]},
            wait_update_factor={"widget":self.ui.WaitUpdateFactorSpinBox,
                                "type":"float", "min":abs.wait_time_update_factor_limits[0], "max":abs.wait_time_update_factor_limits[1]},
            max_consecutive_fails={"widget":self.ui.MaxConsecutiveFailsSpinBox,
                                   "type":"int", "min":abs.max_consecutive_fails_limits[0], "max":abs.max_consecutive_fails_limits[1]},
            auth_token= {"widget":self.ui.AuthTokenInputLineEdit, "type":"lineEdit"},
        )

    """
    --------------------------------------------------------------------------------------------------------------------
    ---------------------------------------- CLOSE session sequence ----------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def close_session(self):

        # save session, then close session
        if self.flags.session_is_loaded:
            self.save_session()
        self.close()



    """
    --------------------------------------------------------------------------------------------------------------------
    ------------------------------------- Utility functions for live inputs --------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """

    def update_tunable_settings(self):
        """
        Updates the mutable settings commonly referred to as 'tune.' This records the live state of all mutable settings
        """

        self.runtime_config.tunable.query_limit_range = (self.ui.MinQueryLimitSpinBox.value(), self.ui.MaxQueryLimitSpinBox.value())
        self.runtime_config.tunable.query_history_length = self.ui.QueryHistoryLengthSpinBox.value()
        self.runtime_config.tunable.query_limit_update_factor = self.ui.QueryLimitUpdateFactorSpinBox.value()
        self.runtime_config.tunable.starting_query_limit = self.ui.StartingQueryValueInputSpinBox.value()
        self.runtime_config.tunable.wait_update_factor = self.ui.WaitUpdateFactorSpinBox.value()
        self.runtime_config.tunable.wait_range = [self.ui.MinWaitDoubleSpinBox.value(), self.ui.MaxWaitDoubleSpinBox.value()]
        self.runtime_config.tunable.wait_update_padding = self.ui.waitUpdatePaddingSpinbox.value()
        self.runtime_config.tunable.max_consecutive_fails = self.ui.MaxConsecutiveFailsSpinBox.value()


    def refresh_input_manager_limits(self):
        "Ensures that when a min/max range is updated, it is also tracked by the input manager"
        self.input_manager._fields["starting_query_size"]["min"]= self.ui.MinQueryLimitSpinBox.value()
        self.input_manager._fields["starting_query_size"]["max"] = self.ui.MaxQueryLimitSpinBox.value()


    @pyqtSlot(str)
    def _on_status(self, msg:str):
        self.ui.StatusValueLabel.setText(msg)
        self.ui.StatusTimerLabel.clear()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.__update_timer_label)
        self.count = 0
        self.timer.start(1000)

    def __update_timer_label(self):
        self.count += 1
        _time = time.strftime("%H:%M:%S", time.gmtime(self.count))
        self.ui.StatusTimerLabel.setText(_time)



    @pyqtSlot(str)
    def _on_error(self, msg:str):
        print(msg, file=sys.stderr, flush=True)
        self._on_status(msg)
        self.field_manager.toggle_fields(query_is_active=False)

    @pyqtSlot(int, int)
    def _on_spatial_progress(self, done:int, total:int):
        self.ui.SnapshotProgressBar.setMaximum(total)
        self.ui.SnapshotProgressBar.setValue(done)

    @pyqtSlot(int, int)
    def _on_temporal_progress(self, done:int, total:int):
        self.ui.SeriesProgressBar.setMaximum(total)
        self.ui.SeriesProgressBar.setValue(done)

    @pyqtSlot(tuple)
    def _on_chunk_saved(self, indices:tuple):
        pass

    @pyqtSlot(int)
    def _on_snapshot_complete(self, t_index:int):
        pass

    @pyqtSlot()
    def _on_series_complete(self):
        self._on_status("Series complete.")
        self.field_manager.toggle_fields(query_is_active=False)

    def _clear_worker_refs(self):
        self._worker = None
        self._qthread = None


class MainWindowInputManager(InputManager):
    def __init__(self, **fields):
        """
        Keys used: query_max, query_min, query_update_factor, query_history_length,
        wait_max, wait_min, wait_padding, wait_update_factor, max_consecutive_fails
        """
        super().__init__(**fields)

    def validate_advanced_panel(self, abs):
        """
        abs: RuntimeConfig.Absolute settings already set on widgets
        Returns a list of error messages
        """
        errors = []

        # Validate that min/max input pairs are valid
        if not self.validate_min_max("query_min", "query_max"):
            errors.append("Invalid query limit range.")
        if not self.validate_min_max("wait_min", "wait_max"):
            errors.append("Invalid wait limit range.")

        # Auto-correct by rounding to nearest limit
        self.force_within_range()

        return errors



class FieldActivityManager:
    "Disabled/Enables appropriate fields in UI based on if query is active/inactive"
    def __init__(self, **kwargs):
        self._fields = {}
        for key, qobject in kwargs.items():
            self._fields[key] = qobject

        self._query_is_active = False


    def toggle_fields(self, query_is_active: bool):
        self._query_is_active = query_is_active
        for field in self._fields.values():
            field.setEnabled(not field.isEnabled())


def excepthook(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)



def main():
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt6"))

    main_window = MainWindow()# Instantiate main window object

    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()