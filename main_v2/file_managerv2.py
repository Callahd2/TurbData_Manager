from main_v2.query_manager  import *
import hashlib
import json
from datetime import datetime
from main_v2.supplementary_classes import State, RuntimeConfig
from pathlib import Path



class FileManager:
    def __init__(self, variable, data_dir, app_dir, hash_str, dataset_constraints, query_method_config, grid_config):


        self.data_dir = data_dir
        self.app_dir = app_dir
        self.hash_str = hash_str
        self.dataset_constraints = dataset_constraints
        self.query_method_config = query_method_config
        self.grid_config = grid_config

        self.variable = variable
        self.paths = None
        # self.hash_log_entry = FileManager.load_hash_log(root_dir)[self.hash_str]
        self.init_series_paths(variable)


    @property
    def selected_variable(self):
        return self.variable


    """
    New Manager Sequence -----------------------------------------------------------------------------------------------
    """

    @staticmethod
    def load_hash_log(data_dir: Path):
        hash_log_path = data_dir / "turb_data" / "hash_log.json"

        if hash_log_path.exists():
            try:
                with open(hash_log_path, "r") as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except (json.JSONDecodeError, OSError):
                return {}
        else:
            return {}


    @staticmethod
    def generate_hash(*static_configs):
        """
        Input:
                DatasetConstraints, QueryMethodConfig, and GridConfig objects
        Returns:
            A hash that is unique to the series based on all the configs
        """
        configs = {}
        for config in static_configs:
            if not isinstance(config, dict):
                config = config.__dict__

            for key in config.keys():
                configs[key] = config[key]

        config_str = json.dumps(configs, sort_keys=True, separators=(",", ":"))

        return hashlib.md5(config_str.encode()).hexdigest()


    @staticmethod
    def hash_exists(hash_curr, hash_log):
        for hash_ in hash_log.keys():
            if hash_curr == hash_:
                return True

        return False


    def init_series_paths(self, variable):
        self.paths = SeriesPaths(self.data_dir, self.hash_str, self.query_method_config, self.grid_config)
        self.paths.generate_variable_dependent_paths(self.hash_str, variable)
        # self.paths.files.dataset_metadata_path = self.hash_log_entry["dataset_metadata_filepath"]


    def set_custom_tag(self, custom_tag):
        self.custom_tag = custom_tag


    def set_dataset_metadata_path(self, dataset_metadata_path):
        self.paths.files.dataset_metadata_path = dataset_metadata_path


    def generate_directories(self):
        for directory in self.paths.dirs.__dict__.values():
            if isinstance(directory, str):
                Path(directory)

            Path.mkdir(directory, parents=True, exist_ok=True)


    def generate_files(self):
        # Instantiate json files for state, runtime_config, series_config
        series_configs = self.get_new_hash_log_entry()

        FileManager._write_new_json(path=self.paths.files.state_path, _dict=self.paths.blank_slates.state.to_dict())
        FileManager._write_new_json(path=self.paths.files.series_config_path, _dict=series_configs)

        if not self.paths.files.runtime_config_path.exists():
            FileManager._write_new_json(path=self.paths.files.runtime_config_path,
                                        _dict=RuntimeConfig().to_dict())


    def get_new_hash_log_entry(self):

        variable_status, last_loaded_status = self._format_status_fields()

        entry = {
            "volume_series": self.paths.series_filename,
            "dataset": self.query_method_config.dataset_title,
            "completed": variable_status,
            "created": datetime.now().strftime("%m/%d/%Y"),
            "last_loaded": last_loaded_status,
            "series_directory": str(self.paths.dirs.series_dir),
            "custom_tag": self.custom_tag,
            "data_directory": str(self.data_dir),
            "dataset_metadata_filepath":str(self.paths.files.dataset_metadata_path),
            "yvals_filepath": str(self.paths.files.yvals_path),
            "config": {
                "grid_config": self.grid_config.__dict__,
                "query_method_config": self.query_method_config.__dict__,
                "dataset_constraints": self.dataset_constraints.__dict__,
            }}

        return entry


    def _format_status_fields(self):
        variable_status = {}
        last_loaded_status = {}
        for variable in self.dataset_constraints.dataset_variables:
            variable_status[variable] = False
            last_loaded_status[variable] = ""

        return variable_status, last_loaded_status


    @staticmethod
    def _write_new_json(path:Path, _dict:dict):
        with open(path, "w") as f:
            json.dump(_dict, f, indent=4)

    @staticmethod
    def _read_from_json(path:Path):
        with open(path, "r") as f:
            return json.load(f)


    def init_files_for_all_variables(self):
        "Initialize directories and state.json for every dataset variable"
        for var in self.dataset_constraints.dataset_variables:
            self.paths.generate_variable_dependent_paths(self.hash_str, var)
            self.generate_directories()
            self.generate_files()


    def set_new_variable(self, new_var):
        self.variable = new_var

        self.paths.generate_variable_dependent_paths(self.hash_str, new_var)

        self.paths.generate_new_session_log_filename(new_var)





    """
    Load Manager Sequence
    """
    # @classmethod
    # def load_file_manager(cls, variable, root_dir, hash_str, dataset_constraints, query_method_config, grid_config):
    #     # Instantiate self
    #     self = cls(root_dir, hash_str, dataset_constraints, query_method_config, grid_config)
    #
    #     # Generate all relevant path objects
    #     self.init_series_paths(variable)
    #     self.variable = variable
    #
    #     return self



"""
Helper Classes ---------------------------------------------------------------------------------------------------------
"""

class Directories:
    def __init__(self):
        # Listed variables are listed for reference but compiled elsewhere
        self.series_var_dir = None
        self.variable_log_dir = None
        self.series_dir = None
        self.dataset_dir = None
        self.turb_data_dir = None
        self.data_dir = None

class Files:
    def __init__(self):
        # Listed variables are listed for reference but compiled elsewhere
        self.hash_log_path = None
        self.series_config_path = None
        self.runtime_config_path = None
        self.state_path = None
        self.current_log_path = None
        self.dataset_metadata_path = None
        self.yvals_path = None

class BlankSlates:
    def __init__(self):
        self.state = State()

class SeriesPaths:
    def __init__(self, data_dir, hash_str, qmc, gc):

        self.dirs = Directories()
        self.files = Files()
        self.blank_slates = BlankSlates()

        # Generate generic directories
        self.dirs.data_dir = data_dir
        self.hash_str = hash_str
        self.dirs.turb_data_dir = data_dir / "turb_data"
        self.dirs.dataset_dir = data_dir / "turb_data" / qmc.dataset_title
        self.series_filename = SeriesPaths.generate_series_filename(hash_str, qmc, gc)
        self.dirs.series_dir = data_dir / "turb_data" / qmc.dataset_title / self.series_filename

        self.files.hash_log_path = self.dirs.turb_data_dir / "hash_log.json"


    @staticmethod
    def generate_series_filename(hash_str, qmc, gc):
        series_filename = (
            f"{qmc.dataset_title}__"
            f"xs={gc.x_bounds[0]}_xe={gc.x_bounds[1]}_nx={gc.nx}__"
            f"ys={gc.y_bounds[0]}_ye={gc.y_bounds[1]}_ny={gc.ny}__"
            f"zs={gc.z_bounds[0]}_ze={gc.z_bounds[1]}_nz={gc.nz}__"
            f"ts={gc.t_bounds[0]}_te={gc.t_bounds[1]}_nt={gc.nt}__"
            f"hash={hash_str[:8]}")

        return series_filename


    def generate_variable_dependent_paths(self, hash_str:str, variable:str):
        self.dirs.series_var_dir = self.dirs.series_dir / variable
        self.dirs.variable_log_dir = self.dirs.series_var_dir / "logs"

        self.files.series_config_path = self.dirs.series_dir / f"series_configs__{hash_str[:8]}.json"
        self.files.runtime_config_path = self.dirs.turb_data_dir / "runtime_config.json"
        self.files.state_path = self.dirs.series_var_dir / f"state__{variable}_{hash_str[:8]}.json"


    def generate_new_session_log_filename(self, variable):
        dt_now = datetime.now().strftime("%m_%d_%Y__%H_%M_%S")
        self.files.current_log_path = self.dirs.variable_log_dir / f"session_log__{dt_now}__{variable}__{self.hash_str[:8]}"













