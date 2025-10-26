from aiogram import Router
from bot.handlers import organic as organic_handlers
from bot.handlers import help as help_handlers

def setup_routers() -> Router:
    r = Router()
    r.include_router(help_handlers.router)
    r.include_router(organic_handlers.router)
    return r
