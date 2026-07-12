from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID

# =====================================
# Division Schemas
# =====================================

class DivisionBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

class DivisionCreate(DivisionBase):
    pass

class DivisionUpdate(DivisionBase):
    pass

class DivisionResponse(DivisionBase):
    id: UUID

    class Config:
        from_attributes = True

# =====================================
# SubDivision Schemas
# =====================================

class SubDivisionBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

class SubDivisionCreate(SubDivisionBase):
    division_id: UUID

class SubDivisionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    division_id: Optional[UUID] = None

class SubDivisionResponse(SubDivisionBase):
    id: UUID
    division: Optional[DivisionResponse] = None

    class Config:
        from_attributes = True

class DivisionWithSubdivisionsResponse(DivisionResponse):
    subdivisions: List[SubDivisionResponse] = []