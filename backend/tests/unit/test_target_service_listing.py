"""Tests for TargetService: target listing (per-UC, per-user, nearby, with status filter)."""

from unittest.mock import patch

import pytest
from bson import ObjectId

from tests.unit._target_service_test_helpers import (
    _geo_db,
    _make_db,
    _make_service,
    _paginated_db,
    _uc_cursor,
)


class TestListTargetsForUserChallenge:
    @pytest.mark.asyncio
    async def test_returns_paginated_result(self):
        user_id = ObjectId()
        uc_id = ObjectId()

        db = _paginated_db(_make_db(), items=[{"_id": ObjectId()}], count=1)
        service = _make_service(db)

        result = await service.list_targets_for_user_challenge(user_id, uc_id)
        assert result["nb_items"] == 1
        assert len(result["items"]) == 1

    @pytest.mark.asyncio
    async def test_sort_ascending(self):
        db = _paginated_db(_make_db())
        service = _make_service(db)

        result = await service.list_targets_for_user_challenge(ObjectId(), ObjectId(), sort="score")
        assert result["page"] == 1


class TestListTargetsNearbyForUserChallenge:
    @pytest.mark.asyncio
    async def test_delegates_to_geonear(self):
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user_challenge(
            ObjectId(), ObjectId(), lat=48.85, lon=2.35, radius_km=5
        )
        assert "items" in result

    @pytest.mark.asyncio
    async def test_returns_items_with_distance(self):
        item = {"_id": ObjectId(), "distance_m": 1200.0}
        db = _geo_db(_make_db(), items=[item], count=1)
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user_challenge(
            ObjectId(), ObjectId(), lat=48.85, lon=2.35, radius_km=10
        )
        assert result["nb_items"] == 1
        assert result["items"][0]["distance_m"] == 1200.0


class TestListTargetsForUser:
    @pytest.mark.asyncio
    async def test_without_status_filter(self):
        db = _paginated_db(_make_db(), count=2)
        service = _make_service(db)

        result = await service.list_targets_for_user(ObjectId())
        assert result["nb_items"] == 2

    @pytest.mark.asyncio
    async def test_with_status_filter_returns_items(self):
        uc_id = ObjectId()
        db = _paginated_db(_make_db(), count=1)
        _uc_cursor(db, uc_docs=[{"_id": uc_id}])

        service = _make_service(db)
        result = await service.list_targets_for_user(ObjectId(), status_filter="accepted")
        assert "items" in result

    @pytest.mark.asyncio
    async def test_with_status_filter_no_uc_returns_empty(self):
        db = _make_db()
        _uc_cursor(db, uc_docs=[])
        service = _make_service(db)

        result = await service.list_targets_for_user(ObjectId(), status_filter="accepted")
        assert result["nb_items"] == 0
        assert result["items"] == []


class TestListTargetsNearbyForUser:
    @pytest.mark.asyncio
    async def test_uses_provided_lat_lon(self):
        db = _geo_db(_make_db())
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user(ObjectId(), lat=48.85, lon=2.35)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_raises_when_no_location_and_none_lat_lon(self):
        db = _make_db()
        service = _make_service(db)

        with patch(
            "app.services.targets.target_service.get_user_location",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="location"):
                await service.list_targets_nearby_for_user(ObjectId())

    @pytest.mark.asyncio
    async def test_uses_saved_location_when_lat_lon_none(self):
        db = _geo_db(_make_db())
        service = _make_service(db)

        with patch(
            "app.services.targets.target_service.get_user_location",
            return_value=(48.85, 2.35),
        ):
            result = await service.list_targets_nearby_for_user(ObjectId())

        assert "items" in result

    @pytest.mark.asyncio
    async def test_with_status_filter_no_uc_returns_empty(self):
        db = _make_db()
        _uc_cursor(db, uc_docs=[])
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user(
            ObjectId(), lat=48.85, lon=2.35, status_filter="accepted"
        )
        assert result["nb_items"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_with_status_filter_uc_found(self):
        uc_id = ObjectId()
        db = _geo_db(_make_db(), count=2)
        _uc_cursor(db, uc_docs=[{"_id": uc_id}])
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user(
            ObjectId(), lat=48.85, lon=2.35, status_filter="accepted"
        )
        assert result["nb_items"] == 2


class TestListTargetsNearby:
    @pytest.mark.asyncio
    async def test_returns_empty_when_count_zero(self):
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        result = await service._list_targets_nearby(
            base_filters={},
            lat=48.85,
            lon=2.35,
            radius_km=10,
            page=1,
            page_size=50,
            sort="distance",
        )
        assert result["nb_items"] == 0
        assert result["nb_pages"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_returns_correct_count_and_items(self):
        items = [{"_id": ObjectId()}, {"_id": ObjectId()}]
        db = _geo_db(_make_db(), items=items, count=2)
        service = _make_service(db)

        result = await service._list_targets_nearby(
            base_filters={},
            lat=48.85,
            lon=2.35,
            radius_km=10,
            page=1,
            page_size=50,
            sort="distance",
        )
        assert result["nb_items"] == 2
        assert len(result["items"]) == 2
        assert result["nb_pages"] == 1

    @pytest.mark.asyncio
    async def test_sort_by_distance_uses_distance_m_ascending(self):
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        await service._list_targets_nearby(
            base_filters={},
            lat=48.85,
            lon=2.35,
            radius_km=10,
            page=1,
            page_size=50,
            sort="distance",
        )

        # Second aggregate call carries the sort stage
        data_pipeline = db.targets.aggregate.call_args_list[1][0][0]
        sort_stage = next(s for s in data_pipeline if "$sort" in s)
        assert sort_stage["$sort"] == {"distance_m": 1}

    @pytest.mark.asyncio
    async def test_sort_by_descending_score(self):
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        await service._list_targets_nearby(
            base_filters={}, lat=48.85, lon=2.35, radius_km=10, page=1, page_size=50, sort="-score"
        )

        data_pipeline = db.targets.aggregate.call_args_list[1][0][0]
        sort_stage = next(s for s in data_pipeline if "$sort" in s)
        assert sort_stage["$sort"] == {"score": -1}

    @pytest.mark.asyncio
    async def test_geonear_uses_lon_lat_order(self):
        """GeoJSON coordinates must be [longitude, latitude]."""
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        lat, lon = 48.85, 2.35
        await service._list_targets_nearby(
            base_filters={}, lat=lat, lon=lon, radius_km=10, page=1, page_size=50, sort="distance"
        )

        count_pipeline = db.targets.aggregate.call_args_list[0][0][0]
        geo_stage = count_pipeline[0]["$geoNear"]
        assert geo_stage["near"]["coordinates"] == [lon, lat]

    @pytest.mark.asyncio
    async def test_radius_converted_to_meters(self):
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        await service._list_targets_nearby(
            base_filters={}, lat=48.85, lon=2.35, radius_km=5, page=1, page_size=50, sort="distance"
        )

        count_pipeline = db.targets.aggregate.call_args_list[0][0][0]
        geo_stage = count_pipeline[0]["$geoNear"]
        assert geo_stage["maxDistance"] == 5000


class TestListTargetsForUserWithStatusFilter:
    @pytest.mark.asyncio
    async def test_without_filter_skips_uc_lookup(self):
        db = _paginated_db(_make_db(), count=3)
        service = _make_service(db)

        result = await service._list_targets_for_user_with_status_filter(
            user_id=ObjectId(), status_filter=None, page=1, page_size=50, sort="-score"
        )

        db.user_challenges.find.assert_not_called()
        assert result["nb_items"] == 3

    @pytest.mark.asyncio
    async def test_with_filter_queries_uc_collection(self):
        uc_id = ObjectId()
        db = _paginated_db(_make_db(), count=1)
        _uc_cursor(db, uc_docs=[{"_id": uc_id}])

        service = _make_service(db)
        result = await service._list_targets_for_user_with_status_filter(
            user_id=ObjectId(), status_filter="accepted", page=1, page_size=50, sort="-score"
        )

        db.user_challenges.find.assert_called_once()
        assert "items" in result

    @pytest.mark.asyncio
    async def test_with_filter_no_uc_returns_early_empty(self):
        db = _make_db()
        _uc_cursor(db, uc_docs=[])

        service = _make_service(db)
        result = await service._list_targets_for_user_with_status_filter(
            user_id=ObjectId(), status_filter="accepted", page=1, page_size=50, sort="-score"
        )

        db.targets.find.assert_not_called()
        assert result == {"items": [], "nb_items": 0, "page": 1, "page_size": 50, "nb_pages": 0}


class TestListTargetsNearbyForUserWithStatusFilter:
    @pytest.mark.asyncio
    async def test_without_filter_delegates_to_geonear(self):
        db = _geo_db(_make_db(), count=0)
        service = _make_service(db)

        result = await service._list_targets_nearby_for_user_with_status_filter(
            user_id=ObjectId(),
            lat=48.85,
            lon=2.35,
            radius_km=10,
            status_filter=None,
            page=1,
            page_size=50,
            sort="distance",
        )

        db.user_challenges.find.assert_not_called()
        assert "items" in result

    @pytest.mark.asyncio
    async def test_with_filter_resolves_uc_ids(self):
        uc_id = ObjectId()
        db = _geo_db(_make_db(), count=1)
        _uc_cursor(db, uc_docs=[{"_id": uc_id}])

        service = _make_service(db)
        result = await service._list_targets_nearby_for_user_with_status_filter(
            user_id=ObjectId(),
            lat=48.85,
            lon=2.35,
            radius_km=10,
            status_filter="accepted",
            page=1,
            page_size=50,
            sort="distance",
        )

        db.user_challenges.find.assert_called_once()
        assert result["nb_items"] == 1

    @pytest.mark.asyncio
    async def test_with_filter_no_uc_returns_early_empty(self):
        db = _make_db()
        _uc_cursor(db, uc_docs=[])

        service = _make_service(db)
        result = await service._list_targets_nearby_for_user_with_status_filter(
            user_id=ObjectId(),
            lat=48.85,
            lon=2.35,
            radius_km=10,
            status_filter="accepted",
            page=1,
            page_size=50,
            sort="distance",
        )

        db.targets.aggregate.assert_not_called()
        assert result == {"items": [], "nb_items": 0, "page": 1, "page_size": 50, "nb_pages": 0}
