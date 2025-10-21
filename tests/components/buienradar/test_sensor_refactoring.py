"""Test helper functions for buienradar sensor data loading."""

from unittest.mock import Mock

import pytest

from homeassistant.components.buienradar.sensor import BrSensor


@pytest.fixture
def mock_sensor():
    """Create a mock BrSensor instance."""
    sensor = Mock(spec=BrSensor)
    sensor._attr_native_value = None
    sensor._attr_entity_picture = None
    sensor.state = None
    sensor.entity_description = Mock()
    return sensor


@pytest.mark.parametrize(
    (
        "sensor_type",
        "fcday",
        "expected_state_value",
        "expected_img",
    ),
    [
        ("symbol_1d", 1, "s1", "img1"),
        ("condition_1d", 0, "c0", "img0"),
        ("conditioncode_3d", 2, "cc2", "img2"),
        ("conditiondetailed_1d", 0, "d0", "img0"),
        ("conditionexact_2d", 1, "x1", "img1"),
    ],
)
def test_load_data_sw_symbol_condition_updates(
    mock_sensor,
    sensor_type,
    fcday,
    expected_state_value,
    expected_img,
):
    """Test forecast symbol/condition mapping and state update."""
    mock_sensor.entity_description.key = sensor_type
    data = {
        "forecast": [
            {
                "condition": {
                    "condition": "c0",
                    "exact_nl": "s0",
                    "exact": "x0",
                    "detailed": "d0",
                    "condcode": "cc0",
                    "image": "img0",
                }
            },
            {
                "condition": {
                    "condition": "c1",
                    "exact_nl": "s1",
                    "exact": "x1",
                    "detailed": "d1",
                    "condcode": "cc1",
                    "image": "img1",
                }
            },
            {
                "condition": {
                    "condition": "c2",
                    "exact_nl": "s2",
                    "exact": "x2",
                    "detailed": "d2",
                    "condcode": "cc2",
                    "image": "img2",
                }
            },
        ]
    }

    result = BrSensor._load_data_sw_symbol_condition(
        mock_sensor, sensor_type, data, fcday
    )

    assert result is True
    assert mock_sensor._attr_native_value == expected_state_value
    assert mock_sensor._attr_entity_picture == expected_img


def test_load_data_sw_symbol_condition_no_change(mock_sensor):
    """Test no update when state and picture are unchanged."""
    sensor_type = "condition_1d"
    fcday = 0
    data = {
        "forecast": [
            {
                "condition": {
                    "condition": "cloudy",
                    "exact_nl": "zonnig",
                    "exact": "sunny",
                    "detailed": "partly cloudy",
                    "condcode": "c-0",
                    "image": "img0",
                }
            },
        ]
    }
    mock_sensor.state = "cloudy"
    mock_sensor.entity_picture = "img0"

    result = BrSensor._load_data_sw_symbol_condition(
        mock_sensor, sensor_type, data, fcday
    )

    assert result is False
    assert mock_sensor._attr_native_value is None
    assert mock_sensor._attr_entity_picture is None


def test_load_data_sw_symbol_condition_index_error(mock_sensor):
    """Test handling out-of-range forecast index."""
    sensor_type = "symbol_5d"
    fcday = 4
    data = {
        "forecast": [
            {"condition": {"condition": "c0", "exact_nl": "s0", "image": "img0"}},
            {"condition": {"condition": "c1", "exact_nl": "s1", "image": "img1"}},
        ]
    }
    mock_sensor.state = "prev_state"
    mock_sensor._attr_entity_picture = "prev_img"

    result = BrSensor._load_data_sw_symbol_condition(
        mock_sensor, sensor_type, data, fcday
    )

    assert result is False
    assert mock_sensor._attr_native_value is None
    assert mock_sensor._attr_entity_picture == "prev_img"


@pytest.mark.parametrize(
    (
        "state_val",
        "forecast_data",
        "sensor_type",
        "fcday",
        "expected_result",
        "expected_value",
    ),
    [
        (
            12.0,
            [{"windspeed": 8.0}, {"windspeed": 12.0}, {"windspeed": 6.5}],
            "windspeed_1d",
            1,
            True,
            43.2,
        ),
        (
            None,
            [{"windspeed": 8.0}, {"windspeed": 12.0}, {"windspeed": 6.5}],
            "windspeed_1d",
            1,
            True,
            12.0,
        ),
        (
            None,
            [{"windspeed": 8.0}, {"windspeed": 12.0}],
            "windspeed_3d",
            3,
            False,
            None,
        ),
    ],
)
def test_load_data_windspeed(
    mock_sensor,
    state_val,
    forecast_data,
    sensor_type,
    fcday,
    expected_result,
    expected_value,
):
    """Test forecast wind speed and visibility conversion."""
    mock_sensor.state = state_val
    mock_sensor.entity_description.key = sensor_type
    data = {"forecast": forecast_data}

    result = BrSensor._load_data_windspeed(mock_sensor, sensor_type, data, fcday)

    assert result is expected_result
    assert mock_sensor._attr_native_value == expected_value


@pytest.mark.parametrize(
    (
        "sensor_type",
        "expected_state_value",
        "expected_img",
    ),
    [
        ("symbol", "s0", "img0"),
        ("condition", "c0", "img0"),
        ("conditioncode", "cc0", "img0"),
        ("conditiondetailed", "d0", "img0"),
        ("conditionexact", "x0", "img0"),
    ],
)
def test_load_data_eq_symbol_condition_updates(
    mock_sensor,
    sensor_type,
    expected_state_value,
    expected_img,
):
    """Test forecast symbol/condition mapping and state update."""
    mock_sensor.entity_description.key = sensor_type
    data = {
        "condition": {
            "condition": "c0",
            "exact_nl": "s0",
            "exact": "x0",
            "detailed": "d0",
            "condcode": "cc0",
            "image": "img0",
        }
    }

    result = BrSensor._load_data_eq_symbol_condition(mock_sensor, sensor_type, data)

    assert result is True
    assert mock_sensor._attr_native_value == expected_state_value
    assert mock_sensor._attr_entity_picture == expected_img


def test_load_data_eq_symbol_condition_no_change(mock_sensor):
    """Test no update when state and picture are unchanged."""
    sensor_type = "condition"
    data = {
        "condition": {
            "condition": "cloudy",
            "exact_nl": "zonnig",
            "exact": "sunny",
            "detailed": "partly cloudy",
            "condcode": "c-0",
            "image": "img0",
        }
    }
    mock_sensor.state = "cloudy"
    mock_sensor.entity_picture = "img0"

    result = BrSensor._load_data_eq_symbol_condition(mock_sensor, sensor_type, data)

    assert result is False
    assert mock_sensor._attr_native_value is None
    assert mock_sensor._attr_entity_picture is None


@pytest.mark.parametrize(
    ("state_val", "sensor_type", "expected_result", "expected_value"),
    [
        (10.0, "windspeed", True, 36.0),
        (15.5, "windgust", True, 55.8),
        (5000, "visibility", True, 5.0),
        (None, "windspeed", True, 10.0),
    ],
)
def test_load_data_wind_visibility(
    mock_sensor, state_val, sensor_type, expected_result, expected_value
):
    """Test wind speed, wind gust, and visibility conversion."""
    mock_sensor.state = state_val

    data = {sensor_type: state_val if state_val is not None else 10.0}

    result = BrSensor._load_data_wind_visibility(mock_sensor, sensor_type, data)

    assert result is expected_result
    assert mock_sensor._attr_native_value == expected_value
