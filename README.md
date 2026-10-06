# 농림축산식품부 안심식당 조회 API

## 실행

```bash
cd safe_restaurant_api
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export MAFRA_API_KEY='발급받은_API_KEY'  # Windows PowerShell: $env:MAFRA_API_KEY='...'
uvicorn main:app --reload --port 8000
```

조회 예시:

```text
http://127.0.0.1:8000/restaurants?sido=충청남도&sigungu=공주시&category=한식&limit=20
```

`/docs`에서 자동 생성된 Swagger 화면으로 테스트할 수 있습니다.

## GPT 연결

1. 서버를 HTTPS 공개 주소에 배포합니다.
2. `openapi.yaml`의 `servers.url`을 실제 주소로 바꿉니다.
3. Custom GPT의 Actions에 OpenAPI Schema를 등록합니다.
4. GPT가 지역·시군구·업종·개수를 API에 전달하도록 지시합니다.

API 키는 코드나 GPT 지침에 넣지 말고 서버 환경변수로만 관리합니다.
