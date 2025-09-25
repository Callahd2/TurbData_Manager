from pathlib import Path
import json

class CreateSessionInputsValidator:
    """
    Separated class to check all inputs contained in NewSessionDialog

    Keys to check:
    root_dir, nx, ny, nz, nt, start_x, start_y, start_z, start_t, end_x, end_y, end_z, end_t,
    """
    def __init__(self, **kwargs):
        self.fields = kwargs

    def load_grid_limits(self, metadata: dict):
        self.limits = metadata["raw"]

    def validate(self):
        errors = []

        # check root_dir
        if not self.fields["root_directory"].exists():
            errors.append("Root directory does not exist")
        elif not self.fields["root_directory"].is_dir():
            errors.append("Root directory is not a directory")

        # Validate nx, ny, nz, nt are within bounds
        if not self.fields["nx"] >= 1 or self.fields["nx"] <= self.limits["nx"]:
            errors.append("Invalid nx")
        if not self.fields["ny"] >= 1 or self.fields["ny"] <= self.limits["ny"]:
            errors.append("Invalid ny")
        if not self.fields["nz"] >= 1 or self.fields["nz"] <= self.limits["nz"]:
            errors.append("Invalid nz")
        if not self.fields["nt"] >= 1 or self.fields["nt"] <= self.limits["nt"]:
            errors.append("Invalid nt")







