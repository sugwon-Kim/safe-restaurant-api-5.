import os
from datetime import date
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

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
            if response.status_code != 200:
                body = response.text[:500]
                raise HTTPException(
                    status_code=502,
                    detail=f"농식품부 응답 오류: HTTP {response.status_code} / {body}",
                )
            try:
                data = response.json()
            except ValueError:
                raise HTTPException(
                    status_code=502,
                    detail=f"농식품부 응답이 JSON이 아닙니다: {response.text[:500]}",
                )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"농식품부 API 접속 실패: {type(exc).__name__} / {str(exc)}",
        )

    root = data.get(MAFRA_API_URL, data) if isinstance(data, dict) else {}
    rows = _as_list(root.get("row") if isinstance(root, dict) else None)
    return [_normalize(r) for r in rows if _active(r)]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """<!doctype html><html lang='ko'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>지유니를 위한 승워니의 안심식당 찾아주기♥</title><style>body{font-family:Arial,'Malgun Gothic';background:#f4f7fb;color:#172033;margin:0}.wrap{max-width:900px;margin:auto;padding:28px 16px}.hero{background:#173b69;color:white;border-radius:18px;padding:24px;margin-bottom:16px}h1{margin:0 0 8px}.search{background:white;border-radius:14px;padding:16px;display:flex;gap:8px;flex-wrap:wrap}input,button{padding:12px;border:1px solid #d5dce8;border-radius:9px;font-size:15px}input{flex:1;min-width:150px}button{background:#2878d0;color:white;font-weight:bold;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:14px}.card{background:white;border-radius:14px;padding:16px;box-shadow:0 3px 12px #0000000d}.tag{color:#1764ad;font-size:13px}.line{margin-top:7px;color:#56657c;font-size:14px}@media(max-width:650px){.grid{grid-template-columns:1fr}}</style><main class='wrap'><section class='hero'><h1>지유니를 위한 스워니의 안심식당 찾기♥</h1><div>지유니와 함께 맛있는 시간을 위한 안심식당 찾아요^^.</div></section><form class='search' id='f'><input id='sido' value='전북특별자치도' placeholder='시도명'><input id='sigungu' value='전주시' placeholder='시군구명' required><input id='category' value='한식' placeholder='업종'><button>검색</button></form><p id='meta'>조회 중...</p><section class='grid' id='r'></section></main><script>const f=document.querySelector('#f'),m=document.querySelector('#meta'),r=document.querySelector('#r');const e=s=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));async function load(x){x&&x.preventDefault();m.textContent='조회 중...';const q=new URLSearchParams({sido:document.getElementById('sido').value,sigungu:document.getElementById('sigungu').value,category:document.getElementById('category').value,limit:'100'});try{const d=await (await fetch('/restaurants?'+q)).json();m.textContent=`${d.query.sido} ${d.query.sigungu} · ${d.query.category||'전체'} · ${d.restaurants.length}곳`;r.innerHTML=d.restaurants.map(x=>`<article class='card'><h3>${e(x.name)}</h3><div class='tag'>${e(x.category_detail||x.category)}</div><div class='line'>📍 ${e(x.address)}</div><div class='line'>☎ ${e(x.phone||'전화번호 없음')}</div><div class='line'>지정 ${e(x.designated_date||'-')} · 수정 ${e(x.updated_at||'-')}</div></article>`).join('')}catch(z){m.textContent='조회 실패';r.innerHTML='<p>API 키와 Render 로그를 확인해 주세요.</p>'}}f.addEventListener('submit',load);load();</script></html>"""


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
