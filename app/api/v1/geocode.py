# routers/geocode.py
from fastapi import APIRouter, HTTPException, Depends
import httpx
from app.utils.security import get_current_user
router = APIRouter(tags=["geocode"])

@router.get("/search")
async def search_location(q: str, current_user = Depends(get_current_user)):
    if not q:
        raise HTTPException(status_code=400, detail="Query kosong")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "format": "json",
                    "q": q,
                    "limit": 5,
                    "countrycodes": "id"
                },
                headers={
                    "User-Agent": "AplikasiWFO/1.0 (admin@perusahaan.com)",
                    "Accept-Language": "id"
                },
                timeout=10.0
            )

            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="Terlalu banyak request, coba lagi beberapa saat")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Gagal menghubungi layanan geocoding: {str(e)}")