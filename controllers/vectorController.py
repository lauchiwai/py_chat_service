from services.vectorService import VectorService
from services.dependencies import get_vector_service
from fastapi import APIRouter, HTTPException, Depends, Security

from common.models.dto.request import GenerateCollectionRequest, VectorSearchRequest, UpsertCollectionRequest
from common.core.auth import get_current_user
from common.models.dto.resultdto import ResultDTO
from common.models.dto.response import CollectionInfo, VectorSearchResult

from typing import List

router = APIRouter(prefix="/Vector", tags=["Vector Management"])

@router.get("/get_collections", response_model=ResultDTO[List[CollectionInfo]])
def get_collections(
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO[List[CollectionInfo]]:
    """Get all collection information"""
    result = service.get_all_collections()
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)

@router.post("/collections/search", response_model=ResultDTO[List[VectorSearchResult]])
def vector_semantic_search(
    request: VectorSearchRequest, 
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO[List[VectorSearchResult]]:
    """Semantic similarity search"""
    result = service.vector_semantic_search(request)
    
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)

@router.post("/collections/upsert")
def upsert_texts(
    request: UpsertCollectionRequest,
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO:
    """Batch upsert text data"""
    result = service.upsert_texts(request)
    
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)

@router.post("/generate_collections")
def generate_collection(
    request: GenerateCollectionRequest,
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO:
    """Generate a new collection"""
    result = service.generate_collection(request)
    
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)