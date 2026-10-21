import json
import requests
import pandas as pd
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# API Key 가져오기
api_key = os.getenv("KOSIS_API_KEY")

# 실제 수치 조회 주소
url = "https://kosis.kr/openapi/Param/statisticsParameterData.do"

params = {
    "method": "getList",
    "apiKey": api_key,
    "orgId": "101",
    "tblId": "DT_1IN1502",
    "itmId": "T100",
    "objL1": "00",
    "prdSe": "Y",
    "newEstPrdCnt": "3",
    "format": "json",
    "jsonVD": "Y",
}

response = requests.get(url, params=params, timeout=30)

# 인증키를 제외한 실제 응답 주소 확인
print("응답 주소:", response.url.split("?")[0])
print("HTTP 상태:", response.status_code)

if not response.ok:
    raise SystemExit("HTTP 요청 실패")

data = response.json()

if isinstance(data, dict):
    raise SystemExit(
        f"API 응답: {data.get('err', '')} "
        f"{data.get('errMsg', '예상하지 못한 응답입니다.')}"
    )

if not isinstance(data, list) or not data:
    raise SystemExit("조회된 데이터가 없습니다.")

df = pd.DataFrame(data)
print("받은 열:", df.columns.tolist())

if not {"DT", "PRD_DE"}.issubset(df.columns):
    raise SystemExit("수치 응답이 아닙니다. 위 응답 주소와 열을 확인하세요.")

# JSON 저장
with open("stats.json", "w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=2)

# 전체 열을 CSV로 저장
df.to_csv("stats.csv", index=False, encoding="utf-8-sig")

# 핵심 열만 화면에 출력
columns = ["PRD_DE", "C1_NM", "ITM_NM", "DT", "UNIT_NM"]
print(df[columns].to_string(index=False))

print("stats.json / stats.csv 저장 완료")