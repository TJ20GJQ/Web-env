from flask import Flask, request, abort, current_app, g


app = Flask(__name__)


# 请求钩子（尝试判断用户的身份 对于未登录用户不做处理 放行） 用g对象保存用户身份信息
@app.before_request
def authentication():
    """
    利用before_request请求钩子，在进入所有视图前先尝试判断用户身份
    :return:
    """
    # TODO 此处利用鉴权机制（如cookie、session、jwt等）鉴别用户身份信息
    # if 已登录用户，用户有身份信息
    g.user_id = 123
    # else 未登录用户，用户无身份信息
    # g.user_id = None


# 强制登录装饰器
def login_required(func):

    def wrapper(*args, **kwargs):
        # 判断用户是否登录
        if g.user_id is None:
            abort(401)
        else:
            # 已登录
            return func(*args, **kwargs)
    return wrapper


@app.route('/')
def index():
    return 'home page user_id={}'.format(g.user_id)


@app.route('/profile')
@login_required
def get_user_profile():
    return 'user profile page user_id={}'.format(g.user_id)