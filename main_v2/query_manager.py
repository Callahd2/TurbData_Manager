from main_v2.supplementary_classes import State
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from main_v2.query_session_v2 import QuerySession
import json
import time
import traceback, sys


class Flags:
    def __init__(self):
        pass

class QueryManager(QObject):

    spatialProgress = pyqtSignal(int, int)
    chunkSaved = pyqtSignal(tuple)
    snapshotComplete = pyqtSignal(int)
    temporalProgress = pyqtSignal(int, int)
    seriesComplete = pyqtSignal()
    status = pyqtSignal(str) # Sends to status label in MainWindow
    logMessage = pyqtSignal(str) # Sends to log in MainWindow
    error = pyqtSignal(str)

    def __init__(self, file_manager, runtime_config, auth_token, variable):
        super().__init__()

        self.fm = file_manager
        self.runtime_config = runtime_config
        self.auth_token = auth_token
        self.variable = variable

        self.state = State.load_from_json(self.fm.paths.files.state_path)
        self.flags = Flags()

        self.flags.stopped = False
        self.flags.paused = False

        self.session = QuerySession(
            dataset_constraints = self.fm.dataset_constraints,
            query_method_config = self.fm.query_method_config,
            grid_config = self.fm.grid_config,
            runtime_config = self.runtime_config,
            state = self.state,
            variable = self.variable,
            auth_token = self.auth_token,
            hash_str=self.fm.hash_str
        )
        # self.num_spatial_points = self.fm.grid_config.nx * self.fm.grid_config.ny * self.fm.grid_config.nz


    @pyqtSlot()
    def start(self):
        """
        Main loop for Querying
        """
        try:
            "When a session is started, get:"
            turb_obj = self.session.get_turbdata_object(
                dataset_title=self.fm.query_method_config.dataset_title.lower(),
                filepath=self.fm.paths.dirs.series_var_dir,
                auth_token=self.auth_token
            )

            total_points = self.session.grid.num_spatial_points
            # time_vector = self.session.grid.time_vector
            nt = self.fm.grid_config.nt

            self.spatialProgress.emit(self.state.resume_volume_index, total_points)
            self.temporalProgress.emit(self.state.resume_temporal_index, nt)

            # Start the query size from configs, then it will update throughout the loop
            current_query_size = self.runtime_config.tunable.starting_query_limit

            "Outer loop cycles through timesteps"
            while not self.flags.stopped:
                if self.session.state.flags.series_is_complete:
                    break

                while self.flags.paused:
                    QThread.msleep(50)
                    if self.flags.stopped:
                        break

                resume_volume_index = self.session.state.resume_volume_index
                if resume_volume_index >= total_points:
                    self._on_snapshot_complete()
                    continue

                time_index = self.session.state.resume_temporal_index
                time_val = self.session.grid.time_vector[time_index]



                "1. Get chunk grid points"
                print(self.session.grid.num_spatial_points)
                print(self.session.state.resume_temporal_index)
                print(self.session.state.resume_volume_index)
                chunk_points, chunk_indices = self.session.get_chunk(
                    query_limit=current_query_size, resume_index=resume_volume_index)

                "2. Query the chunk"
                try:
                    self.status.emit(f"Querying points {chunk_indices[0]}-{chunk_indices[1]} of {total_points}"
                                     f"\tSnapshot {time_index+1} of {nt}")

                    print("Querying...")
                    result = self.session.query_points(
                        turbdata_object=turb_obj, chunk_points=chunk_points, time_val=time_val)
                    query_passed = True
                    print("Query passed")

                except Exception as e:
                    query_passed = False
                    print("Query failed")
                    tb = traceback.format_exc()
                    print(tb, file=sys.stderr, flush=True)

                if query_passed:
                    self._on_query_passed(result, chunk_indices)

                "3. Update query pass/fail history"
                self.session.update_query_history(query_passed=query_passed)

                "4. Update query size"
                new_query_size = self.session.update_query_limit()
                self.session.state.current_query_limit = new_query_size

                "5. Update wait time"
                new_wait_time = self.session.update_wait_time(query_passed)

                if not query_passed:
                    self._on_query_failed(new_wait_time)

                if self.session.state.flags.snapshot_is_complete:
                    self._on_snapshot_complete()

                if self.session.state.resume_temporal_index >= self.session.grid_config.nt:
                    self._on_series_complete()

                self.session.save_state(self.fm.paths.files.state_path)


        except Exception as e:
            tb = traceback.format_exc()
            print(tb, file=sys.stderr, flush=True)
            self.error.emit(tb)


    @pyqtSlot()
    def pause(self): self.flags.paused = True

    @pyqtSlot()
    def stop(self): self.flags.stopped = True


    def _on_query_passed(self, result, chunk_indices):
        num_points_queried = chunk_indices[1] - chunk_indices[0]
        self.state.resume_volume_index += num_points_queried

        self.status.emit("Saving chunk data...")

        self.session.save_chunk_data(result=result, chunk_indices=chunk_indices,
                                     h5_dir=self.fm.paths.dirs.series_var_dir)
        self.session.save_state(state_path=self.fm.paths.files.state_path)
        self.chunkSaved.emit(chunk_indices)
        self.spatialProgress.emit(chunk_indices[1], self.session.grid.num_spatial_points)

    def _on_query_failed(self, new_wait_time):
        self.session.state.num_consecutive_fails += 1
        time.sleep(new_wait_time)
        self.status.emit(f"Waiting for {time.strftime('%H:%M:%S', time.gmtime(new_wait_time))}")

    def _on_snapshot_complete(self):
        self.snapshotComplete.emit(self.session.state.resume_temporal_index)
        self.temporalProgress.emit(self.session.state.resume_temporal_index+1, self.fm.grid_config.nt)
        self.session.state.flags.is_first_chunk = True
        self.session.state.flags.snapshot_is_complete = False
        self.session.state.resume_temporal_index += 1
        self.session.state.resume_volume_index = 0
        self.session.state.is_first_chunk = True


    def _on_series_complete(self):
        self.session.state.flags.series_is_complete = True
        self.flags.stopped = True
        self.__update_hash_log()
        self.session.save_state(self.fm.paths.files.state_path)
        self.seriesComplete.emit()

    def __update_hash_log(self):
        hash_log_path = self.fm.paths.files.hash_log_path
        hash_str = self.fm.hash_str
        variable = self.variable

        # Load hash log
        with open(hash_log_path, "r") as f:
            hash_log = json.load(f)

        # Update hash log
        try:
            hash_log[hash_str]["completed"][variable] = True
        except Exception as e:
            pass

        # Write updated hash log back to file
        with open(hash_log_path, "w") as f:
            json.dump(hash_log, f, indent=4)
