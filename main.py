import os
from datetime import date
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="MAFRA Safe Restaurant API",
    version="0.1.0",
    description="농림축산식품부 안심식당 Open API 중계·검색 API",
)

MAFRA_BASE_URL = os.getenv(
    "MAFRA_BASE_URL",
    "http://211.237.50.150:7080/openapi",
)
MAFRA_API_KEY = os.getenv("MAFRA_API_KEY", "")
MAFRA_API_URL = os.getenv(
    "MAFRA_API_URL", "Grid_20200713000000000605_1"
)


def _as_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _active(row: dict[str, Any]) -> bool:
    if str(row.get("RELAX_USE_YN", "")).upper() != "Y":
        return False
    cancel = str(row.get("RELAX_RSTRNT_CNCL_DT", "")).strip()
    if not cancel:
        return True
    try:
        return date.fromisoformat(cancel) > date.today()
    except ValueError:
        return True


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": row.get("RELAX_RSTRNT_NM", ""),
        "address": " ".join(
            x for x in [row.get("RELAX_ADD1", ""), row.get("RELAX_ADD2", "")] if x
        ),
        "phone": row.get("RELAX_RSTRNT_TEL", ""),
        "category": row.get("RELAX_GUBUN_DETAIL", "") or row.get("RELAX_GUBUN", ""),
        "category_detail": row.get("RELAX_GUBUN_DETAIL", ""),
        "designated_date": row.get("RELAX_RSTRNT_REG_DT", ""),
        "updated_at": row.get("UPDT_DT", ""),
        "sequence": row.get("RELAX_SEQ", ""),
    }


async def _fetch_all(
    sido: str, sigungu: str, category: str | None, limit: int
) -> list[dict[str, Any]]:
    if not MAFRA_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="MAFRA_API_KEY 환경변수가 설정되지 않았습니다.",
        )
    end = min(max(limit * 3, 100), 1000)
    params = {
        "API_KEY": MAFRA_API_KEY,
        "TYPE": "json",
        "RELAX_SI_NM": sido,
        "RELAX_SIDO_NM": sigungu,
        "RELAX_USE_YN": "Y",
    }
    if category:
        # 한식·중식 등은 업종상세(RELAX_GUBUN_DETAIL)로 조회합니다.
        params["RELAX_GUBUN_DETAIL"] = category
    url = f"{MAFRA_BASE_URL}/{MAFRA_API_KEY}/json/{MAFRA_API_URL}/1/{end}"
    params.pop("API_KEY", None)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"농식품부 API 조회 실패: {exc}")

    root = data.get(MAFRA_API_URL, data) if isinstance(data, dict) else {}
    rows = _as_list(root.get("row") if isinstance(root, dict) else None)
    return [_normalize(r) for r in rows if _active(r)]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/restaurants")
async def restaurants(
    sido: str = Query("충청남도", description="시도명"),
    sigungu: str = Query(..., description="시군구명"),
    category: str | None = Query(None, description="업종 상세. 예: 한식"),
    limit: int = Query(20, ge=1, le=1000),
) -> dict[str, Any]:
    rows = await _fetch_all(sido, sigungu, category, limit)
    return {
        "source": "농림축산식품부 안심식당 정보",
        "query": {"sido": sido, "sigungu": sigungu, "category": category},
        "count": min(len(rows), limit),
        "restaurants": rows[:limit],
    }
