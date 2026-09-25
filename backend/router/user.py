from fastapi import FastAPI, Response, status,HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from ..database import get_db, base
from .. import model,utils,schemas,oauth

router=APIRouter(tags=["USERS"])

@router.post("/user",status_code=status.HTTP_201_CREATED)
def create(user:schemas.createUser,db:Session=Depends(get_db)):
    hashed_password=utils.hash(user.password)
    user.password=hashed_password
    new_user=model.User(**user.dict())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

@router.delete("/removeUser/{id}",status_code=status.HTTP_204_NO_CONTENT)
def deleteUser(id:int,db:Session=Depends(get_db),current_user:int=Depends(oauth.get_the_user)):
    user=db.query(model.User).filter(model.User.id==id)
    if user.first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="No such user")
    user.delete()
    db.commit()
    return user