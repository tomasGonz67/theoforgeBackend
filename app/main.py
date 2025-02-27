from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
import os
from datetime import timedelta
from fastapi.middleware.cors import CORSMiddleware

from app.services.jwt_service import create_access_token
from app.schemas.token_schema import TokenResponse
from app.auth.dependencies import get_current_user
from settings.config import settings

app = FastAPI(title="Hello World API")

origins=[
    "http://localhost:5173",
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8000/set-cookie",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allow frontend origin
    allow_credentials=True,  # Required for cookies/auth headers
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get database URL from environment variable
database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url) if database_url else None

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    if engine:
        try:
            # Try to connect to the database
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
    else:
        db_status = "no database configured"
    
    return {
        "status": "healthy",
        "database": db_status
    } 

# Simulated user database for FastAPI example
users_db = {
    "user@example.com": {
        "username": "user@example.com",
        "password": "Secure*1234",
    }
}

# Method 1 - Secure and Preferable - 2 Step Process
# Creating a JSON Response (to then set a HTTP-only cookie after immediate use by frontend)
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or form_data.password != "Secure*1234":  # Replace with real hashing check
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user["username"], "role": "user role example"},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

# Method 2 - Alternative for simplicity
# Instantly setting the cookie and sending a response to frontend
@app.post("/login/cookie")
async def login_cookie(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or form_data.password != "Secure*1234":
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user["username"], "role": "user role example"},
        expires_delta=access_token_expires
    )

    response = JSONResponse(content={"message": "Login successful with cookie"})

    # Set token in HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript from accessing it
        secure=False,  # Use True in production with HTTPS
        samesite="Lax"  # Helps prevent CSRF attacks
    )

    return response

# Set cookie after creating JSON response and immediate frontend handling (second step of Method #1)
# Frontend can retrieve requests afterward by having ' credentials: "include" ' in fetch
@app.post("/set-cookie")
async def set_cookie(token_data: TokenResponse, response: Response):
    try:
        access_token = token_data.access_token

        if not access_token:
            raise HTTPException(status_code=400, detail="Missing token")

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,  # JavaScript cannot access this
            secure=False, # set to true in prod
            samesite="Lax"
        )

        return JSONResponse(
            content={"message": "Cookie set successfully"}, 
            headers={"Access-Control-Allow-Credentials": "true"}
        )
    
    except Exception as e:
        print(f"Error in set_cookie: {str(e)}")  # Log the error for debugging
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/test-auth")
async def test_auth(response: Response):
    # Create a token for testing
    access_token = create_access_token(
        data={"sub": "user@example.com", "role": "user role example"},
        expires_delta=timedelta(minutes=30)
    )
    
    # Set the cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="Lax"
    )
    
    # Return the token for convenience
    return {"access_token": access_token, "message": "Test cookie set, now try the /auth endpoint"}

# When protecting certain routes using JWT authentication with the cookie
@app.get("/auth")
async def protected_route(username: str = Depends(get_current_user)):
    return {"message": f"Hello, {username}! You have access to this route."}

# Clears cookie when logging out
@app.post("/logout/cookie")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}