from flask import Flask  # 导入Flask模块


# # 配置对象方式加载配置信息
# class DefaultConfig(object):
#     SECRET_KEY = 'NJSKBH45613'


# 创建Flask的实例对象
app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')

# 设置
# app.config.from_object(DefaultConfig)  # 通过对象 优点：继承 缺点：敏感数据暴露
# app.config.from_pyfile('setting.py')  # 通过文件 优点：独立文件，保护敏感数据 缺点：不能继承，文件路径固定，不灵活
# export PROJECT_SETTING = setting.py
app.config.from_envvar('PROJECT_SETTING', silent=True)  # 通过环境变量 优点：独立文件，保护敏感数据，文件路径不固定，灵活 缺点：不方便，要记得设置环境变量
# 实际上：先通过对象设置默认参数，再通过环境变量指向的配置文件中读取的配置信息覆盖掉从配置对象中加载的同名参数


# 定义视图
# 装饰器（路由）
@app.route('/')
# 视图函数
def hello_world():
    print(app.config['SECRET_KEY'])
    return 'Hello World!'


if __name__ == '__main__':
    app.run(host='0.0.0.0')
