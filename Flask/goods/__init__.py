from flask import Blueprint

goods_bp = Blueprint('goods', __name__)

from . import views
