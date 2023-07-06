from flask import Flask, Blueprint

# 创建Flask的实例对象
app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')

# 创建蓝图对象
user_bp = Blueprint('user', __name__)


# 定义视图
@user_bp.route('/profile')
def get_profile():
    return 'user profile'


# 注册蓝图 应用--》蓝图--》视图
app.register_blueprint(user_bp, url_prefix='/user')  # url_prefix 加前缀

from goods import goods_bp
app.register_blueprint(goods_bp)

if __name__ == '__main__':
    app.run()
