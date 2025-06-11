from services.vectorService import VectorService
from services.dependencies import get_vector_service
from fastapi import APIRouter, HTTPException, Depends, Security

from common.models.request.vectorRequest import CheckVectorDataExistRequest, DeleteVectorDataRequest, GenerateCollectionRequest, VectorSearchRequest, UpsertCollectionRequest
from common.core.auth import get_current_user
from common.models.dto.resultdto import ResultDTO
from common.models.response.vectorResponse import CollectionInfo, VectorSearchResult

from typing import List

router = APIRouter(prefix="/Vector", tags=["Vector Management"])

@router.get("/get_collections", response_model=ResultDTO[List[CollectionInfo]])
async def get_collections(
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO[List[CollectionInfo]]:
    """Get all collection information"""
    result = await service.get_all_collections()
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)
    
@router.post("/check_vector_data_exist", response_model=ResultDTO[bool])
async def check_vector_data_exist(
    request: CheckVectorDataExistRequest, 
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]),
) -> ResultDTO[List[CollectionInfo]]:
    """check vector data exist"""
    result = await service.check_vector_data_exist(request)
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)
    
@router.delete("/delete_vector_data", response_model=ResultDTO)
async def delete_vector_data(
    request: DeleteVectorDataRequest, 
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]),
) -> ResultDTO[List[CollectionInfo]]:
    """delete vector data"""
    result = await service.delete_vector_data(request)
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)

@router.post("/collections/search", response_model=ResultDTO[List[VectorSearchResult]])
async def vector_semantic_search(
    request: VectorSearchRequest, 
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO[List[VectorSearchResult]]:
    """Semantic similarity search"""
    result = await service.vector_semantic_search(request)
    
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)

@router.post("/collections/upsert")
async def upsert_texts(
    request: UpsertCollectionRequest,
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO:
    """Batch upsert text data"""
    result = await service.upsert_texts(request)
    
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)

@router.post("/generate_collections")
async def generate_collection(
    request: GenerateCollectionRequest,
    service: VectorService = Depends(get_vector_service),
    user_payload: dict = Security(get_current_user, scopes=["authenticated"]) 
) -> ResultDTO:
    """Generate a new collection"""
    result = await service.generate_collection(request)
    
    if result.code == 200:
        return result
    else:
        raise HTTPException(status_code=result.code, detail=result.message)