"""Models package for dispersion and forecasting models."""

from .gaussian_model import GaussianPlumeModel
from .forecast_model import AirQualityForecastModel

__all__ = ['GaussianPlumeModel', 'AirQualityForecastModel']
