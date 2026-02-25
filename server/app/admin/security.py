"""
x_admin_token: str | None = Header(None, alias="X-Admin-Token")
HTTP 요청 헤더 중 X-Admin-Token이라는 이름의 값을 읽어서 x_admin_token 변수에 넣습니다.
헤더가 없으면 기본값 None이 들어갑니다.

if not x_admin_token or x_admin_token != ADMIN_TOKEN:
토큰이 아예 없거나(not x_admin_token)
있더라도 서버에 정의된 ADMIN_TOKEN 값과 다르면
조건을 만족한다고 보고 아래 예외를 발생시킵니다.
raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN_ONLY")
HTTP 403 Forbidden 응답을 보내면서 요청을 거부합니다.
응답 본문에는 "ADMIN_ONLY"라는 에러 메시지가 들어갑니다.
즉, 인증은 되었더라도 “관리자만 접근 가능”한 자원에 대한 권한이 없다는 의미로 사용하는 패턴입니다.
"""

from fastapi import Header, HTTPException, status
from app.core.config import ADMIN_TOKEN

def require_admin(
    x_admin_token: str | None = Header(None, alias="X-Admin-Token"),
):
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ADMIN_ONLY",
        )