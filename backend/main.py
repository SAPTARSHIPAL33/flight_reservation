from fastapi import FastAPI
from .database import base,engine
from .routers import search_flight,user,auth
from . import model 

model.base.metadata.create_all(bind=engine)

app=FastAPI()

app.include_router(search_flight.router)
app.include_router(user.router)
app.include_router(auth.router)