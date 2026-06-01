"""Models package for dispersion and forecasting models."""

from .gaussian_model import GaussianPlumeModel
from .forecast_model import PollutionForecastModel

__all__ = ['GaussianPlumeModel', 'PollutionForecastModel']
