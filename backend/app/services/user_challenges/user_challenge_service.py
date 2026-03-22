# backend/app/services/user_challenges/user_challenge_service.py
# Main UserChallenge management service with dependency injection.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import utcnow

from .status_calculator import StatusCalculator
from .user_challenge_query import UserChallengeQuery
from .user_challenge_sync import UserChallengeSync
from .user_challenge_validator import UserChallengeValidator


class UserChallengeService:
    """Main UserChallenge management service.

    Description:
        Orchestrates synchronization, queries, validation, and updates
        for UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the service.

        Args:
            db: MongoDB database instance.
        """
        self.db = db

        # Initialize components
        self.status_calculator = StatusCalculator()
        self.sync_service = UserChallengeSync(db)
        self.query_service = UserChallengeQuery(db)
        self.validator = UserChallengeValidator(db)

    async def sync_user_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Create and synchronize UserChallenges for a user.

        Args:
            user_id: User identifier.

        Returns:
            dict: Synchronization statistics.
        """
        return await self.sync_service.sync_user_challenges(user_id)

    async def list_user_challenges(
        self,
        user_id: ObjectId,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """List UserChallenges with pagination and filtering.

        Args:
            user_id: User identifier.
            status_filter: Status filter ('pending', 'accepted', 'dismissed', 'completed').
            page: Page number (1-based).
            page_size: Page size.

        Returns:
            dict: Paginated results with metadata.
        """
        return await self.query_service.list_user_challenges(
            user_id=user_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

    async def get_user_challenge_detail(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> dict[str, Any] | None:
        """Retrieve the full detail of a UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            dict | None: Enriched detail or None if not found.
        """
        return await self.query_service.get_user_challenge_detail(user_id, uc_id)

    async def patch_user_challenge(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        patch_data: dict[str, Any],
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Update a UserChallenge with validation.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            patch_data: Patch data.

        Returns:
            tuple: (success, error_message, updated_uc).
        """
        # Validation
        is_valid, error_msg, validated_data = await self.validator.validate_patch_operation(
            user_id, uc_id, patch_data
        )
        if not is_valid:
            return False, error_msg, None

        # Retrieve dependencies
        dependencies = await self.validator.get_patch_dependencies(user_id, uc_id)
        current_uc = dependencies.get("current_uc", {})

        # Prepare update data
        update_data = self._prepare_patch_update(validated_data, current_uc, dependencies)

        # Apply the update
        success = await self._apply_patch_update(user_id, uc_id, update_data)
        if not success:
            return False, "Failed to update UserChallenge", None

        # Retrieve the updated UC
        updated_uc = await self.get_user_challenge_detail(user_id, uc_id)

        return True, None, updated_uc

    async def bulk_update_status(
        self,
        user_id: ObjectId,
        uc_ids: list[ObjectId],
        new_status: str,
    ) -> dict[str, Any]:
        """Update the status of multiple UserChallenges.

        Args:
            user_id: User identifier.
            uc_ids: List of UserChallenge identifiers.
            new_status: New status to apply.

        Returns:
            dict: Bulk operation result.
        """
        # Validation
        is_valid, error_msg, valid_ids = await self.validator.validate_bulk_operation(
            user_id, uc_ids, new_status
        )
        if not is_valid:
            return {"success": False, "error": error_msg, "updated": 0}

        # Prepare the update
        now = utcnow()
        update_doc = {
            "status": new_status,
            "updated_at": now,
        }

        # Add status-specific fields
        if new_status == "completed":
            update_doc["manual_override"] = True
            update_doc["override_reason"] = "Manual completion"
            update_doc["overridden_at"] = now
            # Create a progress snapshot
            update_doc["progress"] = self.status_calculator.create_progress_snapshot(100.0)

        # Apply the bulk update
        coll_ucs = self.db.user_challenges
        result = await coll_ucs.update_many(
            {"_id": {"$in": valid_ids}, "user_id": user_id}, {"$set": update_doc}
        )

        return {
            "success": True,
            "updated": result.modified_count,
            "requested": len(valid_ids),
        }

    async def reset_user_challenge(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> tuple[bool, str | None]:
        """Reset a UserChallenge to its default state.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            tuple: (success, error_message).
        """
        # Validate ownership
        if not await self.validator.validate_ownership(user_id, uc_id):
            return False, "UserChallenge not found or not owned"

        # Apply the reset
        success = await self.sync_service.reset_user_challenge_status(user_id, uc_id)

        return success, None if success else "Failed to reset UserChallenge"

    def _prepare_patch_update(
        self,
        validated_data: dict[str, Any],
        current_uc: dict[str, Any],
        dependencies: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare update data for a patch operation.

        Args:
            validated_data: Validated patch data.
            current_uc: Current UserChallenge document.
            dependencies: Contextual dependencies.

        Returns:
            dict: MongoDB update data.
        """
        now = utcnow()
        update_data = {
            "updated_at": now,
        }

        # Copy validated fields
        for field in ["status", "notes", "manual_override", "override_reason"]:
            if field in validated_data:
                if validated_data[field] is None:
                    update_data.setdefault("$unset", {})[field] = ""
                else:
                    update_data[field] = validated_data[field]

        # Handle override logic
        new_status = validated_data.get("status")
        computed_status = dependencies.get("computed_status")

        if new_status:
            is_override, override_type = self.status_calculator.determine_override_logic(
                new_status, computed_status
            )

            if is_override:
                update_data["manual_override"] = True
                update_data["overridden_at"] = now
                if override_type == "manual_completion":
                    update_data["override_reason"] = "Manual completion"
                    # Create a progress snapshot
                    update_data["progress"] = self.status_calculator.create_progress_snapshot(100.0)

        # Auto-complete if applicable
        if dependencies.get("can_auto_complete") and not current_uc.get("computed_status"):
            update_data["computed_status"] = "completed"
            update_data["progress"] = self.status_calculator.create_progress_snapshot(100.0)

        return update_data

    async def _apply_patch_update(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        update_data: dict[str, Any],
    ) -> bool:
        """Apply a MongoDB update.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            update_data: Update data.

        Returns:
            bool: True if the update succeeded.
        """
        coll_ucs = self.db.user_challenges

        # Separate $set and $unset
        set_data = {k: v for k, v in update_data.items() if k != "$unset"}
        unset_data = update_data.get("$unset", {})

        # Build the update query
        update_query = {}
        if set_data:
            update_query["$set"] = set_data
        if unset_data:
            update_query["$unset"] = unset_data

        result = await coll_ucs.update_one({"_id": uc_id, "user_id": user_id}, update_query)

        return result.modified_count > 0
