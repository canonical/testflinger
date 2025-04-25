"""
Flask extensions that may be imported by other modules
"""

from prometheus_flask_exporter import PrometheusMetrics

metrics = PrometheusMetrics.for_app_factory()
