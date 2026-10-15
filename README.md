# QuoteFlow 프로젝트 스타터

견적서 추출·검색·관리 서비스의 협업용 골격입니다. 실제 Upstage/Supabase 연동과 영속 저장은 구현하지 않았습니다.

## 실행
- 프론트엔드: `cd frontend && npm install && npm run dev`
- 백엔드: `cp backend/.env.example backend/.env && docker compose -f backend/docker-compose.yml up --build`
- API 문서: `http://localhost:8000/docs`

## 구성
- `frontend/`: React + Vite 대시보드 UI 초안
- `backend/`: FastAPI 라우트/스키마, Docker, Supabase SQL 초안
- `docs/`: 기획, API 계약, 가상 입력 데이터

주의: 요청사항에 맞춰 `/api/extract`는 GET으로 두었지만, 추출 작업을 시작하는 동작은 부작용이 있으므로 실제 구현에서는 `POST /api/extract` 또는 `POST /api/extraction-jobs`로 분리하는 것을 권장합니다. 실제 견적서 샘플을 쓸 경우 개인정보를 익명화하세요.
