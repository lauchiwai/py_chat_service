from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer  
from jose import jwt
from dotenv import load_dotenv

import os

load_dotenv() 

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",  
    auto_error=True,
    scheme_name="BearerAuth"
)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    print("==== 到達依賴項 ====")
    if not token:
        print("==== 沒有收到token ====")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供授權憑證",
        )
    
    try:
        SECRET_KEY = os.getenv("JWT_SECRET_KEY")
        ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")  
        ISSUER = os.getenv("JWT_ISSUER")
        AUDIENCE = os.getenv("JWT_AUDIENCE")   
        
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"verify_exp": True, "verify_header": False}
        )
        
        print(f"[Auth Debug] 解析後的 Payload: {payload}")
        return payload
    except jwt.ExpiredSignatureError:
        print("==== Token 已過期 ====")
        raise HTTPException(status_code=401, detail="Token 已過期")
    except Exception as e:
        print(f"JWT驗證失敗: {str(e)}")
        raise HTTPException(status_code=401, detail="無效Token")