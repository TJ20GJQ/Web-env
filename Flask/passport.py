from flask import Blueprint, current_app

bp = Blueprint('passport', __name__)


@bp.route('/bp')
def viewfunc():
    print(current_app.redis_cli)
    return 'ok'
