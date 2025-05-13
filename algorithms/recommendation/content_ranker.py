"""
Advanced Content Ranking Algorithm

This module provides sophisticated recommendation algorithms that consider:
1. Content-based filtering (category and attribute matching)
2. Collaborative filtering signals (engagement patterns)
3. Contextual factors (time, location)
4. Diversity enforcement
"""

import logging
import math
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def weighted_content_ranking(
    content_items: List[Dict[str, Any]],
    user_preferences: Optional[Dict[str, float]] = None,
    content_freshness_weight: float = 0.25,
    content_engagement_weight: float = 0.25,
    category_match_weight: float = 0.3,
    diversity_weight: float = 0.2,
    time_decay_factor: float = 0.05,
    return_scores: bool = False,
) -> List[Any]:
    """
    Rank content items based on multiple weighted factors and user preferences.

    Args:
        content_items: List of content items to rank, each with at least:
                      - id: unique identifier
                      - category_ids: list of category IDs
                      - engagement_score: measure of popularity/engagement
                      - freshness: recency score (0-1 typically)
        user_preferences: Dict mapping category IDs to preference weights (0-1)
        content_freshness_weight: Weight for recency factor (0-1)
        content_engagement_weight: Weight for engagement/popularity factor (0-1)
        category_match_weight: Weight for content-user preference matching (0-1)
        diversity_weight: Weight for diversity promotion (0-1)
        time_decay_factor: Controls how quickly older content loses relevance
        return_scores: If True, return tuples of (item_id, score)

    Returns:
        List of content item IDs in ranked order, or (item_id, score) if return_scores=True
    """
    if not content_items:
        return []

    # Ensure weights are valid
    total_weight = (
        content_freshness_weight
        + content_engagement_weight
        + category_match_weight
        + diversity_weight
    )

    if not math.isclose(total_weight, 1.0, abs_tol=0.01):
        logger.warning(f"Weights don't sum to 1.0 (sum={total_weight}). Normalizing.")
        factor = 1.0 / total_weight
        content_freshness_weight *= factor
        content_engagement_weight *= factor
        category_match_weight *= factor
        diversity_weight *= factor

    # Default user preferences if None
    if user_preferences is None:
        user_preferences = {}

    try:
        # Stage 1: Calculate base scores
        scored_items = []
        already_seen_categories = set()  # For diversity tracking

        for item in content_items:
            try:
                item_id = item.get("id")
                if not item_id:
                    continue  # Skip items without id

                # 1. Freshness component
                freshness_score = item.get("freshness", 0.5)

                # Apply time decay if not already factored into freshness
                if "created_at" in item and time_decay_factor > 0:
                    # Calculate days since creation if we have actual dates
                    if isinstance(item["created_at"], (datetime, str)):
                        if isinstance(item["created_at"], str):
                            try:
                                created_at = datetime.fromisoformat(item["created_at"])
                            except ValueError:
                                created_at = datetime.now()  # Fallback
                        else:
                            created_at = item["created_at"]

                        days_old = (datetime.now() - created_at).days
                        time_decay = math.exp(-time_decay_factor * days_old)
                        freshness_score *= time_decay

                # 2. Engagement component
                engagement_score = item.get("engagement_score", 0.0)
                # Normalize to 0-1 range (assuming most engagements will be under 100)
                normalized_engagement = min(1.0, engagement_score / 100.0)

                # 3. Category match component
                category_match_score = 0.0
                item_categories = item.get("category_ids", [])

                if item_categories and user_preferences:
                    # Calculate the average preference score across matching categories
                    matching_prefs = [
                        user_preferences.get(cat_id, 0.0)
                        for cat_id in item_categories
                        if cat_id in user_preferences
                    ]

                    if matching_prefs:
                        category_match_score = sum(matching_prefs) / len(matching_prefs)
                    else:
                        # Default score for items with no category matches
                        category_match_score = 0.1
                else:
                    # Default score for items with no categories
                    category_match_score = 0.2

                # 4. Diversity component
                diversity_score = 1.0  # Default full score

                # Penalize items from categories we've already seen
                overlap = set(item_categories).intersection(already_seen_categories)
                if overlap:
                    # Decrease score based on how many categories we've already seen
                    diversity_score = max(0.1, 1.0 - (len(overlap) / max(1, len(item_categories))))

                # Update seen categories set for future items
                already_seen_categories.update(item_categories)

                # 5. Calculate final weighted score
                final_score = (
                    freshness_score * content_freshness_weight
                    + normalized_engagement * content_engagement_weight
                    + category_match_score * category_match_weight
                    + diversity_score * diversity_weight
                )

                # Add small random factor to avoid identical scores (tie-breaking)
                jitter = random.uniform(0, 0.01)
                final_score += jitter

                scored_items.append((item_id, final_score))

            except Exception as e:
                logger.error(f"Error scoring item {item.get('id', 'unknown')}: {str(e)}")
                continue

        # Sort by final score (descending)
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # Stage 2: Apply post-processing
        # Add a few high-diversity picks to prevent homogeneity
        if len(scored_items) > 10:
            # Insert some diverse picks to avoid filter bubbles
            # This simulates the "discovery" effect that recommendation systems need
            pass  # Implementation would depend on business needs

        if return_scores:
            return scored_items
        else:
            return [item[0] for item in scored_items]

    except Exception as e:
        logger.error(f"Error in content ranking algorithm: {str(e)}")
        # Fallback to simple ordering by engagement
        try:
            return [
                item.get("id")
                for item in sorted(
                    content_items,
                    key=lambda x: x.get("engagement_score", 0.0),
                    reverse=True,
                )
            ]
        except Exception as ex:
            # Ultimate fallback - just return IDs as is
            return [item.get("id") for item in content_items if item.get("id")]


def collaborative_filtering_boost(
    content_items: List[Dict[str, Any]],
    user_id: str,
    similar_users: Optional[List[Tuple[str, float]]] = None,
    user_item_interactions: Optional[Dict[str, List[str]]] = None,
    boost_factor: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Apply collaborative filtering to boost content engagement scores.

    Args:
        content_items: List of content items to rank
        user_id: ID of the current user
        similar_users: List of (user_id, similarity_score) tuples for similar users
        user_item_interactions: Dict mapping user IDs to lists of item IDs they interacted with
        boost_factor: How much to boost scores (0-1)

    Returns:
        List of content items with adjusted engagement scores
    """
    if not similar_users or not user_item_interactions:
        return content_items

    # Create a map of item_id -> original item for fast lookup
    item_map = {item["id"]: item for item in content_items if "id" in item}

    # Get items the current user has already interacted with
    user_items = set(user_item_interactions.get(user_id, []))

    # Collect items from similar users, weighted by similarity
    item_scores = {}
    for similar_user_id, similarity in similar_users:
        if similar_user_id == user_id:
            continue  # Skip self

        # Get items this similar user has interacted with
        similar_user_items = user_item_interactions.get(similar_user_id, [])

        # Score each item based on similarity
        for item_id in similar_user_items:
            if item_id in user_items:
                continue  # Skip already interacted items

            if item_id not in item_map:
                continue  # Skip items not in our content pool

            if item_id not in item_scores:
                item_scores[item_id] = 0.0

            item_scores[item_id] += similarity

    # Normalize scores
    if item_scores:
        max_score = max(item_scores.values())
        if max_score > 0:
            for item_id in item_scores:
                item_scores[item_id] /= max_score

    # Apply the collaborative filtering boost to engagement scores
    boosted_items = []
    for item in content_items:
        item_id = item.get("id")
        if not item_id:
            boosted_items.append(item)
            continue

        # Copy the item to avoid modifying the original
        boosted_item = dict(item)

        # Apply the boost if this item was recommended by similar users
        if item_id in item_scores:
            cf_score = item_scores[item_id]
            current_engagement = boosted_item.get("engagement_score", 0.0)

            # Boost the engagement score
            boosted_engagement = current_engagement * (1.0 + (cf_score * boost_factor))
            boosted_item["engagement_score"] = boosted_engagement
            boosted_item["cf_boosted"] = True  # Mark as boosted for tracking

        boosted_items.append(boosted_item)

    return boosted_items


def diversity_reranker(
    ranked_items: List[Any],
    item_attributes: Dict[str, List[str]],
    diversity_threshold: float = 0.3,
) -> List[Any]:
    """
    Re-rank a list of items to increase diversity while preserving relevance.

    Args:
        ranked_items: List of item IDs or (item_id, score) tuples in ranked order
        item_attributes: Dict mapping item IDs to lists of attribute values
        diversity_threshold: How much diversity to enforce (0-1)

    Returns:
        Re-ranked list of items with improved diversity
    """
    if not ranked_items or not item_attributes:
        return ranked_items

    try:
        # Determine if we're dealing with (id, score) tuples or just ids
        has_scores = isinstance(ranked_items[0], tuple) and len(ranked_items[0]) == 2

        # Extract items and scores
        if has_scores:
            items = [(item[0], item[1]) for item in ranked_items]
        else:
            items = [(item, 1.0 - (i * 0.01)) for i, item in enumerate(ranked_items)]

        reranked = []
        seen_attributes = set()

        # Take the top item first
        if items:
            top_item = items.pop(0)
            reranked.append(top_item)
            item_id = top_item[0]

            # Add its attributes to seen set
            for attr in item_attributes.get(item_id, []):
                seen_attributes.add(attr)

        # Re-rank the rest based on diversity and original rank
        while items:
            # Calculate diversity scores
            diversity_scores = []

            for i, (item_id, original_score) in enumerate(items):
                # Calculate uniqueness of this item (how many new attributes)
                item_attrs = set(item_attributes.get(item_id, []))
                new_attrs = item_attrs - seen_attributes

                if item_attrs:
                    uniqueness = len(new_attrs) / len(item_attrs)
                else:
                    uniqueness = 0.0

                # Final score combines original relevance with diversity
                final_score = (
                    original_score * (1.0 - diversity_threshold) + uniqueness * diversity_threshold
                )

                diversity_scores.append((i, final_score))

            # Sort by final score and pick the best
            diversity_scores.sort(key=lambda x: x[1], reverse=True)
            best_index = diversity_scores[0][0]

            # Get the chosen item
            chosen_item = items.pop(best_index)
            reranked.append(chosen_item)

            # Update seen attributes
            item_id = chosen_item[0]
            for attr in item_attributes.get(item_id, []):
                seen_attributes.add(attr)

        # Return in same format as input
        if has_scores:
            return reranked
        else:
            return [item[0] for item in reranked]

    except Exception as e:
        logger.error(f"Error in diversity reranker: {str(e)}")
        return ranked_items
