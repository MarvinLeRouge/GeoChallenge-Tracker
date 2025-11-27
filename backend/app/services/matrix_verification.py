"""Service for matrix D/T verification functionality."""

from typing import Optional, Dict, List, Tuple
from pymongo.database import Database
from bson import ObjectId
from bson.errors import InvalidId

from app.models.calendar_verification import MatrixResult, MatrixFilters


class MatrixVerificationService:
    """Service to verify user's matrix D/T completion based on found caches."""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def verify_user_matrix(
        self, 
        user_id: str, 
        filters: MatrixFilters
    ) -> MatrixResult:
        """
        Verify if user has completed matrix D/T challenge.
        
        Args:
            user_id: The user ID to check
            filters: Optional filters for cache type and size
            
        Returns:
            MatrixResult with completion status for 9x9 D/T matrix
        """
        # Resolve cache type and size names to IDs if provided
        cache_type_id = None
        cache_size_id = None
        
        if filters.cache_type_name:
            # Check if it's a valid ObjectId first
            try:
                potential_id = ObjectId(filters.cache_type_name)
                # Verify the ObjectId exists in cache_types
                cache_type = await self.db.cache_types.find_one({"_id": potential_id})
                if cache_type:
                    cache_type_id = potential_id
                else:
                    # ObjectId not found - return empty result
                    return self._empty_matrix_result(filters)
            except InvalidId:
                # Not a valid ObjectId, search by name OR code (case insensitive)
                cache_type = await self.db.cache_types.find_one({
                    "$or": [
                        {"name": {"$regex": f"^{filters.cache_type_name}$", "$options": "i"}},
                        {"code": {"$regex": f"^{filters.cache_type_name}$", "$options": "i"}}
                    ]
                })
                if cache_type:
                    cache_type_id = cache_type["_id"]
                else:
                    # Cache type name/code not found - return empty result
                    return self._empty_matrix_result(filters)
        
        if filters.cache_size_name:
            # Check if it's a valid ObjectId first
            try:
                potential_id = ObjectId(filters.cache_size_name)
                # Verify the ObjectId exists in cache_sizes
                cache_size = await self.db.cache_sizes.find_one({"_id": potential_id})
                if cache_size:
                    cache_size_id = potential_id
                else:
                    # ObjectId not found - return empty result
                    return self._empty_matrix_result(filters)
            except InvalidId:
                # Not a valid ObjectId, search by name OR code OR aliases (case insensitive)
                cache_size = await self.db.cache_sizes.find_one({
                    "$or": [
                        {"name": {"$regex": f"^{filters.cache_size_name}$", "$options": "i"}},
                        {"code": {"$regex": f"^{filters.cache_size_name}$", "$options": "i"}},
                        {"aliases": {"$regex": f"^{filters.cache_size_name}$", "$options": "i"}}
                    ]
                })
                if cache_size:
                    cache_size_id = cache_size["_id"]
                else:
                    # Cache size name/code/alias not found - return empty result
                    return self._empty_matrix_result(filters)
        
        # Build query for found caches
        query = {"user_id": ObjectId(user_id)}
        
        # Add cache filters if resolved
        cache_filter = {}
        if cache_type_id:
            cache_filter["type_id"] = cache_type_id
        if cache_size_id:
            cache_filter["size_id"] = cache_size_id
        
        # Get found caches with optional filtering
        pipeline = [
            {"$match": query},
            {
                "$lookup": {
                    "from": "caches",
                    "localField": "cache_id",
                    "foreignField": "_id",
                    "as": "cache_info"
                }
            },
            {"$unwind": "$cache_info"}
        ]
        
        # Add cache type/size filters to pipeline if needed
        if cache_filter:
            pipeline.append({"$match": {f"cache_info.{k}": v for k, v in cache_filter.items()}})
        
        # Project only needed fields
        pipeline.append({
            "$project": {
                "cache_info.difficulty": 1,
                "cache_info.terrain": 1,
                "cache_info.type_id": 1,
                "cache_info.size_id": 1
            }
        })

        found_caches = await self.db.found_caches.aggregate(pipeline).to_list(length=None)
        
        # Extract unique D/T combinations from found caches
        completed_combinations_set = set()
        dt_combinations_count = {}
        
        for found_cache in found_caches:
            cache_info = found_cache["cache_info"]
            difficulty = float(cache_info["difficulty"])
            terrain = float(cache_info["terrain"])
            
            # Round to nearest 0.5 to ensure consistency
            difficulty = round(difficulty * 2) / 2
            terrain = round(terrain * 2) / 2
            
            dt_combo = (difficulty, terrain)
            completed_combinations_set.add(dt_combo)
            
            if dt_combo in dt_combinations_count:
                dt_combinations_count[dt_combo] += 1
            else:
                dt_combinations_count[dt_combo] = 1
        
        # Generate all possible D/T combinations (9x9 matrix)
        all_combinations = self._generate_all_dt_combinations()
        all_combinations_set = set(all_combinations)
        
        # Calculate completion
        completed_count = len(completed_combinations_set.intersection(all_combinations_set))
        completion_rate = completed_count / 81
        
        # Find missing combinations
        missing_combinations_set = all_combinations_set - completed_combinations_set
        missing_combinations = [
            {"difficulty": combo[0], "terrain": combo[1]} 
            for combo in sorted(missing_combinations_set)
        ]
        
        # Group missing combinations by difficulty
        missing_combinations_by_difficulty = {}
        for combo in missing_combinations:
            difficulty_str = str(combo["difficulty"])
            if difficulty_str not in missing_combinations_by_difficulty:
                missing_combinations_by_difficulty[difficulty_str] = []
            missing_combinations_by_difficulty[difficulty_str].append({"terrain": combo["terrain"]})
        
        # Format completed combinations with counts
        completed_combinations = [
            {
                "difficulty": combo[0], 
                "terrain": combo[1], 
                "count": dt_combinations_count[combo]
            } 
            for combo in sorted(completed_combinations_set)
        ]
        
        # Use the filter names directly (already resolved above)
        cache_type_name = filters.cache_type_name if cache_type_id else None
        cache_size_name = filters.cache_size_name if cache_size_id else None
        
        return MatrixResult(
            completed_combinations=completed_count,
            completion_rate=completion_rate,
            missing_combinations=missing_combinations,
            missing_combinations_by_difficulty=missing_combinations_by_difficulty,
            completed_combinations_details=completed_combinations,
            cache_type_filter=cache_type_name,
            cache_size_filter=cache_size_name
        )
    
    def _generate_all_dt_combinations(self) -> List[Tuple[float, float]]:
        """
        Generate list of all D/T combinations for 9x9 matrix.
        
        Returns:
            List of (difficulty, terrain) tuples from 1.0 to 5.0 by 0.5
        """
        combinations = []
        
        for difficulty in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
            for terrain in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
                combinations.append((difficulty, terrain))
        
        return combinations
    
    def _empty_matrix_result(self, filters: MatrixFilters) -> MatrixResult:
        """
        Return empty matrix result when filters don't match any cache types/sizes.
        
        Args:
            filters: The applied filters
            
        Returns:
            MatrixResult with zero completions
        """
        all_combinations = self._generate_all_dt_combinations()
        missing_combinations = [
            {"difficulty": combo[0], "terrain": combo[1]} 
            for combo in all_combinations
        ]
        
        # Group all combinations as missing by difficulty
        missing_combinations_by_difficulty = {}
        for combo in missing_combinations:
            difficulty_str = str(combo["difficulty"])
            if difficulty_str not in missing_combinations_by_difficulty:
                missing_combinations_by_difficulty[difficulty_str] = []
            missing_combinations_by_difficulty[difficulty_str].append({"terrain": combo["terrain"]})
        
        return MatrixResult(
            completed_combinations=0,
            completion_rate=0.0,
            missing_combinations=missing_combinations,
            missing_combinations_by_difficulty=missing_combinations_by_difficulty,
            completed_combinations_details=[],
            cache_type_filter=filters.cache_type_name,
            cache_size_filter=filters.cache_size_name
        )