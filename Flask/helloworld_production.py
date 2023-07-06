from flask import Flask  # 导入Flask模块
import json


# 配置对象方式加载配置信息
class DefaultConfig(object):
    SECRET_KEY = 'NJSKBH45613'


class DevelopmentConfig(DefaultConfig):
    DEBUG = True


def create_flask_app(config):
    """构建flask对象的工厂函数"""
    app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')

    # 工程上：先通过对象设置默认参数，再通过环境变量指向的配置文件中读取的配置信息覆盖掉从配置对象中加载的同名参数
    app.config.from_object(config)
    app.config.from_envvar('PROJECT_SETTING', silent=False)
    return app


app = create_flask_app(DevelopmentConfig)


# app = create_flask_app(DevelopmentConfig)


# 定义视图
# 装饰器（路由）
# @app.route('/')
# # 视图函数
# def hello_world():
#     print(app.config['SECRET_KEY'])
#     return 'Hello World!'


# if __name__ == '__main__':
#     # 运行flask提供的调试服务器
#     app.run(host="0.0.0.0", port=8000)

# 新版运行方式：
# 环境变量：PROJECT_SETTING=setting.py;FLASK_APP=helloworld_production;FLASK_ENV=production/development
# 配置：1、Module neme：flask；Parameters：run 2、Parameters：-m flask run

# print(app.url_map)
# 需求：需要遍历url_map，取出特定信息，在一个特定的接口返回
# for rule in app.url_map.iter_rules():
#     print('name={} path={}'.format(rule.endpoint, rule.rule))

@app.route('/')
def route_map():
    """主视图，返回所有视图网址"""
    rules_iterator = app.url_map.iter_rules()
    return json.dumps({rule.endpoint: rule.rule for rule in rules_iterator})


# Debug模式作用：后端出现错误，会直接返回真实的错误信息给前端；修改代码后，自动重启开发服务器
