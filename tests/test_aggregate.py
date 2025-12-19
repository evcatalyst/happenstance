"""Tests for aggregate module functions."""
from unittest.mock import MagicMock, patch

import pytest

from happenstance.aggregate import _calculate_distance, _geocode_address


class TestGeocodeAddress:
    """Tests for Nominatim-based geocoding."""
    
    @patch('happenstance.aggregate.requests.get')
    @patch('happenstance.aggregate.time.sleep')
    def test_geocode_success(self, mock_sleep, mock_get):
        """Test successful geocoding with Nominatim."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "lat": "37.7749",
                "lon": "-122.4194"
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        result = _geocode_address("Market Street", region="San Francisco")
        
        assert result == (37.7749, -122.4194)
        assert mock_get.call_count == 1
        assert mock_sleep.call_count == 1
        
        # Verify the request was made correctly
        call_args = mock_get.call_args
        assert call_args[1]['params']['q'] == "Market Street, San Francisco"
        assert call_args[1]['params']['format'] == "json"
        assert 'User-Agent' in call_args[1]['headers']
    
    @patch('happenstance.aggregate.requests.get')
    @patch('happenstance.aggregate.time.sleep')
    def test_geocode_empty_address(self, mock_sleep, mock_get):
        """Test geocoding with empty address."""
        result = _geocode_address("", region="San Francisco")
        
        assert result is None
        assert mock_get.call_count == 0
        assert mock_sleep.call_count == 0
    
    @patch('happenstance.aggregate.requests.get')
    @patch('happenstance.aggregate.time.sleep')
    def test_geocode_no_results(self, mock_sleep, mock_get):
        """Test geocoding when Nominatim returns no results."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        result = _geocode_address("Invalid Address", region="San Francisco")
        
        assert result is None
    
    @patch('happenstance.aggregate.requests.get')
    @patch('happenstance.aggregate.time.sleep')
    def test_geocode_request_error(self, mock_sleep, mock_get):
        """Test geocoding when request fails."""
        mock_get.side_effect = Exception("Network error")
        
        result = _geocode_address("Market Street", region="San Francisco")
        
        assert result is None


class TestCalculateDistance:
    """Tests for haversine distance calculation."""
    
    def test_distance_same_location(self):
        """Test distance between same coordinates is zero."""
        distance = _calculate_distance(37.7749, -122.4194, 37.7749, -122.4194)
        assert distance < 0.01  # Should be very close to 0
    
    def test_distance_known_locations(self):
        """Test distance between known locations."""
        # San Francisco to Los Angeles (approximately 347 miles)
        sf_lat, sf_lon = 37.7749, -122.4194
        la_lat, la_lon = 34.0522, -118.2437
        
        distance = _calculate_distance(sf_lat, sf_lon, la_lat, la_lon)
        
        # Should be approximately 347 miles (within 10 miles tolerance)
        assert 337 < distance < 357
    
    def test_distance_short_distance(self):
        """Test distance for short distances (walking distance)."""
        # Two points approximately 0.5 miles apart in San Francisco
        lat1, lon1 = 37.7749, -122.4194
        lat2, lon2 = 37.7820, -122.4194
        
        distance = _calculate_distance(lat1, lon1, lat2, lon2)
        
        # Should be less than 1 mile
        assert distance < 1.0
        assert distance > 0
