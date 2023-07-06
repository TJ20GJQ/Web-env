from flask import Flask, request, abort
from werkzeug.routing import BaseConverter


app = Flask(__name__)


@app.errorhandler(500)  # 错误批处理
def internal_server_error(e):
    print(e)
    return '服务器搬家了'


@app.errorhandler(ZeroDivisionError)
def zero_division_error(e):
    print(e)
    return '除数不能为0'


@app.route('/users/<int:user_id>')
def get_user_data(user_id):
    print(type(user_id))
    return 'get user {}'.format(user_id)  # 默认string


class MobileConverter(BaseConverter):
    """手机号格式"""
    regex = r'1[3-9]\d{9}'


app.url_map.converters['mobile'] = MobileConverter


@app.route('/sms_codes/<mobile:mob_num>')
def send_sms_code(mob_num):
    print(type(mob_num))
    return 'send sms code to {}'.format(mob_num)


# /articles?channel_id=123
@app.route('/articles')
def get_articles():
    channel_id = request.args.get('channel_id')

    if channel_id is None:
        abort(400)  # 400 bad request    状态码4开头为客户端错误，5开头为服务器错误

    return 'you wanna get articles of channel {}'.format(channel_id)


@app.route('/upload', methods=['POST'])
def upload_file():
    f = request.files['pic']
    # with open('./demo.png', 'wb') as new_file:
    #     new_file.write(f.read())
    f.save('./demo.png')
    return 'ok'
