from givernylocal.turbulence_toolkit import *
from main_v2.supplementary_classes import *
from main_v2.query_set_exceptions import *
import json
import h5py
from pathlib import *
from main_v2.timing_helpers import *


class Grid:
    def __init__(self):
        pass

class Flags:
    def __init__(self):
        pass


class QuerySession:
    def __init__(self, dataset_constraints, query_method_config, grid_config, runtime_config, state, variable,
                 auth_token, hash_str):

        self.dataset_constraints = dataset_constraints
        self.query_method_config = query_method_config
        self.grid_config = grid_config
        self.runtime_config = runtime_config
        self.state = state
        self.variable = variable
        self.auth_token = auth_token
        self.hash_str = hash_str

        self.grid = Grid()
        self.flags = Flags()

        self.grid.num_spatial_points = self.grid_config.nx * self.grid_config.ny * self.grid_config.nz
        self.grid.points = self.init_points()
        self.grid.time_vector = self.init_time_vector()
        self.variable_dims = self.dataset_constraints.variable_components[self.variable]
        print(self.grid.num_spatial_points)

        n = self.runtime_config.tunable.query_history_length
        self.state.query_history = [0] * n

        self.snapshot_h5_path = None
        self.snapshot_indices = None


    """
    --------------------------------------------------------------------------------------------------------------------
    -------------------------------------- STARTING A NEW SESSION Sequence ---------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """

    def init_points(self):
        """
        Initializes a 3D grid of spatial query points based on user-defined bounds and resolution.
        Validate spatial domain coverage and grid density against dataset limits.

        :return: self.points -> np.ndarray of shape (N, 3)
        :raises: SpatialResolutionError
        """

        # self.log.debug("Validating spatial bounds")
        invalid_x_bounds = (self.grid_config.x_bounds[0] < self.dataset_constraints.domain_x[0] or
                            self.grid_config.x_bounds[1] > self.dataset_constraints.domain_x[1] or
                            self.grid_config.x_bounds[1] <= self.grid_config.x_bounds[0])
        invalid_y_bounds = (self.grid_config.y_bounds[0] < self.dataset_constraints.domain_y[0] or
                            self.grid_config.y_bounds[1] > self.dataset_constraints.domain_y[1] or
                            self.grid_config.y_bounds[1] <= self.grid_config.y_bounds[0])
        invalid_z_bounds = (self.grid_config.z_bounds[0] < self.dataset_constraints.domain_z[0] or
                            self.grid_config.z_bounds[1] > self.dataset_constraints.domain_z[1] or
                            self.grid_config.z_bounds[1] <= self.grid_config.z_bounds[0])

        # self.log.debug("Validating number of spatial points")
        invalid_nx = self.grid_config.nx > self.dataset_constraints.max_res_x
        invalid_ny = self.grid_config.ny > self.dataset_constraints.max_res_y
        invalid_nz = self.grid_config.nz > self.dataset_constraints.max_res_z

        if invalid_x_bounds or invalid_y_bounds or invalid_z_bounds:
            # self.log.exception("Invalid spatial bounds. Selected spatial bounds do not lie within valid domain")
            raise SpatialResolutionError("Selected spatial bounds do not lie within valid domain")
        if invalid_nx or invalid_ny or invalid_nz:
            # self.log.exception(
            #     "Invalid number of spatial points. Quantity of points on one or more axes is more than maximum resultion")
            raise SpatialResolutionError("Quantity of points on one or more axes is more than maximum resultion")

        # Initialize vector of all possible gridpoints
        # self.log.debug("Creating a grid of all possible spatial points")
        all_possible_yvals = np.loadtxt("../JHUTDDatasets/channel/channel_yvals.txt")
        all_possible_xvals = np.linspace(self.dataset_constraints.domain_x[0], self.dataset_constraints.domain_x[1],
                                         self.dataset_constraints.max_res_x)
        all_possible_zvals = np.linspace(self.dataset_constraints.domain_z[0], self.dataset_constraints.domain_z[1],
                                         self.dataset_constraints.max_res_z)

        # Initialize vector of all possible grid indices
        # all_possible_x_indices = np.arange(0, 2048)
        # all_possible_y_indices = np.arange(0, 512)
        # all_possible_z_indices = np.arange(0, 1536)

        # Determine start/end indices along grid axes and validate
        # self.log.debug("Finding user-defined spatial indices within all possible points in grid")
        index_start_x, index_end_x, available_x_indices, nx_too_constrained = (
            self._validate_resolution(self.grid_config.x_bounds, all_possible_xvals, self.grid_config.nx))

        index_start_y, index_end_y, available_y_indices, ny_too_constrained = (
            self._validate_resolution(self.grid_config.y_bounds, all_possible_yvals, self.grid_config.ny))

        index_start_z, index_end_z, available_z_indices, nz_too_constrained = (
            self._validate_resolution(self.grid_config.z_bounds, all_possible_zvals, self.grid_config.nz))

        # Validate resolution and return error if needed
        inval_points = [[], [], []]

        def append_vals(vals, list2d):
            for i in range(len(vals)):
                list2d[i].append(vals[i])
            return list2d

        if nx_too_constrained or ny_too_constrained or nz_too_constrained:
            if nx_too_constrained:
                inval_points = append_vals(["x", self.grid_config.nx, int(available_x_indices)], inval_points)
            if ny_too_constrained:
                inval_points = append_vals(["y", self.grid_config.ny, int(available_y_indices)], inval_points)
            if nz_too_constrained:
                inval_points = append_vals(["z", self.grid_config.nz, int(available_z_indices)], inval_points)

            raise SpatialResolutionError(
                f"Selected grid resolution exceeds available indices on axes: {', '.join(inval_points[0])}\n"
                f"Selected number of grid points: {inval_points[1]}\n"
                f"Available grid points between selected bounds: {inval_points[2]}"
            )

        # self.log.debug("Creating finalized spatial grid from user-defined spatial bounds")
        x_points = np.linspace(self.grid_config.x_bounds[0], self.grid_config.x_bounds[1], self.grid_config.nx,
                               dtype=np.float64)
        y_points = np.linspace(self.grid_config.y_bounds[0], self.grid_config.y_bounds[1], self.grid_config.ny,
                               dtype=np.float64)
        z_points = np.linspace(self.grid_config.z_bounds[0], self.grid_config.z_bounds[1], self.grid_config.nz,
                               dtype=np.float64)

        points = np.array([axis.ravel() for axis in np.meshgrid(x_points, y_points, z_points, indexing='ij')],
                          dtype=np.float64).T

        return points

    @staticmethod
    def _validate_resolution(bounds, full_grid, requested_n):
        """
        Converts user defined bounds to indices and validates against dataset limits.
        Helper function to initPoints.
        """
        index_start = np.argmin(np.abs(full_grid - bounds[0]))
        index_end = np.argmin(np.abs(full_grid - bounds[1]))

        available_indices = index_end - index_start

        too_constrained = available_indices < requested_n

        return index_start, index_end, available_indices, too_constrained


    def init_time_vector(self):
        """
        Generate a list of temporal locations for each spatial volume.
        List of time points is aligned to the minimum delta-t of the dataset.

        :return: self.time_indices -> np.ndarray of shape (nt, 1)
        :raises: InvalidTimeBoundError, InvalidTimePointQuantityError, TimeResolutionError, NotEnoughTimeIndicesError
        """

        user_t_start = self.grid_config.t_bounds[0]
        user_t_end = self.grid_config.t_bounds[1]

        if user_t_start < self.dataset_constraints.domain_t[0] or user_t_end > self.dataset_constraints.domain_t[1]:
            raise InvalidTimeBoundError(
                f"Selected time bounds do not exist inside possible domain {self.dataset_constraints.domain_t}")
        elif self.grid_config.nt > 4000:
            raise InvalidTimePointQuantityError(
                f"Selected number of time points is too large. Max existing time points: {4000}")

        time_index_vector = np.arange(0, 4000)
        time_vector = time_index_vector * self.dataset_constraints.min_dt

        i_start = int(np.ceil(user_t_start / self.dataset_constraints.min_dt))
        i_end = int(np.floor(user_t_end / self.dataset_constraints.min_dt))

        self.snapshot_indices = np.linspace(i_start, i_end, self.grid_config.nt, dtype=int)

        unique_indices = np.unique(self.snapshot_indices)
        adjusted_nt = len(unique_indices)

        if len(unique_indices) < len(self.snapshot_indices):
            raise TimeResolutionError(
                f"Error:\nNumber of time steps {self.grid_config.nt} between bounds [{user_t_start}, {user_t_end}] not possible) "
                f"with a minimum timestep of {self.dataset_constraints.min_dt}.")
            # prompt_to_adjust_or_to_enter_new_parameters()
        elif i_end <= i_start:
            raise NotEnoughTimeIndicesError("Error:\nRounded time bounds do not contain enough distinct time points")

        return time_vector[self.snapshot_indices]

    @staticmethod
    def get_turbdata_object(dataset_title, filepath, auth_token):
        try:
            turbdata_obj = turb_dataset(dataset_title=dataset_title,
                                        output_path=str(filepath),
                                        auth_token=auth_token)
        except Exception as e:
            raise TurbDatasetObjectFailError(f"Failed to instantiate turb_dataset object.\n{e}")

        return turbdata_obj


    """
    --------------------------------------------------------------------------------------------------------------------
    ------------------------------------------ QUERY LOOP sequence -----------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def get_chunk(self, query_limit, resume_index):
        """
        :param query_limit: [int] number of points allowed to query
        :param resume_index: [int] Last unfinished index position in self.points

        :return: np.ndarray: Array of shape (N,3) containing the next chunk's points
        """
        # Get the end index of the chunk. If the end index is passed the volume size, then change flag and adjust index
        computed_end_index = resume_index + query_limit

        self.state.flags.is_last_chunk = False

        if computed_end_index > self.grid.num_spatial_points:
            end_index = self.grid.num_spatial_points
            self.state.flags.is_last_chunk = True
        else:
            end_index = computed_end_index

        chunk_points = self.grid.points[resume_index:end_index, :]
        chunk_indices = (resume_index, end_index)

        # self.chunk_points = chunk_points
        # self.chunk_indices = chunk_indices

        # print(f"Chunk from index {resume_index} to {end_index-1} ({end_index - resume_index} points)")

        return chunk_points, chunk_indices


    def query_points(self, turbdata_object, chunk_points, time_val):
        """
        Request points from JHU Turbulence Database through API interface.
        getData is imported from givernylocal.turbulence_toolkit

        :return: result - array of requested variable at select spatial points
        :raises: QueryFailedError
        """
        # self.log.debug("START QUERY_POINTS BLOCK")
        # time = self.time_indices[self.state.resume_temporal_index]
        # queryPoints = self.points[self.state.resume_volume_index:self.state.resume_volume_index + self.state.current_query_limit]


        try:
            # self.log.debug("Attempting query...")
            # self.log.debug("Querying points: %d - %d of %d | Current snapshot: %d of %d",
            #                chunk_indices[0]+1, chunk_indices[1], self.num_spatial_points,
            #                self.state.resume_temporal_index+1, self.grid_config.nt)
            # self.log.debug(self.state.__dict__)

            # with LogDuration(self.log, "getData()", warn_if_over=2.0):

                result = getData(turbdata_object,
                                 self.variable,
                                 time_val,
                                 self.query_method_config.temporal_method.lower(),
                                 self.query_method_config.spatial_method.lower(),
                                 self.query_method_config.spatial_operator.lower(),
                                 chunk_points)

            # self.log.debug("Query was successful")

        except Exception as e:
            # self.log.exception("Query failed")
            # self.log.debug(self.state.__dict__)

            raise QueryFailedError(f"Query failed\n{e}")

        if self.state.flags.is_last_chunk:
            # self.log.debug("Updating snapshot_is_complete flag")
            # self.log.debug(self.state.__dict__)
            self.state.flags.snapshot_is_complete = True
            # self.state.resume_volume_index += 1

        if self.state.flags.snapshot_is_complete and self.state.resume_temporal_index + 1 == self.grid_config.nt:
            # self.log.debug("Updating series_is_complete flag")
            # self.log.debug(self.state.__dict__)
            self.state.flags.series_is_complete = True

        # self.log.debug("ENDING QUERY_POINTS BLOCK")

        return result


    def update_query_history(self, query_passed:bool):
        self.state.query_history.append(query_passed)
        if len(self.state.query_history) > self.runtime_config.tunable.query_history_length:
            self.state.query_history.pop(0)


    def update_query_limit(self):
        """
        Updates the amount of points each query attempt tries to request

        :return: self.query_limit
        """
        if len(self.state.query_history) < 2:
            print("Not enough attempts in query history to update query limit")
            new_query_limit = self.state.current_query_limit
        else:
            weights = np.logspace(0.1, 1, len(self.state.query_history), base=10)
            weights /= weights.sum()

            weighted_score = np.dot(weights, self.state.query_history)
            centered_score = (2 * weighted_score) - 1

            qmin, qmax = self.runtime_config.tunable.query_limit_range
            alpha = self.runtime_config.tunable.query_limit_update_factor

            delta = centered_score * alpha * self.state.current_query_limit
            computed_query_limit = self.state.current_query_limit + delta

            new_query_limit = max(min(computed_query_limit, qmax), qmin)

            self.state.current_query_limit = new_query_limit

        return new_query_limit


    def update_wait_time(self, attempt_passed:bool):
        min_wait_time, max_wait_time = self.runtime_config.tunable.wait_range

        if attempt_passed:
            self.state.num_consecutive_fails = 0
            return min_wait_time

        # self.state.num_consecutive_fails += 1

        padding = self.runtime_config.tunable.wait_update_padding

        if self.state.num_consecutive_fails <= padding:
            return min_wait_time

        growth_factor = self.runtime_config.tunable.wait_update_factor

        new_wait_time = min_wait_time * (growth_factor ** (self.state.num_consecutive_fails - padding))

        return min(new_wait_time, max_wait_time)



    """
    --------------------------------------------------------------------------------------------------------------------
    ------------------------------------------ Utility functions -------------------------------------------------------
    --------------------------------------------------------------------------------------------------------------------
    """
    def save_state(self, state_path):
        with open(state_path, "w") as f:
            json.dump(Helper.to_dict(self.state), f, indent=4)


    def _init_snapshot_file(self, result):

        variable = self.variable
        time_index = self.state.resume_temporal_index
        snapshot_time = self.grid.time_vector[time_index]
        n_points = self.grid.num_spatial_points
        dims = self.variable_dims
        h5_path = self.snapshot_h5_path

        print(f"[DEBUG] Creating new snapshot file {h5_path} with dataset {variable}")
        with h5py.File(h5_path, "w") as h5f:
            h5f.create_dataset(
                variable,
                shape=(n_points, dims),
                dtype=np.float32,
                compression="gzip",
                chunks=True
            )

            h5f.attrs["snapshot_time"] = snapshot_time
            h5f.attrs["axes"] = [str(ax) for ax in result[0].axes]
            h5f.attrs["columns"] = [str(c) for c in result[0].columns]
            h5f.attrs["nx"] = self.grid_config.nx
            h5f.attrs["ny"] = self.grid_config.ny
            h5f.attrs["nz"] = self.grid_config.nz
            h5f.attrs["shape"] = (n_points, dims)
            h5f.attrs["min"] = result[0].values.min()
            h5f.attrs["max"] = result[0].values.max()
            h5f.attrs["dtype"] = str(result[0].values.dtype)
            h5f.attrs["dataset"] = self.query_method_config.dataset_title
            # h5f.attrs["variable"] = self.runtime_config.variable
            h5f.attrs["temporal_method"] = self.query_method_config.temporal_method
            h5f.attrs["spatial_method"] = self.query_method_config.spatial_method
            h5f.attrs["spatial_operator"] = self.query_method_config.spatial_operator
            # print("[DEBUG] h5 file was created")


    def save_chunk_data(self, result, chunk_indices, h5_dir):

        variable = self.variable
        time_index = self.state.resume_temporal_index
        hash_str = self.hash_str

        h5_filename = f"t={time_index + 1}_of_nt={self.grid_config.nt}__hash={hash_str[:8]}.h5"
        h5_path = h5_dir / h5_filename
        h5_path.parent.mkdir(parents=True, exist_ok=True)

        self.snapshot_h5_path = h5_path

        if h5_path.exists() and h5_path.is_dir():
            raise IsADirectoryError(f"Expected file but found directory at: {h5_path}")

        if self.state.flags.is_first_chunk and not h5_path.exists():
            if not hasattr(result[0], "values"):
                raise TypeError(f"Result[0] does not have 'values' attribute. Type: {type(result[0])}")

            self._init_snapshot_file(result)
            self.state.flags.is_first_chunk = False

        # Save chunk data
        try:
            with h5py.File(h5_path, "a") as h5:

                data_array = result[0].values if hasattr(result[0], "values") else result
                if not isinstance(data_array, np.ndarray):
                    data_array = np.array(data_array)
                dset = h5[variable]

                dset[chunk_indices[0]:chunk_indices[1], :] = data_array

        except OSError as e:
            # self.log.exception("Failed to open/write to %s", h5_path)
            raise OSError(f"Failed to open/write to {h5_path}")









