
# dataset_constraints, runtime_config, query_method_config, grid_config

from PyQt6.QtGui import QIntValidator, QDoubleValidator
from PyQt6.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QLabel
import json


# For now instantiate with dictionaries. Later, UI will directly instantiate attributes for config classes.
class DatasetConstraints:
    def __init__(self, dataset_constraints):
        self.min_dt = dataset_constraints["min_dt"]
        self.domain_x = dataset_constraints["domain_x"]
        self.domain_y = dataset_constraints["domain_y"]
        self.domain_z = dataset_constraints["domain_z"]
        self.domain_t = dataset_constraints["domain_t"]
        self.max_res_x = dataset_constraints["max_res_x"]
        self.max_res_y = dataset_constraints["max_res_y"]
        self.max_res_z = dataset_constraints["max_res_z"]
        self.dataset_variables = dataset_constraints["dataset_variables"]
        self.variable_components = dataset_constraints["variable_components"]

        # self.components = dataset_constraints.get("variable_components", {})
        print(self.variable_components)


class QueryMethodConfig:
    def __init__(self, query_method_config):
        self.dataset_title = query_method_config["dataset_title"]
        self.temporal_method = query_method_config["temporal_method"]
        self.spatial_method = query_method_config["spatial_method"]
        self.spatial_operator = query_method_config["spatial_operator"]
        # self.dataset_object = query_method_config["dataset_object"]

class GridConfig:
    def __init__(self, grid_config):
        self.nx = grid_config["nx"]
        self.ny = grid_config["ny"]
        self.nz = grid_config["nz"]
        self.nt = grid_config["nt"]
        self.t_bounds = grid_config["t_bounds"]
        self.x_bounds = grid_config["x_bounds"]
        self.y_bounds = grid_config["y_bounds"]
        self.z_bounds = grid_config["z_bounds"]




class State:
    def __init__(self):
        self.flags = Flags()

        self.flags.series_is_complete = False
        self.flags.snapshot_is_complete = False
        self.flags.is_last_chunk = False
        self.flags.is_first_chunk = True
        self.flags.is_last_snapshot = False
        self.flags.is_new_series = True

        self.resume_volume_index = 0
        self.current_query_limit = 4000
        self.query_history = []
        self.num_consecutive_fails = 0
        self.resume_temporal_index = 0

    def to_dict(self):
        def recurse(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, (list, tuple, set)):
                return [recurse(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: recurse(v) for k, v in obj.items()}
            elif hasattr(obj, "__dict__"):
                return {k: recurse(v) for k, v in vars(obj).items()}
            else:
                return str(obj)

        return recurse(self)


    @classmethod
    def load_from_json(cls, state_path):
        with open(state_path, "r") as f:
            state_dict = json.load(f)

        # Instantiate state object using dict loaded from json file
        self = cls()
        for key, val in state_dict.items():
            if key == "flags":
                for flag_name, flag_value in val.items():
                    setattr(self.flags, flag_name, flag_value)
            else:
                setattr(self, key, val)

        self.num_consecutive_fails = 0
        return self



class RuntimeConfig:

    class Tunable:
        def __init__(self):
            self.query_limit_range = [100, 4000]
            self.query_history_length = 10
            self.query_limit_update_factor = 0.3
            self.starting_query_limit = 4000

            self.wait_update_factor = 1.5
            self.wait_range = [1, 3600]
            self.wait_update_padding = 3

            self.max_consecutive_fails = 20

    class Absolute:
        def __init__(self):
            self.query_min_size_limits = [1, 3999999]
            self.query_max_size_limits = [2, 4000000]
            self.query_limit_update_factor_limits = [0.2, 0.6]
            self.query_history_length_limits = [3, 10]

            self.wait_max_limits = [2, 43200]
            self.wait_min_limits = [1, 42199]
            self.wait_update_padding_limits = [1, 5]
            self.wait_time_update_factor_limits = [1.5, 3]

            self.max_consecutive_fails_limits = [1, 100]

    def __init__(self):
        self.tunable = self.Tunable()
        self.absolute = self.Absolute()


    @classmethod
    def load_runtime_config(cls, runtime_config: dict):
        self = RuntimeConfig()
        for key, val in runtime_config["tunable"].items():
            setattr(self.tunable, key, val)

        for key, val in runtime_config["absolute"].items():
            setattr(self.absolute, key, val)

        return self


    def to_dict(self):
        def recurse(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, (list, tuple, set)):
                return [recurse(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: recurse(v) for k, v in obj.items()}
            elif hasattr(obj, "__dict__"):
                return {k: recurse(v) for k, v in vars(obj).items()}
            else:
                return str(obj)

        return recurse(self)


    """
    INPUT MANAGER ------------------------------------------------------------------------------------------------------
    """

class InputManager:
    def __init__(self, **kwargs):
        """
        Centralized input validation class

        Input: key= {
                    'widget':widget,
                    'type': 'int' | 'float' | 'combo' | 'path'
                    }
        """
        self._fields = {}

        for key, entry in kwargs.items():
            self._fields[key] = entry


    def attach_validators(self):
        "Attaches QValidator objects to widgets"
        for ent in self._fields.values():
            widget = ent["widget"]

            if isinstance(widget, QLabel):
                continue
            else:

                min_val, max_val = ent.get("min"), ent.get("max")
                type = ent.get("type")

                if ent["type"] == "int":
                    validator = QIntValidator(min_val, max_val, widget)
                    widget.setValidator(validator)

                if ent["type"] == "float":
                    validator = QDoubleValidator(min_val, max_val, ent.get("decimals", 4), widget)
                    validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                    widget.setValidator(validator)


    def force_within_range(self):
        "Auto corrects inputs to remain within range for QSpinBoxes, QDoubleSpinBoxes"
        for ent in self._fields.values():
            widget = ent["widget"]

            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                min_val, max_val = ent.get("min"), ent.get("max")
                curr_val = widget.value()

                if curr_val < min_val:
                    widget.setValue(min_val)
                if curr_val > max_val:
                    widget.setValue(max_val)


    def clear_inputs(self):
        for ent in self._fields.values():
            widget = ent["widget"]
            widget.clear()


    def validate_min_max(self, min_key, max_key, feedback_label=None, message="Min cannot exceed max."):
        "Ensures that min < max for a give pair of widgets"
        min_widget = self._fields[min_key]["widget"]
        max_widget = self._fields[max_key]["widget"]

        min_val, max_val = min_widget.value(), max_widget.value()

        if min_val > max_val:
            if feedback_label:
                feedback_label.setText(message)
            min_widget.setValue(max_val)
            return False
        if feedback_label:
            feedback_label.setText("")
        return True


    def all_fields_filled(self):
        "Generic check if all fields are filled"
        for ent in self._fields.values():
            widget = ent["widget"]
            # Check if line edit is empty
            if isinstance(widget, QLineEdit) and not widget.text().strip():
                return False
            # Check if combo bax has a valid selection. First index is always a placeholder entry
            if isinstance(widget, QComboBox) and widget.currentIndex() <= 0:
                return False
        return True


    def get_field_value(self, key):
        widget = self._fields[key]["widget"]
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        return None




class Flags:
    def __init__(self):
        pass

    def __str__(self):
        if self.__dict__:
            list = []
            for flag, state in self.__dict__.items():
                list.append(f"Flag: {flag}\tState: {state}")
            return list
        else:
            return "Flags object is empty"


class Helper:
    @staticmethod
    def to_dict(object):
        def recurse(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, (list, tuple, set)):
                return [recurse(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: recurse(v) for k, v in obj.items()}
            elif hasattr(obj, "__dict__"):
                return {k: recurse(v) for k, v in vars(obj).items()}
            else:
                return str(obj)

        return recurse(object)

