"""Test shopping list component."""

from http import HTTPStatus

import pytest

from homeassistant.components.shopping_list import NoMatchingShoppingListItem
from homeassistant.components.shopping_list.const import (
    ATTR_CATEGORY,
    ATTR_REVERSE,
    DOMAIN,
    EVENT_SHOPPING_LIST_UPDATED,
    SERVICE_ADD_CATEGORY,
    SERVICE_ADD_ITEM,
    SERVICE_CLEAR_COMPLETED_ITEMS,
    SERVICE_COMPLETE_ITEM,
    SERVICE_DELETE_ALL,
    SERVICE_GROUP_BY_CATEGORIES,
    SERVICE_REMOVE_CATEGORY,
    SERVICE_REMOVE_ITEM,
    SERVICE_SORT,
)
from homeassistant.components.websocket_api import (
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    TYPE_RESULT,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from tests.common import async_capture_events
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_add_item(hass: HomeAssistant, sl_setup) -> None:
    """Test adding an item intent."""

    response = await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": " beer "}}
    )
    assert len(hass.data[DOMAIN].items) == 1
    assert hass.data[DOMAIN].items[0]["name"] == "beer"  # name was trimmed

    # Response text is now handled by default conversation agent
    assert response.response_type == intent.IntentResponseType.ACTION_DONE


async def test_remove_item(hass: HomeAssistant, sl_setup) -> None:
    """Test removiung list items."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "cheese"}}
    )

    assert len(hass.data[DOMAIN].items) == 2

    # Remove a single item
    item_id = hass.data[DOMAIN].items[0]["id"]
    await hass.data[DOMAIN].async_remove(item_id)

    assert len(hass.data[DOMAIN].items) == 1

    item = hass.data[DOMAIN].items[0]
    assert item["name"] == "cheese"

    # Trying to remove the same item twice should fail
    with pytest.raises(NoMatchingShoppingListItem):
        await hass.data[DOMAIN].async_remove(item_id)


async def test_update_list(hass: HomeAssistant, sl_setup) -> None:
    """Test updating all list items."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "cheese"}}
    )

    # Update a single attribute, other attributes shouldn't change
    await hass.data[DOMAIN].async_update_list({"complete": True})

    beer = hass.data[DOMAIN].items[0]
    assert beer["name"] == "beer"
    assert beer["complete"] is True

    cheese = hass.data[DOMAIN].items[1]
    assert cheese["name"] == "cheese"
    assert cheese["complete"] is True

    # Update multiple attributes
    await hass.data[DOMAIN].async_update_list({"name": "dupe", "complete": False})

    beer = hass.data[DOMAIN].items[0]
    assert beer["name"] == "dupe"
    assert beer["complete"] is False

    cheese = hass.data[DOMAIN].items[1]
    assert cheese["name"] == "dupe"
    assert cheese["complete"] is False


async def test_clear_completed_items(hass: HomeAssistant, sl_setup) -> None:
    """Test clear completed list items."""
    await intent.async_handle(
        hass,
        "test",
        "HassShoppingListAddItem",
        {"item": {"value": "beer"}},
    )

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "cheese"}}
    )

    assert len(hass.data[DOMAIN].items) == 2

    # Update a single attribute, other attributes shouldn't change
    await hass.data[DOMAIN].async_update_list({"complete": True})

    await hass.data[DOMAIN].async_clear_completed()

    assert len(hass.data[DOMAIN].items) == 0


async def test_recent_items_intent(hass: HomeAssistant, sl_setup) -> None:
    """Test recent items."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "soda"}}
    )

    response = await intent.async_handle(hass, "test", "HassShoppingListLastItems")

    assert (
        response.speech["plain"]["speech"]
        == "These are the top 3 items on your shopping list: soda, wine, beer"
    )


async def test_deprecated_api_get_all(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, sl_setup
) -> None:
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    client = await hass_client()
    resp = await client.get("/api/shopping_list")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "beer"
    assert not data[0]["complete"]
    assert data[1]["name"] == "wine"
    assert not data[1]["complete"]


async def test_ws_get_items(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test get shopping_list items websocket command."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    await client.send_json({"id": 5, "type": "shopping_list/items"})
    msg = await client.receive_json()
    assert msg["success"] is True
    assert len(events) == 0

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    data = msg["result"]
    assert len(data) == 2
    assert data[0]["name"] == "beer"
    assert not data[0]["complete"]
    assert data[1]["name"] == "wine"
    assert not data[1]["complete"]


async def test_ws_get_categories(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test get shopping_list categories websocket command."""

    data = hass.data[DOMAIN]

    await data.async_add_category("testCategory")
    await data.async_add_category("secondTestCategory")

    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    await client.send_json({"id": 11, "type": "shopping_list/categories/list"})
    msg = await client.receive_json()
    assert len(events) == 0  # no event is fired for fetching the categories

    assert msg["id"] == 11
    assert msg["success"] is True
    categories = msg["result"]
    assert isinstance(categories, list)
    assert len(categories) >= 2

    first_category = next(cat for cat in categories if cat["name"] == "testCategory")
    assert first_category is not None
    assert first_category["predefined"] is False

    second_category = next(
        cat for cat in categories if cat["name"] == "secondTestCategory"
    )
    assert second_category is not None
    assert second_category["predefined"] is False


async def test_deprecated_api_update(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, sl_setup
) -> None:
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_client()
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    resp = await client.post(
        f"/api/shopping_list/item/{beer_id}", json={"name": "soda"}
    )

    assert resp.status == HTTPStatus.OK
    assert len(events) == 1
    data = await resp.json()
    assert data == {
        "id": beer_id,
        "name": "soda",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }

    resp = await client.post(
        f"/api/shopping_list/item/{wine_id}", json={"complete": True}
    )

    assert resp.status == HTTPStatus.OK
    assert len(events) == 2
    data = await resp.json()
    assert data == {
        "id": wine_id,
        "name": "wine",
        "complete": True,
        "category": None,
        "quantity": None,
        "unit": None,
    }

    beer, wine = hass.data["shopping_list"].items
    assert beer == {
        "id": beer_id,
        "name": "soda",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert wine == {
        "id": wine_id,
        "name": "wine",
        "complete": True,
        "category": None,
        "quantity": None,
        "unit": None,
    }

async def test_remove_existing_category(hass: HomeAssistant, sl_setup) -> None:
    """Test that an existing category is removed successfully."""

    data = hass.data[DOMAIN]

    # Ensure there is at least one category
    if not data.categories:
        data.categories.append("SampleCategory")

    category_to_remove = data.categories[0]

    # Call the remove_category service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_CATEGORY,
        {ATTR_CATEGORY: category_to_remove},
        blocking=True,
    )

    # The category should no longer exist
    assert category_to_remove not in data.categories


async def test_remove_non_existing_category(hass: HomeAssistant, sl_setup) -> None:
    """Test that removing a non-existing category does not change categories."""

    data = hass.data[DOMAIN]

    # Snapshot current categories
    before = list(data.categories)

    # Attempt to remove a category that does not exist; component logs error
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_CATEGORY,
        {ATTR_CATEGORY: "NotInList"},
        blocking=True,
    )

    # Categories should be unchanged
    assert data.categories == before

async def test_ws_update_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test update shopping_list item websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {
            "id": 5,
            "type": "shopping_list/items/update",
            "item_id": beer_id,
            "name": "soda",
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data == {
        "id": beer_id,
        "name": "soda",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert len(events) == 1

    await client.send_json(
        {
            "id": 6,
            "type": "shopping_list/items/update",
            "item_id": wine_id,
            "complete": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data == {
        "id": wine_id,
        "name": "wine",
        "complete": True,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert len(events) == 2

    beer, wine = hass.data["shopping_list"].items
    assert beer == {
        "id": beer_id,
        "name": "soda",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert wine == {
        "id": wine_id,
        "name": "wine",
        "complete": True,
        "category": None,
        "quantity": None,
        "unit": None,
    }


async def test_api_update_fails(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, sl_setup
) -> None:
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )

    client = await hass_client()
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    resp = await client.post("/api/shopping_list/non_existing", json={"name": "soda"})

    assert resp.status == HTTPStatus.NOT_FOUND
    assert len(events) == 0

    beer_id = hass.data["shopping_list"].items[0]["id"]
    resp = await client.post(f"/api/shopping_list/item/{beer_id}", json={"name": 123})

    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_ws_update_item_fail(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test failure of update shopping_list item websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {
            "id": 5,
            "type": "shopping_list/items/update",
            "item_id": "non_existing",
            "name": "soda",
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    data = msg["error"]
    assert data == {"code": "item_not_found", "message": "Item not found"}
    assert len(events) == 0

    await client.send_json({"id": 6, "type": "shopping_list/items/update", "name": 123})
    msg = await client.receive_json()
    assert msg["success"] is False
    assert len(events) == 0


async def test_deprecated_api_clear_completed(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, sl_setup
) -> None:
    """Test the API."""

    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]

    client = await hass_client()
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Mark beer as completed
    resp = await client.post(
        f"/api/shopping_list/item/{beer_id}", json={"complete": True}
    )
    assert resp.status == HTTPStatus.OK
    assert len(events) == 1

    resp = await client.post("/api/shopping_list/clear_completed")
    assert resp.status == HTTPStatus.OK
    assert len(events) == 2

    items = hass.data["shopping_list"].items
    assert len(items) == 1

    assert items[0] == {
        "id": wine_id,
        "name": "wine",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }


async def test_ws_clear_items(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test clearing shopping_list items websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {
            "id": 5,
            "type": "shopping_list/items/update",
            "item_id": beer_id,
            "complete": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert len(events) == 1

    await client.send_json({"id": 6, "type": "shopping_list/items/clear"})
    msg = await client.receive_json()
    assert msg["success"] is True
    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0] == {
        "id": wine_id,
        "name": "wine",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert len(events) == 2


async def test_deprecated_api_create(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, sl_setup
) -> None:
    """Test the API."""

    client = await hass_client()
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    resp = await client.post("/api/shopping_list/item", json={"name": "soda"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data["name"] == "soda"
    assert data["complete"] is False
    assert len(events) == 1

    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0]["name"] == "soda"
    assert items[0]["complete"] is False


async def test_deprecated_api_create_fail(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, sl_setup
) -> None:
    """Test the API."""

    client = await hass_client()
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    resp = await client.post("/api/shopping_list/item", json={"name": 1234})

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert len(hass.data["shopping_list"].items) == 0
    assert len(events) == 0


async def test_ws_add_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test adding shopping_list item websocket command."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {"id": 5, "type": "shopping_list/items/add", "name": "soda", "category": None}
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert data["name"] == "soda"
    assert data["complete"] is False
    assert len(events) == 1

    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0]["name"] == "soda"
    assert items[0]["complete"] is False


async def test_ws_add_item_fail(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test adding shopping_list item failure websocket command."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {"id": 5, "type": "shopping_list/items/add", "name": 123, "category": None}
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert len(events) == 0
    assert len(hass.data["shopping_list"].items) == 0

async def test_ws_remove_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test removing shopping_list item websocket command."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json({"id": 5, "type": "shopping_list/items/add", "name": "soda"})
    msg = await client.receive_json()
    first_item_id = msg["result"]["id"]
    await client.send_json(
        {"id": 6, "type": "shopping_list/items/add", "name": "cheese"}
    )
    msg = await client.receive_json()
    assert len(events) == 2

    items = hass.data["shopping_list"].items
    assert len(items) == 2

    await client.send_json(
        {"id": 7, "type": "shopping_list/items/remove", "item_id": first_item_id}
    )
    msg = await client.receive_json()
    assert len(events) == 3
    assert msg["success"] is True

    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0]["name"] == "cheese"

async def test_ws_remove_item_fail(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test removing shopping_list item failure websocket command."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json({"id": 5, "type": "shopping_list/items/add", "name": "soda"})
    msg = await client.receive_json()
    await client.send_json({"id": 6, "type": "shopping_list/items/remove"})
    msg = await client.receive_json()
    assert msg["success"] is False
    assert len(events) == 1
    assert len(hass.data["shopping_list"].items) == 1


async def test_ws_add_category(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test adding shopping_list category websocket command."""

    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {"id": 5, "type": "shopping_list/categories/add", "name": "testAddCategory"}
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    data = msg["result"]
    assert "categories" in data
    categories = data["categories"]
    assert any(
        category["name"] == "testAddCategory" and category["predefined"] is False
        for category in categories
    )
    assert len(events) == 1

    stored_categories = hass.data[DOMAIN].categories
    assert "testAddCategory" in stored_categories


async def test_ws_add_category_fail_case_sensitivity(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test adding a duplicate category fails, ignoring case."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "shopping_list/categories/add", "name": "testAddCategory"}
    )
    await client.receive_json()
    await client.send_json(
        {"id": 2, "type": "shopping_list/categories/add", "name": "Testaddcategory"}
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert msg["id"] == 2
    assert msg["error"]["code"] == "invalid_category"


async def test_ws_add_category_fail_validation(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test invalid category names, empty or too long."""

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "shopping_list/categories/add",
            "name": "   ",  # not allowed empty names after stripping
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert msg["id"] == 1
    assert msg["error"]["code"] == "invalid_category"

    long_name = "t" * 51  # longer than allowed 50 characters
    await client.send_json(
        {"id": 2, "type": "shopping_list/categories/add", "name": long_name}
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert msg["id"] == 2
    assert msg["error"]["code"] == "invalid_category"


async def test_ws_remove_item(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test removing shopping_list item websocket command."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {"id": 5, "type": "shopping_list/items/add", "name": "soda", "category": None}
    )
    msg = await client.receive_json()
    first_item_id = msg["result"]["id"]
    await client.send_json(
        {"id": 6, "type": "shopping_list/items/add", "name": "cheese", "category": None}
    )
    msg = await client.receive_json()
    assert len(events) == 2

    items = hass.data["shopping_list"].items
    assert len(items) == 2

    await client.send_json(
        {"id": 7, "type": "shopping_list/items/remove", "item_id": first_item_id}
    )
    msg = await client.receive_json()
    assert len(events) == 3
    assert msg["success"] is True

    items = hass.data["shopping_list"].items
    assert len(items) == 1
    assert items[0]["name"] == "cheese"


async def test_ws_remove_item_fail(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test removing shopping_list item failure websocket command."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {"id": 5, "type": "shopping_list/items/add", "name": "soda", "category": None}
    )
    msg = await client.receive_json()
    await client.send_json({"id": 6, "type": "shopping_list/items/remove"})
    msg = await client.receive_json()
    assert msg["success"] is False
    assert len(events) == 1
    assert len(hass.data["shopping_list"].items) == 1


async def test_ws_reorder_items(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test reordering shopping_list items websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "apple"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    apple_id = hass.data["shopping_list"].items[2]["id"]

    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await client.send_json(
        {
            "id": 6,
            "type": "shopping_list/items/reorder",
            "item_ids": [wine_id, apple_id, beer_id],
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert len(events) == 1
    assert hass.data["shopping_list"].items[0] == {
        "id": wine_id,
        "name": "wine",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert hass.data["shopping_list"].items[1] == {
        "id": apple_id,
        "name": "apple",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert hass.data["shopping_list"].items[2] == {
        "id": beer_id,
        "name": "beer",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }

    # Mark wine as completed.
    await client.send_json(
        {
            "id": 7,
            "type": "shopping_list/items/update",
            "item_id": wine_id,
            "complete": True,
        }
    )
    _ = await client.receive_json()
    assert len(events) == 2

    await client.send_json(
        {
            "id": 8,
            "type": "shopping_list/items/reorder",
            "item_ids": [apple_id, beer_id],
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is True
    assert len(events) == 3
    assert hass.data["shopping_list"].items[0] == {
        "id": apple_id,
        "name": "apple",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert hass.data["shopping_list"].items[1] == {
        "id": beer_id,
        "name": "beer",
        "complete": False,
        "category": None,
        "quantity": None,
        "unit": None,
    }
    assert hass.data["shopping_list"].items[2] == {
        "id": wine_id,
        "name": "wine",
        "complete": True,
        "category": None,
        "quantity": None,
        "unit": None,
    }


async def test_ws_reorder_items_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test reordering shopping_list items websocket command."""
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "beer"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "wine"}}
    )
    await intent.async_handle(
        hass, "test", "HassShoppingListAddItem", {"item": {"value": "apple"}}
    )

    beer_id = hass.data["shopping_list"].items[0]["id"]
    wine_id = hass.data["shopping_list"].items[1]["id"]
    apple_id = hass.data["shopping_list"].items[2]["id"]

    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Testing sending bad item id.
    await client.send_json(
        {
            "id": 8,
            "type": "shopping_list/items/reorder",
            "item_ids": [wine_id, apple_id, beer_id, "BAD_ID"],
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert msg["error"]["code"] == ERR_NOT_FOUND
    assert len(events) == 0

    # Testing not sending all unchecked item ids.
    await client.send_json(
        {
            "id": 9,
            "type": "shopping_list/items/reorder",
            "item_ids": [wine_id, apple_id],
        }
    )
    msg = await client.receive_json()
    assert msg["success"] is False
    assert msg["error"]["code"] == ERR_INVALID_FORMAT
    assert len(events) == 0


async def test_add_item_service(hass: HomeAssistant, sl_setup) -> None:
    """Test adding shopping_list item service."""
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].items) == 1
    assert len(events) == 1


async def test_add_category_service(hass: HomeAssistant, sl_setup) -> None:
    """Test adding shopping_list category service."""
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_CATEGORY,
        {ATTR_NAME: "testCategory"},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].categories) >= 1
    assert len(events) == 1


async def test_remove_item_service(hass: HomeAssistant, sl_setup) -> None:
    """Test removing shopping_list item service."""
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "cheese"},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].items) == 2
    assert len(events) == 2

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].items) == 1
    assert hass.data[DOMAIN].items[0]["name"] == "cheese"
    assert len(events) == 3


async def test_clear_completed_items_service(hass: HomeAssistant, sl_setup) -> None:
    """Test clearing completed shopping_list items service."""
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].items) == 1
    assert len(events) == 1

    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_COMPLETE_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].items) == 1
    assert len(events) == 1

    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_COMPLETED_ITEMS,
        {},
        blocking=True,
    )
    assert len(hass.data[DOMAIN].items) == 0
    assert len(events) == 1


async def test_sort_list_service(hass: HomeAssistant, sl_setup) -> None:
    """Test sort_all service."""

    for name in ("zzz", "ddd", "aaa"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_ITEM,
            {ATTR_NAME: name},
            blocking=True,
        )

    # sort ascending
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SORT,
        {ATTR_REVERSE: False},
        blocking=True,
    )

    assert hass.data[DOMAIN].items[0][ATTR_NAME] == "aaa"
    assert hass.data[DOMAIN].items[1][ATTR_NAME] == "ddd"
    assert hass.data[DOMAIN].items[2][ATTR_NAME] == "zzz"
    assert len(events) == 1

    # sort descending
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SORT,
        {ATTR_REVERSE: True},
        blocking=True,
    )

    assert hass.data[DOMAIN].items[0][ATTR_NAME] == "zzz"
    assert hass.data[DOMAIN].items[1][ATTR_NAME] == "ddd"
    assert hass.data[DOMAIN].items[2][ATTR_NAME] == "aaa"
    assert len(events) == 2


async def test_group_by_categories_service(hass: HomeAssistant, sl_setup) -> None:
    """Test group_by_categories service."""
    # Add items with different categories
    items_with_categories = [
        {"name": "Apple", "category": "Fruit & Vegetables"},
        {"name": "Milk", "category": "Dairy"},
        {"name": "Bread", "category": "Bakery"},
        {"name": "Banana", "category": "Fruit & Vegetables"},
        {"name": "Cheese", "category": "Dairy"},
    ]

    items_without_categories = ["Mysterious Item", "Another Mystery"]

    # Add items with categories
    for item_data in items_with_categories:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_ITEM,
            {ATTR_NAME: item_data["name"], "category": item_data["category"]},
            blocking=True,
        )

    # Add items without categories (omit category field)
    for item_name in items_without_categories:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_ITEM,
            {ATTR_NAME: item_name},
            blocking=True,
        )

    # Capture events before grouping
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call group_by_categories service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_BY_CATEGORIES,
        {},
        blocking=True,
    )

    # Verify items are grouped by category and sorted within categories
    items = hass.data[DOMAIN].items
    item_names = [item[ATTR_NAME] for item in items]

    # Expected order: Bakery (Bread), Dairy (Cheese, Milk), Fruit & Vegetables (Apple, Banana), then uncategorized items (Another Mystery, Mysterious Item)
    expected_order = [
        "Bread",  # Bakery
        "Cheese",  # Dairy (alphabetically first)
        "Milk",  # Dairy (alphabetically second)
        "Apple",  # Fruit & Vegetables (alphabetically first)
        "Banana",  # Fruit & Vegetables (alphabetically second)
        "Another Mystery",  # No category (alphabetically first)
        "Mysterious Item",  # No category (alphabetically second)
    ]

    assert item_names == expected_order

    # Verify categories are in the right order
    categories = [item.get("category") for item in items]
    expected_categories = [
        "Bakery",
        "Dairy",
        "Dairy",
        "Fruit & Vegetables",
        "Fruit & Vegetables",
        "Other",
        "Other",
    ]

    assert categories == expected_categories

    # Verify event was fired
    assert len(events) == 1
    assert events[0].data["action"] == "group_by_categories"


async def test_group_by_categories_empty_list(hass: HomeAssistant, sl_setup) -> None:
    """Test group_by_categories service with empty shopping list."""
    # Capture events
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call group_by_categories service on empty list
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_BY_CATEGORIES,
        {},
        blocking=True,
    )

    # Verify list is still empty
    assert len(hass.data[DOMAIN].items) == 0

    # Verify event was still fired
    assert len(events) == 1
    assert events[0].data["action"] == "group_by_categories"


async def test_group_by_categories_single_category(
    hass: HomeAssistant, sl_setup
) -> None:
    """Test group_by_categories service with items from single category."""
    # Add items with same category
    items = ["Cheese", "Milk", "Yogurt"]
    for name in items:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_ITEM,
            {ATTR_NAME: name, "category": "Dairy"},
            blocking=True,
        )

    # Call group_by_categories service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_BY_CATEGORIES,
        {},
        blocking=True,
    )

    # Verify items are sorted alphabetically within the single category
    item_names = [item[ATTR_NAME] for item in hass.data[DOMAIN].items]
    assert item_names == ["Cheese", "Milk", "Yogurt"]

    # Verify all have same category
    categories = [item.get("category") for item in hass.data[DOMAIN].items]
    assert all(cat == "Dairy" for cat in categories)


async def test_group_by_categories_no_categories(hass: HomeAssistant, sl_setup) -> None:
    """Test group_by_categories service with items having no categories."""
    # Add items without categories (omit category field)
    items = ["Zzz Item", "Aaa Item", "Mmm Item"]
    for name in items:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_ITEM,
            {ATTR_NAME: name},
            blocking=True,
        )

    # Call group_by_categories service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GROUP_BY_CATEGORIES,
        {},
        blocking=True,
    )

    # Verify items are sorted alphabetically
    item_names = [item[ATTR_NAME] for item in hass.data[DOMAIN].items]
    assert item_names == ["Aaa Item", "Mmm Item", "Zzz Item"]

    # Verify all have no category
    categories = [item.get("category") for item in hass.data[DOMAIN].items]
    assert all(cat == "Other" for cat in categories)


async def test_async_group_by_categories_method(hass: HomeAssistant, sl_setup) -> None:
    """Test the async_group_by_categories method directly."""
    data = hass.data[DOMAIN]

    # Add items directly to the data object
    items_to_add = [
        {
            "name": "Zebra Fruit",
            "category": "Fruit & Vegetables",
            "id": "1",
            "complete": False,
            "quantity": None,
            "unit": None,
        },
        {
            "name": "Apple",
            "category": "Fruit & Vegetables",
            "id": "2",
            "complete": False,
            "quantity": None,
            "unit": None,
        },
        {
            "name": "Yogurt",
            "category": "Dairy",
            "id": "3",
            "complete": False,
            "quantity": None,
            "unit": None,
        },
        {
            "name": "Bread",
            "category": "Bakery",
            "id": "4",
            "complete": False,
            "quantity": None,
            "unit": None,
        },
        {
            "name": "Mystery",
            "category": None,
            "id": "5",
            "complete": False,
            "quantity": None,
            "unit": None,
        },
    ]

    data.items = items_to_add

    # Capture events
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call the method directly
    await data.async_group_by_categories()

    # Verify sorting: Bakery, Dairy, Fruit & Vegetables, then uncategorized
    item_names = [item["name"] for item in data.items]
    expected_order = ["Bread", "Yogurt", "Apple", "Zebra Fruit", "Mystery"]
    assert item_names == expected_order

    # Verify event was fired
    assert len(events) == 1
    assert events[0].data["action"] == "group_by_categories"


async def test_delete_all_service(hass: HomeAssistant, sl_setup) -> None:
    """Test delete_all service with multiple items."""
    # Add multiple items with different states
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "wine"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "cheese"},
        blocking=True,
    )

    # Mark one item as completed
    await hass.services.async_call(
        DOMAIN,
        SERVICE_COMPLETE_ITEM,
        {ATTR_NAME: "beer"},
        blocking=True,
    )

    # Verify we have 3 items, one completed
    assert len(hass.data[DOMAIN].items) == 3
    completed_items = [item for item in hass.data[DOMAIN].items if item["complete"]]
    assert len(completed_items) == 1

    # Capture events before delete_all
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call delete_all service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_ALL,
        {},
        blocking=True,
    )

    # Verify all items are deleted
    assert len(hass.data[DOMAIN].items) == 0

    # Verify event was fired with correct action
    assert len(events) == 1
    assert events[0].data["action"] == "delete_all"


async def test_delete_all_service_empty_list(hass: HomeAssistant, sl_setup) -> None:
    """Test delete_all service with empty shopping list."""
    # Verify list is initially empty
    assert len(hass.data[DOMAIN].items) == 0

    # Capture events
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call delete_all service on empty list
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_ALL,
        {},
        blocking=True,
    )

    # Verify list is still empty
    assert len(hass.data[DOMAIN].items) == 0

    # Verify event was still fired
    assert len(events) == 1
    assert events[0].data["action"] == "delete_all"


async def test_ws_delete_all(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test delete_all websocket command."""
    client = await hass_ws_client(hass)

    # Add multiple items via websocket
    await client.send_json(
        {"id": 1, "type": "shopping_list/items/add", "name": "soda", "category": None}
    )
    msg1 = await client.receive_json()
    assert msg1["success"] is True

    await client.send_json(
        {"id": 2, "type": "shopping_list/items/add", "name": "chips", "category": None}
    )
    msg2 = await client.receive_json()
    assert msg2["success"] is True

    await client.send_json(
        {"id": 3, "type": "shopping_list/items/add", "name": "milk", "category": None}
    )
    msg3 = await client.receive_json()
    assert msg3["success"] is True

    # Verify we have 3 items
    assert len(hass.data[DOMAIN].items) == 3

    # Capture events
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call delete_all via websocket
    await client.send_json({"id": 4, "type": "shopping_list/items/delete_all"})
    msg = await client.receive_json()

    # Verify websocket response
    assert msg["success"] is True
    assert msg["id"] == 4
    assert msg["type"] == TYPE_RESULT

    # Verify all items are deleted
    assert len(hass.data[DOMAIN].items) == 0

    # Verify event was fired
    assert len(events) == 1
    assert events[0].data["action"] == "delete_all"


async def test_ws_delete_all_empty_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, sl_setup
) -> None:
    """Test delete_all websocket command with empty list."""
    client = await hass_ws_client(hass)

    # Verify list is initially empty
    assert len(hass.data[DOMAIN].items) == 0

    # Capture events
    events = async_capture_events(hass, EVENT_SHOPPING_LIST_UPDATED)

    # Call delete_all via websocket on empty list
    await client.send_json({"id": 1, "type": "shopping_list/items/delete_all"})
    msg = await client.receive_json()

    # Verify websocket response
    assert msg["success"] is True
    assert msg["id"] == 1
    assert msg["type"] == TYPE_RESULT

    # Verify list is still empty
    assert len(hass.data[DOMAIN].items) == 0

    # Verify event was still fired
    assert len(events) == 1
    assert events[0].data["action"] == "delete_all"


async def test_delete_all_with_categories(hass: HomeAssistant, sl_setup) -> None:
    """Test delete_all service preserves categories while deleting items."""
    # Add some categories first (via service)
    await hass.services.async_call(
        DOMAIN,
        "add_category",
        {ATTR_NAME: "Custom Category"},
        blocking=True,
    )

    # Add items with categories
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "Apple", "category": "Fruit & Vegetables"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_ITEM,
        {ATTR_NAME: "Custom Item", "category": "Custom Category"},
        blocking=True,
    )

    # Get initial categories count
    initial_categories = hass.data[DOMAIN].categories.copy()

    # Verify we have items
    assert len(hass.data[DOMAIN].items) == 2

    # Delete all items
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_ALL,
        {},
        blocking=True,
    )

    # Verify items are deleted but categories remain
    assert len(hass.data[DOMAIN].items) == 0
    assert hass.data[DOMAIN].categories == initial_categories
