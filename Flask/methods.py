"""
flask默认请求方式：GET
OPTIONS（自带）：简化版的GET请求，用于询问服务器接口信息，比如接口允许的请求方式、允许的请求源头域名
    CORS跨域 django-cors -> 中间件中拦截处理了options请求
    返回response -> allow-origin xxx
    GET
HEAD（自带）：简化版的GET请求，只返回GET请求处理时的响应头，不返回响应体

自定POST PUT DELETE PATCH
不支持：返回状态码405: Method not allowed
"""
from flask import Flask  # 导入Flask模块

app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')


# 定义视图
@app.route('/', methods=['POST'])
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
