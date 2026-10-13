# 한국어 로컬 OCR 모델

`korean_rec.onnx`는 RapidAI가 공개 배포하는 PP-OCRv4 한국어 recognition 모델입니다. RapidOCR ONNXRuntime의 기본 detection/classification 모델과 함께 로컬에서 사용합니다.

- 원본: https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv4/rec/korean_PP-OCRv4_rec_mobile.onnx
- 배포 명세: https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml
- 프로젝트: https://github.com/RapidAI/RapidOCR
- 라이선스: Apache-2.0 (RapidOCR/PaddleOCR 공개 모델)

최초 개발 시 모델만 다운로드했습니다. 견적서·이미지는 외부 OCR 서버로 전송하지 않습니다. 기본 실행은 이 모델 파일을 사용하며 런타임 다운로드가 없습니다.
