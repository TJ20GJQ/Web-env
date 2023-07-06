from flask import Flask, request, abort, current_app, g


app = Flask(__name__)

# redis-cli
app.redis_cli = 'redis client'


# /articles
@app.route('/articles')
def get_articles():
    channel_id = request.args.get('channel_id')
    print(app.redis_cli)
    if channel_id is None:
        abort(400)  # 400 Bad Request

    return 'you wanna get articles of channel {}'.format(channel_id)


from passport import bp
app.register_blueprint(bp)


def db_query(user_id, uname):
    print('user_id={}'.format(user_id))


def db_query():
    uid = g.user_id
    uname = g.uname
    print('user_id={}'.format(uid))


@app.route('/')
def get_user_profile():
    user_id = 123
    uname = 'itcast'

    g.user_id = user_id  # g对象相当于一个容器
    g.uname = uname
    ret = db_query()
    return 'hello world'


# app1 = Flask(__name__)
# app2 = Flask(__name__)
# 修改FLASK_APP=04_context:app1
#
# # redis-cli
# app1.redis_cli = 'redis client 1'
# app2.redis_cli = 'redis client 2'
#
#
# # /articles
# @app1.route('/app1')
# def get_articles():
#     return '{}'.format(current_app.redis_cli)
#
#
# @app2.route('/app2')
# def get_articles_2():
#     return '{}'.format(current_app.redis_cli)
