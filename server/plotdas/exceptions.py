class PlotDASError(Exception):
    """Base exception for errors suitable for CLI display."""


class ConfigurationError(PlotDASError):
    pass


class InvalidRequestError(PlotDASError):
    pass


class UnsupportedFormatError(PlotDASError):
    pass


class DataReadError(PlotDASError):
    pass


class DataGapError(DataReadError):
    pass


class ChannelRangeError(InvalidRequestError):
    pass


class OutputExistsError(PlotDASError):
    pass


class JobError(PlotDASError):
    pass

