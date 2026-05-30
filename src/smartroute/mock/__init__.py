"""Mock service layer for development without real external APIs."""
from smartroute.mock.data import HANGZHOU_POIS, POI_REVIEWS, DISTANCE_MATRIX
from smartroute.mock.services import MockServiceLayer

__all__ = ["HANGZHOU_POIS", "POI_REVIEWS", "DISTANCE_MATRIX", "MockServiceLayer"]
