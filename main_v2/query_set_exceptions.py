class QueryFailedError(Exception):
    pass

class InvalidTimeRangeError(Exception):
    pass

class SubvolumeTooLarge(Exception):
    pass

class InvalidTimeBoundError(Exception):
    pass

class InvalidTimePointQuantityError(Exception):
    pass

class TimeResolutionError(Exception):
    pass

class NotEnoughTimeIndicesError(Exception):
    pass

# class InvalidSpatialBoundsError(Exception):
#     pass

# class InvalidSpatialPointQuantityError(Exception):
#     pass

class SpatialResolutionError(Exception):
    pass

class fileManagerInitializationError(Exception):
    pass

class TurbDatasetObjectFailError(Exception):
    pass

class SeriesAlreadyCompletedError(Exception):
    pass