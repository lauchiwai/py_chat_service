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
    if token.startswith("Bearer "):
        token = token[7:].strip()
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="have not provide jwt token",
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
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid Token")