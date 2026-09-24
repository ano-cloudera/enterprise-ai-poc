from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.ossie.service import (
    OssieJoinPathRequest,
    OssieQueryRequest,
    OssieResolveRequest,
    get_tempo_ossie_service,
)


router = APIRouter(prefix="/semantic", tags=["semantic"])


@router.get("/status")
def semantic_status():
    return get_tempo_ossie_service().status()


@router.get("/capabilities")
def semantic_capabilities():
    return get_tempo_ossie_service().capabilities()


@router.post("/resolve")
def resolve_semantic_object(request: OssieResolveRequest):
    return get_tempo_ossie_service().resolve(request.question)


@router.post("/ontology")
def query_ontology(request: OssieResolveRequest):
    return get_tempo_ossie_service().query_ontology(request.question)


@router.post("/join-path")
def find_join_path(request: OssieJoinPathRequest):
    try:
        return get_tempo_ossie_service().find_join_path(
            request.metric,
            request.dimensions,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown governed metric") from exc


@router.get("/metrics/{metric_name}")
def get_metric_definition(metric_name: str):
    try:
        return get_tempo_ossie_service().get_metric_definition(metric_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown governed metric") from exc


@router.post("/compile")
def compile_governed_query(request: OssieQueryRequest):
    try:
        return get_tempo_ossie_service().compile_query(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/query")
def execute_governed_query(request: OssieQueryRequest):
    try:
        return get_tempo_ossie_service().execute_query(request)
    except RuntimeError as exc:
        code = str(exc)
        if code in {"OSSIE_SEMANTIC_MODE_DISABLED", "OSSIE_REQUIRES_IMPALA_BACKEND"}:
            raise HTTPException(status_code=409, detail=code) from exc
        raise
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

