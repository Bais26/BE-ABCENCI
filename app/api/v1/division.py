from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.models.division import Division, SubDivision
from app.schemas.division import (
    DivisionCreate, DivisionUpdate, DivisionResponse,
    SubDivisionCreate, SubDivisionUpdate, SubDivisionResponse,
    DivisionWithSubdivisionsResponse
)
from app.utils.security import get_current_admin
from app.models.user import User

router = APIRouter(tags=["Divisions & Subdivisions"], dependencies=[Depends(get_current_admin)])

# =====================================
# CRUD for Divisions
# =====================================

@router.post("/divisions", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
def create_division(
    division_data: DivisionCreate,
    db: Session = Depends(get_db)
):
    """Admin: Create a new division."""
    existing_division = db.query(Division).filter(Division.name.ilike(division_data.name)).first()
    if existing_division:
        raise HTTPException(status_code=400, detail=f"Division '{division_data.name}' already exists.")
    
    new_division = Division(**division_data.model_dump())
    db.add(new_division)
    db.commit()
    db.refresh(new_division)
    return new_division

@router.get("/divisions", response_model=List[DivisionWithSubdivisionsResponse])
def get_all_divisions(db: Session = Depends(get_db)):
    """Admin: Get all divisions along with their subdivisions."""
    return db.query(Division).options(joinedload(Division.subdivisions)).order_by(Division.name).all()

@router.put("/divisions/{division_id}", response_model=DivisionResponse)
def update_division(
    division_id: UUID,
    division_data: DivisionUpdate,
    db: Session = Depends(get_db)
):
    """Admin: Update a division's name."""
    division = db.query(Division).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found.")
    
    # Check if new name already exists
    if division_data.name != division.name:
        existing = db.query(Division).filter(Division.name.ilike(division_data.name)).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Division name '{division_data.name}' already in use.")
            
    division.name = division_data.name
    db.commit()
    db.refresh(division)
    return division

@router.delete("/divisions/{division_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_division(
    division_id: UUID,
    db: Session = Depends(get_db)
):
    """Admin: Delete a division. Fails if it has subdivisions linked."""
    division = db.query(Division).options(joinedload(Division.subdivisions)).filter(Division.id == division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found.")
    
    if division.subdivisions:
        raise HTTPException(status_code=400, detail="Cannot delete division. It has associated subdivisions. Please delete them first.")
        
    db.delete(division)
    db.commit()
    return None

# =====================================
# CRUD for Subdivisions
# =====================================

@router.post("/subdivisions", response_model=SubDivisionResponse, status_code=status.HTTP_201_CREATED)
def create_subdivision(
    subdivision_data: SubDivisionCreate,
    db: Session = Depends(get_db)
):
    """Admin: Create a new subdivision for a given division."""
    # Check if division exists
    division = db.query(Division).filter(Division.id == subdivision_data.division_id).first()
    if not division:
        raise HTTPException(status_code=404, detail="Division not found.")
        
    # Check if subdivision name is unique within the division
    existing_sub = db.query(SubDivision).filter(
        SubDivision.division_id == subdivision_data.division_id,
        SubDivision.name.ilike(subdivision_data.name)
    ).first()
    if existing_sub:
        raise HTTPException(status_code=400, detail=f"Subdivision '{subdivision_data.name}' already exists in this division.")

    new_subdivision = SubDivision(**subdivision_data.model_dump())
    db.add(new_subdivision)
    db.commit()
    db.refresh(new_subdivision)
    return new_subdivision

@router.get("/subdivisions", response_model=List[SubDivisionResponse])
def get_all_subdivisions(
    division_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """Admin: Get all subdivisions, optionally filtered by division_id."""
    query = db.query(SubDivision).options(joinedload(SubDivision.division)).order_by(SubDivision.name)
    if division_id:
        query = query.filter(SubDivision.division_id == division_id)
    return query.all()

@router.put("/subdivisions/{subdivision_id}", response_model=SubDivisionResponse)
def update_subdivision(
    subdivision_id: UUID,
    subdivision_data: SubDivisionUpdate,
    db: Session = Depends(get_db)
):
    """Admin: Update a subdivision's name or move it to another division."""
    subdivision = db.query(SubDivision).filter(SubDivision.id == subdivision_id).first()
    if not subdivision:
        raise HTTPException(status_code=404, detail="Subdivision not found.")

    update_data = subdivision_data.model_dump(exclude_unset=True)

    # If division is being changed, validate the new one
    if 'division_id' in update_data and subdivision.division_id != update_data['division_id']:
        new_division = db.query(Division).filter(Division.id == update_data['division_id']).first()
        if not new_division:
            raise HTTPException(status_code=404, detail="New division not found.")

    # Check for name uniqueness within the target division
    target_division_id = update_data.get('division_id', subdivision.division_id)
    new_name = update_data.get('name', subdivision.name)
    
    existing_sub = db.query(SubDivision).filter(
        SubDivision.division_id == target_division_id,
        SubDivision.name.ilike(new_name),
        SubDivision.id != subdivision_id
    ).first()
    if existing_sub:
        raise HTTPException(status_code=400, detail=f"Subdivision name '{new_name}' already exists in the target division.")

    for field, value in update_data.items():
        setattr(subdivision, field, value)
        
    db.commit()
    db.refresh(subdivision)
    return subdivision

@router.delete("/subdivisions/{subdivision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subdivision(
    subdivision_id: UUID,
    db: Session = Depends(get_db)
):
    """Admin: Delete a subdivision."""
    subdivision = db.query(SubDivision).filter(SubDivision.id == subdivision_id).first()
    if not subdivision:
        raise HTTPException(status_code=404, detail="Subdivision not found.")
        
    db.delete(subdivision)
    db.commit()
    return None