from fastapi import FastAPI
from .database import base,engine
from .router import search_flight,user,auth,admin,booking
from . import model 

model.base.metadata.create_all(bind=engine)

app=FastAPI()

app.include_router(search_flight.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(booking.router)