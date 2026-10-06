from __future__ import annotations

from fastapi import APIRouter, Query


router = APIRouter()

_STARTERS = [
    {
        "id": "v3-01",
        "question": "Material apa fill rate-nya paling jelek di Q4 2024?",
        "domain": "service_level",
        "domains": ["service_level"],
        "difficulty": "medium",
        "analysis_type": "ranking",
        "expected_visualization": "bar",
    },
    {
        "id": "v3-02",
        "question": "Top 10 material sell-in tertinggi dari sales silver",
        "domain": "sales",
        "domains": ["sales"],
        "difficulty": "simple",
        "analysis_type": "ranking",
        "expected_visualization": "bar",
    },
    {
        "id": "v3-03",
        "question": "Bandingkan picking vs unloading minutes per sales office",
        "domain": "operations",
        "domains": ["picking", "unloading"],
        "difficulty": "complex",
        "analysis_type": "comparison",
        "expected_visualization": "bar",
    },
]


@router.get("/random-queries")
def random_queries(limit: int = Query(default=3, ge=1, le=20)) -> dict:
    return {"questions": _STARTERS[:limit]}
