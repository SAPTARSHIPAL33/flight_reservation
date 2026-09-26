from fastapi import Depends, APIRouter,status,HTTPException
from .. import database , schemas,utils,model,oauth
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

router=APIRouter(tags=["AUTHENTICATION"])

@router.post("/login",response_model=schemas.Token)
def login(user_credentials:OAuth2PasswordRequestForm=Depends(), db:Session=Depends(database.get_db)):
    # {
    #     'username':"random",
    #     'password':"random"
    # }
    user=db.query(model.User).filter(model.User.email==user_credentials.username).first() #checking email
    
    if not user or not utils.verify(user_credentials.password , user.password):   #validaing password
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials")
    
    access_token=oauth.create_access_token(data={"user_id":user.id})
    return {"access_token":access_token,"token_type":"bearer"}