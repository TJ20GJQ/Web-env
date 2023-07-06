from flask import Flask  # 导入Flask模块

# 创建Flask的实例对象
# app = Flask(__name__)  # 确定工程文件目录 -> Flask('模块名')
# app = Flask(__name__, static_url_path='/s')
app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')


# 定义视图
# 装饰器（路由）
@app.route('/')
# 视图函数
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
