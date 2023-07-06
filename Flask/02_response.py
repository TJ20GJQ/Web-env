from flask import Flask, render_template, redirect, jsonify, make_response, request, session
from werkzeug.routing import BaseConverter


app = Flask(__name__)


class DefaultConfig(object):
    SECRET_KEY = 'GJQ123'


app.config.from_object(DefaultConfig)


@app.route('/')
def home():
    mint = 123
    mstr = 'gjq'

    data = dict(
        my_str='GJQ',
        my_int=456
    )
    # return render_template('index.html', my_str=mstr, my_int=mint)
    return render_template('index.html', **data)


@app.route('/demo2')
def demo2():
    return redirect('http://www.baidu.com')


@app.route('/demo3')
def demo3():
    json_dict = {
        "user_id": 10,
        "user_name": 'gjq'
    }
    return jsonify(json_dict)  # 转换成json格式字符串，并设置响应头Content-Type:application/json


@app.route('/demo4')
def demo4():
    # return '状态码为666', 666
    return '状态码为666', 666, {'Itcast': 'Python'}


@app.route('/demo5')
def demo5():
    resp = make_response('make response test')
    resp.headers['Itcast'] = 'Python3'
    resp.status = '404 not fount'
    return resp


@app.route('/cookie')  # 设置cookie
def set_cookie():
    resp = make_response('set cookie ok')
    # resp.set_cookie('username', 'itcast')
    resp.set_cookie('username', 'itcast', max_age=3600)  # 设置生命周期(s)
    return resp


@app.route('/get_cookie')  # 读取cookie
def get_cookie():
    resp = request.cookies.get('username')
    return resp


@app.route('/delete_cookie')  # 删除cookie
def delete_cookie():
    resp = make_response('hello world')
    resp.delete_cookie('username')
    return resp


@app.route('/set_session')
def set_session():
    session['username'] = 'itcast'
    return 'set session ok'


@app.route('/get_session')  # 需要设置SECRET_KEY
def get_session():
    username = session.get('username')
    return 'get session username {}'.format(username)
