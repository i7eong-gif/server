# app/core/ads.py
import random

ADS = [
    {
        "text": "자동매매 툴 ○○ – 무료 체험",
        "url": "https://example.com"
    },
    {
        "text": "미국 주식 데이터 API 할인 중",
        "url": "https://example.com"
    }
]

def get_ad():
    return random.choice(ADS)
