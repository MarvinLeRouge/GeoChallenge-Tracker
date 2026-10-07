# backend/app/services/user_challenges/user_challenge_validator.py
# Validation service for UserChallenge operations.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from .status_calculator import StatusCalculator


class UserChallengeValidator:
    """Validation service for UserChallenges.

    Description:
        Responsible for validating patch operations, status transitions,
        and data consistency for UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the validation service.

        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.status_calculator = StatusCalculator()

    def _validate_status_field(
        self, current_uc: dict[str, Any], patch_data: dict[str, Any], validated_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate and apply the `status` field of a patch, if present.

        Args:
            current_uc: The current UserChallenge document.
            patch_data: Patch data.
            validated_data: Output dict, mutated in place on success.

        Returns:
            tuple[bool, str | None]: `(is_valid, error_message)`.
        """
        if "status" not in patch_data:
            return True, None

        new_status = patch_data["status"]
        is_valid, error_msg = self.status_calculator.validate_status_transition(
            current_uc.get("status"),
            new_status,
            current_uc.get("computed_status"),
        )
        if not is_valid:
            return False, error_msg

        validated_data["status"] = new_status
        return True, None

    @staticmethod
    def _validate_notes_field(
        patch_data: dict[str, Any], validated_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate and apply the `notes` field of a patch, if present.

        Args:
            patch_data: Patch data.
            validated_data: Output dict, mutated in place on success.

        Returns:
            tuple[bool, str | None]: `(is_valid, error_message)`.
        """
        if "notes" not in patch_data:
            return True, None

        notes = patch_data["notes"]
        if notes is None:
            validated_data["notes"] = None
            return True, None

        if not isinstance(notes, str):
            return False, "Notes must be a string"
        if len(notes) > 2000:
            return False, "Notes too long (max 2000 characters)"
        validated_data["notes"] = notes.strip() if notes.strip() else None
        return True, None

    @staticmethod
    def _validate_manual_override_field(
        patch_data: dict[str, Any], validated_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate and apply the `manual_override` field of a patch, if present.

        Args:
            patch_data: Patch data.
            validated_data: Output dict, mutated in place on success.

        Returns:
            tuple[bool, str | None]: `(is_valid, error_message)`.
        """
        if "manual_override" not in patch_data:
            return True, None

        override_value = patch_data["manual_override"]
        if not isinstance(override_value, bool):
            return False, "manual_override must be a boolean"
        validated_data["manual_override"] = override_value
        return True, None

    @staticmethod
    def _validate_override_reason_field(
        patch_data: dict[str, Any], validated_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate and apply the `override_reason` field of a patch, if present.

        Args:
            patch_data: Patch data.
            validated_data: Output dict, mutated in place on success.

        Returns:
            tuple[bool, str | None]: `(is_valid, error_message)`.
        """
        if "override_reason" not in patch_data:
            return True, None

        reason = patch_data["override_reason"]
        if reason is None:
            validated_data["override_reason"] = None
            return True, None

        if not isinstance(reason, str):
            return False, "override_reason must be a string"
        if len(reason) > 500:
            return False, "Override reason too long (max 500 characters)"
        validated_data["override_reason"] = reason.strip() if reason.strip() else None
        return True, None

    async def validate_patch_operation(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        patch_data: dict[str, Any],
    ) -> tuple[bool, str | None, dict[str, Any]]:
        """Validate a patch operation on a UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            patch_data: Patch data to validate.

        Returns:
            tuple: (is_valid, error_message, validated_data).
        """
        # Retrieve the existing UC
        current_uc = await self._get_user_challenge(user_id, uc_id)
        if not current_uc:
            return False, "UserChallenge not found", {}

        # Validate allowed fields
        allowed_fields = {"status", "notes", "manual_override", "override_reason"}
        invalid_fields = set(patch_data.keys()) - allowed_fields
        if invalid_fields:
            return False, f"Invalid fields: {', '.join(invalid_fields)}", {}

        validated_data: dict[str, Any] = {}

        is_valid, error_msg = self._validate_status_field(current_uc, patch_data, validated_data)
        if not is_valid:
            return False, error_msg, {}

        is_valid, error_msg = self._validate_notes_field(patch_data, validated_data)
        if not is_valid:
            return False, error_msg, {}

        is_valid, error_msg = self._validate_manual_override_field(patch_data, validated_data)
        if not is_valid:
            return False, error_msg, {}

        is_valid, error_msg = self._validate_override_reason_field(patch_data, validated_data)
        if not is_valid:
            return False, error_msg, {}

        return True, None, validated_data

    async def validate_ownership(self, user_id: ObjectId, uc_id: ObjectId) -> bool:
        """Validate that the user owns the given UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            bool: True if the user owns the UC.
        """
        current_uc = await self._get_user_challenge(user_id, uc_id)
        return current_uc is not None

    async def validate_bulk_operation(
        self,
        user_id: ObjectId,
        uc_ids: list[ObjectId],
        operation_type: str,
    ) -> tuple[bool, str | None, list[ObjectId]]:
        """Validate a bulk operation on UserChallenges.

        Args:
            user_id: User identifier.
            uc_ids: List of UserChallenge identifiers.
            operation_type: Operation type ('dismiss', 'accept', 'reset').

        Returns:
            tuple: (is_valid, error_message, valid_uc_ids).
        """
        if not uc_ids:
            return False, "No UserChallenge IDs provided", []

        if len(uc_ids) > 100:
            return False, "Too many UserChallenges (max 100)", []

        valid_operations = {"dismiss", "accept", "reset", "complete"}
        if operation_type not in valid_operations:
            return False, f"Invalid operation: {operation_type}", []

        # Verify that all UCs belong to the user
        coll_ucs = self.db.user_challenges
        existing_count = await coll_ucs.count_documents(
            {
                "_id": {"$in": uc_ids},
                "user_id": user_id,
            }
        )

        if existing_count != len(uc_ids):
            return False, "Some UserChallenges not found or not owned", []

        return True, None, uc_ids

    async def get_patch_dependencies(self, user_id: ObjectId, uc_id: ObjectId) -> dict[str, Any]:
        """Retrieve the dependencies needed for a patch operation.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            dict: Context data for the patch.
        """
        current_uc = await self._get_user_challenge(user_id, uc_id)
        if not current_uc:
            return {}

        # Check whether the challenge's cache has been found
        challenge_id = current_uc.get("challenge_id")
        if not isinstance(challenge_id, ObjectId):
            challenge_cache_found = False
        else:
            challenge_cache_found = await self._is_challenge_cache_found(user_id, challenge_id)

        return {
            "current_uc": current_uc,
            "challenge_cache_found": challenge_cache_found,
            "can_auto_complete": challenge_cache_found,
            "computed_status": self.status_calculator.should_auto_complete(challenge_cache_found),
        }

    async def _get_user_challenge(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> dict[str, Any] | None:
        """Retrieve a specific UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            dict | None: UserChallenge or None if not found.
        """
        coll_ucs = self.db.user_challenges
        return await coll_ucs.find_one({"_id": uc_id, "user_id": user_id})

    async def _is_challenge_cache_found(self, user_id: ObjectId, challenge_id: ObjectId) -> bool:
        """Check whether the challenge's cache has been found by the user.

        Args:
            user_id: User identifier.
            challenge_id: Challenge identifier.

        Returns:
            bool: True if the cache has been found.
        """
        # Retrieve the challenge's cache ID
        coll_challenges = self.db.challenges
        challenge = await coll_challenges.find_one({"_id": challenge_id}, {"cache_id": 1})
        if not challenge or not challenge.get("cache_id"):
            return False

        # Check whether it has been found
        coll_found = self.db.found_caches
        found = await coll_found.find_one(
            {
                "user_id": user_id,
                "cache_id": challenge["cache_id"],
            }
        )

        return found is not None
