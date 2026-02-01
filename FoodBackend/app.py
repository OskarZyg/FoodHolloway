import dataclasses
import json
import logging
import os
import time
from typing import Optional, Dict, List

import dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from google.genai.errors import ClientError
from pydantic import BaseModel, Field, validator
from starlette.middleware.cors import CORSMiddleware

from aiintegration import AIIntegration
from emailclient import ReviewDatabase, EmailClient
from placesdatabase import PlacesDatabase, PlacesManager, FoodPlace
from searches import DataFrameFuzzySearch

dotenv.load_dotenv()
app = FastAPI()

review_database = ReviewDatabase()
email_client = EmailClient(review_database, {
    'IMAP_HOST': os.getenv('IMAP_HOST'),
    'IMAP_USERNAME': os.getenv('IMAP_USERNAME'),
    'IMAP_PASSWORD': os.getenv('IMAP_PASSWORD'),
})

sched = BackgroundScheduler()
sched.start()
sched.add_job(email_client.process_changes, 'interval', seconds=30, coalesce=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

places_database = PlacesDatabase()
places_manager = PlacesManager("data.osm.pbf", places_database.cursor)
ai_integration = AIIntegration()

# Initialize database
db = ReviewDatabase('reviews.db')

logger = logging.Logger(__name__)

@app.get("/places/{lon}/{lat}/")
def read_root(lon: float, lat: float):
    nearby_pois = places_manager.find_nearby_pois(lon, lat, 2000)

    if len(nearby_pois) == 0:
        return []



    results = (nearby_pois
               .reset_index()[['fsa_id', 'name', 'amenity', 'lat', 'lon']]
               .to_dict(orient='records')
               )

    return results

@dataclasses.dataclass
class AdvancedPoi(FoodPlace):
    cuisine: Optional[str]
    star_rating: Optional[float]
    opening_hours: Optional[str]
    vegetarian: Optional[bool]
    vegan: Optional[bool]
    description: Optional[str]

@app.get("/place/{fsa_id}")
def read_item(fsa_id: str):
    if fsa_id not in places_manager.pois.index:
        return None

    row = places_manager.pois.loc[fsa_id]  # Single brackets for Series

    tags = json.loads(row.tags)

    try:
        ai_features = ai_integration.get_node_description(tags)
    except ClientError:
        ai_features = {"cuisine": tags.get('cuisine'), "description": tags.get('description')}

    stats = db.get_subject_statistics(fsa_id)
    rating = None
    if stats is not None:
        rating = stats['average_rating']

    return AdvancedPoi(
        fsa_id,
        row['name'],
        row['amenity'],
        row['lat'],
        row['lon'],
        ai_features['cuisine'],
        rating,
        tags.get('opening_hours'),
        'diet:vegetarian' in tags and tags['diet:vegetarian'] == "yes",
        'diet:vegan' in tags and tags['diet:vegan'] == "yes",
        ai_features['description']
    )

@app.get('/search/{query}')
def search(query: str):
    searcher = DataFrameFuzzySearch(places_manager.pois, name_col='name', tags_col='tags', tag_key='cuisine')
    threshold = 70
    print(f"Search: '{query}' (threshold={threshold})")
    results = searcher.search(query, threshold=threshold)
    if results.empty:
      return []


    results = (results
               .reset_index()[['fsa_id', 'name', 'amenity', 'lat', 'lon']]
               .to_dict(orient='records')
               )

    return results


class ReviewRequestCreate(BaseModel):
    """Request model for creating a review."""
    rating: int = Field(..., ge=1, le=5, description="Rating between 1 and 5")
    review_subject: str = Field(..., min_length=1, description="Description of what is being reviewed",
                                alias="reviewSubject")

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase

    @validator('review_subject')
    def subject_not_empty(cls, v):
        if not v.strip():
            raise ValueError('review_subject cannot be empty or whitespace')
        return v.strip()


class ReviewRequestResponse(BaseModel):
    """Response model for a created review."""
    uuid: str
    fsa_id: str = Field(..., alias="fsaId")
    rating: int
    review_subject: str = Field(..., alias="reviewSubject")

    class Config:
        populate_by_name = True


class ReviewResponse(BaseModel):
    """Response model for a single review."""
    uuid: str
    rating: int
    review_subject: str = Field(..., alias="reviewSubject")
    email: str | None
    display_name: str | None = Field(None, alias="displayName")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    class Config:
        populate_by_name = True


class ReviewListResponse(BaseModel):
    """Response model for list of reviews."""
    fsa_id: str = Field(..., alias="fsaId")
    count: int
    reviews: List[ReviewResponse]

    class Config:
        populate_by_name = True


class ReviewStatsResponse(BaseModel):
    """Response model for review statistics."""
    fsa_id: str = Field(..., alias="fsaId")
    review_subject: str = Field(..., alias="reviewSubject")
    total_reviews: int = Field(..., alias="totalReviews")
    completed_reviews: int = Field(..., alias="completedReviews")
    pending_reviews: int = Field(..., alias="pendingReviews")
    average_rating: float = Field(..., alias="averageRating")
    min_rating: int = Field(..., alias="minRating")
    max_rating: int = Field(..., alias="maxRating")
    rating_distribution: Dict[int, int] = Field(..., alias="ratingDistribution")

    class Config:
        populate_by_name = True


@app.put('/place/{fsa_id}/review',
         response_model=ReviewRequestResponse,
         status_code=201,
         response_model_by_alias=True)
async def post_review_request(fsa_id: str, review_data: ReviewRequestCreate):
    """
    Create a new review request for a place/establishment.

    Args:
        fsa_id: Food Standards Agency ID or similar identifier
        review_data: JSON body containing rating and reviewSubject (or review_subject)

    Returns:
        Created review request with UUID
    """
    try:
        # Create the review request
        review_uuid = db.create_review_request(
            review_data.rating,
            review_data.review_subject
        )

        logger.info("Created review request %s for FSA ID: %s", review_uuid, fsa_id)

        return ReviewRequestResponse(
            uuid=review_uuid,
            fsa_id=fsa_id,
            rating=review_data.rating,
            review_subject=review_data.review_subject
        )

    except ValueError as e:
        logger.error("Validation error: %s", str(e))
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        logger.error("Unexpected error creating review request: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.get('/place/{fsa_id}/reviews',
         response_model=ReviewListResponse,
         response_model_by_alias=True)
async def get_reviews_for_place(fsa_id: str):
    """
    Get all reviews for a specific place/establishment.

    Args:
        fsa_id: Food Standards Agency ID or similar identifier

    Returns:
        List of reviews for the place
    """
    try:
        # In a real implementation, you might want to filter by fsa_id
        # For now, we'll use the fsa_id as the review_subject or store it separately
        reviews = db.get_reviews_by_subject_partial(fsa_id)

        return ReviewListResponse(
            fsa_id=fsa_id,
            count=len(reviews),
            reviews=[ReviewResponse(**review) for review in reviews]
        )

    except Exception as e:
        logger.error("Error retrieving reviews: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.get('/place/{fsa_id}/review/stats',
         response_model=ReviewStatsResponse,
         response_model_by_alias=True)
async def get_review_stats_for_place(fsa_id: str):
    """
    Get statistics for reviews of a specific place/establishment.

    Args:
        fsa_id: Food Standards Agency ID or similar identifier

    Returns:
        Statistics including average rating, distribution, etc.
    """
    try:
        stats = db.get_subject_statistics(fsa_id)

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No reviews found for FSA ID: {fsa_id}"
            )

        return ReviewStatsResponse(
            fsa_id=fsa_id,
            **stats
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving statistics: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


if __name__ == '__main__':
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    uvicorn.run(app, host="0.0.0.0", port=8000)