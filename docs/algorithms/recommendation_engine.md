## docs/algorithms/recommendation_engine.md

```markdown
# Recommendation Engine

## Overview

The Queue Me Recommendation Engine powers personalized content discovery across the platform. It intelligently suggests shops, specialists, services, and content (reels/stories) to customers based on their preferences, behavior, and contextual factors.

## Architecture

The recommendation engine follows a multi-layered architecture combining several algorithmic approaches:

1. **Content-Based Filtering**: Recommending items similar to what a user has liked in the past
2. **Collaborative Filtering**: Recommending items liked by similar users
3. **Contextual Boosting**: Adjusting recommendations based on real-time context
4. **Geospatial Proximity**: Prioritizing nearby options
5. **Hybrid Ranking**: Combining multiple signals into a final score

## Core Components

### 1. User Preference Extraction

The engine builds a comprehensive user preference profile by analyzing:

- Booking history (services, specialists, and shops)
- Favorite items (explicitly saved by the user)
- Content interactions (views, likes, comments)
- Time preferences (when they typically book)
- Location data (for proximity-based recommendations)

### 2. Personalized "For You" Feed Generator

The heart of the recommendation system is the algorithm that generates personalized content feeds.

### 3. Specialist Recommendation Algorithm

The engine recommends specialists based on user preferences and specialist attributes:

```python
def recommend_specialists(customer_id, service_id=None):
    # Get customer and their preferences
    customer = User.objects.get(id=customer_id)
    preferences = extract_customer_preferences(customer_id)

    # Filter by city
    specialists = Specialist.objects.filter(
        employee__shop__location__city=customer.city,
        is_active=True
    ).select_related('employee', 'employee__shop')

    # Filter by service if specified
    if service_id:
        specialists = specialists.filter(
            specialist_services__service_id=service_id
        )

    # Score and rank specialists
    scored_specialists = []
    for specialist in specialists:
        score = calculate_specialist_score(specialist, customer, preferences)
        scored_specialists.append({
            'specialist': specialist,
            'score': score
        })

    # Sort by score (descending)
    scored_specialists.sort(key=lambda x: x['score'], reverse=True)

    return [s['specialist'] for s in scored_specialists]
