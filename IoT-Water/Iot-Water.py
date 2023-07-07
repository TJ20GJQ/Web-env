from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import cross_origin
from datetime import datetime,timedelta
import time
from threading import Thread
import requests
import json
import random
from flask import request
import pandas as pd

app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')

HOSTNAME = "127.0.0.1"  # MySQL所在主机名
PORT = 3306  # MySQL监听的端口号，默认3306
USERNAME = "root"  # 连接MySQL的用户名，自己设置
PASSWORD = "GJQ123"  # 连接MySQL的密码，自己设置
DATABASE = "WaterData"  # MySQL上创建的数据库名称
# 通过修改以下代码来操作不同的SQL比写原生SQL简单很多 --> 通过ORM可以实现从底层更改使用的SQL
app.config[
    'SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
db = SQLAlchemy(app)

token_jxy = ""  # Token 调用IoTDA
token_gjq = ""  # Token 调用ModelArts
token_flag = False  # 已获取Token标识
getData_flag = False  # 启动数据获取标识
autoCtrl_flag = False  # 启动自动控制标识


class WaterData(db.Model):
    """
    定义存储数据表table WaterData及其column
    """
    __tablename__ = "waterData"

    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    datetime = db.Column(db.DateTime)
    temperature = db.Column(db.Float)
    DO = db.Column(db.Float)
    PH = db.Column(db.Float)
    TDS = db.Column(db.Float)
    COD = db.Column(db.Float)


def query2dict(model_list):
    """
    将MySQL查询到的数据对象（list/object）转为字典格式
    :param model_list:查询结果 list/object
    :return:dict
    """
    if isinstance(model_list, list):  # 如果传入的参数是一个list类型的，说明是使用的all()的方式查询的
        if isinstance(model_list[0], db.Model):  # 这种方式是获得的整个对象，相当于 select * from table
            lst = []
            for model in model_list:
                dic = {}
                for col in model.__table__.columns:
                    dic[col.name] = getattr(model, col.name)
                lst.append(dic)
            return lst
        else:  # 这种方式获得了数据库中的个别字段，相当于 select id,name from table
            lst = []
            for result in model_list:  # 当以这种方式返回的时候，result中会有一个keys()的属性
                lst.append([dict(zip(result.keys, r)) for r in result])
            return lst
    else:  # 不是list，说明是用的get()或者first()查询的，得到的结果是一个对象
        if isinstance(model_list, db.Model):  # 这种方式是获得的整个对象，相当于 select * from table limit=1
            dic = {}
            for col in model_list.__table__.columns:
                dic[col.name] = getattr(model_list, col.name)
            return dic
        else:  # 这种方式获得了数据库中的个别字段，相当于 select id,name from table limit = 1
            return dict(zip(model_list.keys(), model_list))


class Async_getData:
    """
    实现多线程的异步非阻塞向IoTDA的API获取数据，存入数据库，实现数据的实时更新
    """
    def start_async(*args):
        fun = args[0]

        def start_thread(*args, **kwargs):
            """启动线程（内部方法）"""
            t = Thread(target=fun, args=args, kwargs=kwargs)
            t.start()

        return start_thread

    @start_async
    def get_data_thread(*args):
        cod_valid = pd.read_csv('COD_valid.csv', index_col=False)['fit']
        times = 0  # 循环次数，用来存储实际污水厂COD数据
        with app.app_context():
            db.create_all()  # 在数据库中生成数据表
            db.session.commit()
        global getData_flag
        while token_flag and getData_flag:  # 已获取token且开启数据获取
            # print("Getting data...")
            url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8" \
                  r"a70fc9b5286d79d/devices/641e635340773741f9fc2714_L610_CN2023/properties?service_id=SpraySwitch"
            Params = {
                "service_id": "SpraySwitch"
            }
            Headers = {
                "X-Auth-Token": token_jxy
            }
            response = requests.get(url=url, params=Params, headers=Headers)
            res = json.loads(response.text)
            print(res)
            with app.app_context():
                try:
                    add = WaterData(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    temperature=res['response']['services'][0]['properties']['temperature'],
                                    PH=res['response']['services'][0]['properties']['PH'],
                                    DO=2.5 + 0.2*round(random.random(), 2),
                                    TDS=0.56 + 0.1*round(random.random(), 2),
                                    COD=cod_valid[times])
                    db.session.add(add)
                    db.session.commit()
                except KeyError:  # 如果数据获取有误
                    # add = WaterData(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), temperature=100.0,
                    #                 PH=5.9, DO=2.5, TDS=0.56, COD=cod_valid[times])
                    # db.session.add(add)
                    # db.session.commit()
                    pass
            time.sleep(1)
            times = times + 1


class Async_autoCtrl:
    """
    实现多线程的异步非阻塞实时控制（基于对工厂实际COD数据的预测）
    """
    def start_async(*args):
        fun = args[0]

        def start_thread(*args, **kwargs):
            """启动线程（内部方法）"""
            t = Thread(target=fun, args=args, kwargs=kwargs)
            t.start()

        return start_thread

    @start_async
    def auto_ctrl_thread(*args):
        while autoCtrl_flag:
            with app.app_context():
                res = query2dict(WaterData.query.all())
                cods = []
                for dic in res[-48:]:
                    cods.append(dic['COD'])
                url = "https://192.168.203.131:1027"
                Body = {
                    "history": cods
                }
                requests.packages.urllib3.disable_warnings()
                res = requests.post(url=url, json=Body, verify=False)
                res = json.loads(res.text)[0]['predict']
                url = "https://192.168.203.131:1028"
                Body = {
                    "ctrl_data": res
                }
                res = requests.post(url=url, json=Body, verify=False)
                res = json.loads(res.text)['resp_data']
                print(res)
                time.sleep(1)


@app.route('/')
@cross_origin()
def start():
    """
    根目录，获取token，每次必须先启动以更新token
    :return: Get Token OK / Get Token Failed
    """
    url = r"https://iam.cn-north-4.myhuaweicloud.com/v3/auth/tokens"
    Headers = {
        "Content-Type": "application/json"
    }
    Body_jxy = {
        "auth": {
            "identity": {
                "methods": [
                    "password"
                ],
                "password": {
                    "user": {
                        "name": "jx1",
                        "password": "mayuguojia4",
                        "domain": {
                            "name": "hw091458930"
                        }
                    }
                }
            },
            "scope": {
                "project": {
                    "name": "cn-north-4"
                }
            }
        }
    }
    Body_gjq = {
        "auth": {
            "identity": {
                "methods": [
                    "password"
                ],
                "password": {
                    "user": {
                        "name": "IoT-Water",
                        "password": "GJQ1030ab",
                        "domain": {
                            "name": "jiaqiyun"
                        }
                    }
                }
            },
            "scope": {
                "project": {
                    "name": "cn-north-4"
                }
            }
        }
    }
    try:
        response_jxy = requests.post(url=url, headers=Headers, json=Body_jxy)
        response_gjq = requests.post(url=url, headers=Headers, json=Body_gjq)
        global token_jxy, token_gjq
        token_jxy = response_jxy.headers["X-Subject-Token"]
        token_gjq = response_gjq.headers["X-Subject-Token"]
        global token_flag
        token_flag = True
        return "Get Token OK!"
    except:
        return "Get Token Failed!"


@app.route('/start_get')
@cross_origin()
def start_get_data():
    """
    启动获取数据线程
    :return: Start get data and store into MySQL
    """
    global getData_flag
    getData_flag = True
    Async_getData().get_data_thread()  # 启动异步线程
    return 'Start get data and store into MySQL.'


@app.route('/stop_get')
@cross_origin()
def stop_get_data():
    """
    关闭获取数据线程
    :return: Stop get data and store into MySQL
    """
    global getData_flag
    getData_flag = False
    return 'Stop get data and store into MySQL.'


@app.route('/query<num>')
@cross_origin()
def query_data(num):
    """
    按条数查询设备属性数据
    :param num: 希望查询数据条数
    :return: 查询得到的数据
    """
    res = query2dict(WaterData.query.all())
    res_convert = []
    for dic in res[-int(num):]:
        dic['datetime'] = dic['datetime'].strftime('%Y-%m-%d %H:%M:%S')
        res_convert.append(dic)
    return res_convert


@app.route('/queryIn<period>', methods=['GET', 'POST'])
@cross_origin()
def query_period_data(period):
    """
    根据时段查询MySQL数据，使用GET方法获取最近时间段数据，使用POST方法获得历史时间段数据
    :param period: Hour/Day/Month
    :return: 符合时间段要求的数据
    """
    if request.method == 'GET':  # GET获取当前时间的区间数据
        time_now = datetime.now()
        # print(time_now.strftime('%Y-%m-%d %H:%M:%S'))
        if period == 'Hour':
            res = WaterData.query.filter(WaterData.datetime >= time_now - timedelta(hours=1)).all()
        elif period == 'Day':
            res = WaterData.query.filter(WaterData.datetime >= time_now - timedelta(days=1)).all()
        elif period == 'Month':
            res = WaterData.query.filter(WaterData.datetime >= time_now - timedelta(days=30)).all()
        else:
            res = []
    else:  # POST获取历史时间的区间数据
        time_form = request.form.to_dict()
        if period == 'Hour':
            time_query = datetime(int(time_form["year"]), int(time_form["month"]), int(time_form["day"]),
                                  int(time_form["hour"]))
            res = WaterData.query.filter(time_query <= WaterData.datetime).filter(WaterData.datetime < time_query + timedelta(hours=1)).all()
        elif period == 'Day':
            time_query = datetime(int(time_form["year"]), int(time_form["month"]), int(time_form["day"]))
            res = WaterData.query.filter(time_query <= WaterData.datetime).filter(WaterData.datetime < time_query + timedelta(days=1)).all()
        elif period == 'Month':
            time_query = datetime(int(time_form["year"]), int(time_form["month"]), 1)
            if int(time_form["month"]) < 12:
                time_query_till = datetime(int(time_form["year"]), int(time_form["month"])+1, 1)
            else:
                time_query_till = datetime(int(time_form["year"])+1, 1, 1)
            res = WaterData.query.filter(time_query <= WaterData.datetime).filter(WaterData.datetime < time_query_till).all()
        else:
            res = []
    if len(res) >= 1:
        res = query2dict(res)
        res_convert = []
        for dic in res:
            dic['datetime'] = dic['datetime'].strftime('%Y-%m-%d %H:%M:%S')
            res_convert.append(dic)
        return res_convert
    else:
        return []


# 使用LSTM算法预测下一个
@app.route('/lstm')
@cross_origin()
def predict_data_lstm():
    # url = "https://c8af6bb488604c9896ae462d73d7056d.apigw.cn-north-4.huaweicloud.com/v1/infers/01ee8b10-b5fa-4a7c-
    # 94bc-4f417b63a76c"
    # Headers = {
    #     "X-Auth-Token": token_gjq}
    url = "https://192.168.203.131:1027"
    Body = {
        "history": [428.847, 422.564, 416.514, 410.696, 405.111, 399.758, 394.638, 389.750, 385.095, 380.672, 376.482,
                    372.524, 368.799, 365.307, 362.046, 359.019, 356.224, 353.661, 351.331, 349.233, 347.368, 345.736,
                    344.336, 343.168, 341.125, 340.293, 341.150, 342.997, 345.267, 347.698, 348.516, 349.393, 352.321,
                    355.089, 356.239, 356.967, 357.737, 358.178, 354.248, 351.348, 348.909, 347.552, 353.144, 358.907,
                    365.038, 370.885, 374.398, 377.583]
    }
    # res = requests.post(url=url, headers=Headers, json=Body)
    requests.packages.urllib3.disable_warnings()
    res = requests.post(url=url, json=Body, verify=False)
    # print(json.loads(res.text)[0]['predict'])
    return [json.loads(res.text)[0]['predict']]


# 使用SVM算法预测下一个
@app.route('/svm')
@cross_origin()
def predict_data_svm():
    # url = "https://c8af6bb488604c9896ae462d73d7056d.apigw.cn-north-4.huaweicloud.com/v1/infers/1cbd3692-732f-4d7f-
    # bcf7-70a0081f4606"
    # Headers = {
    #     "X-Auth-Token": token_gjq}
    url = "https://192.168.203.131:1025"
    Body = {
        "history": [5.479, 5.600, 5.715]
    }
    # res = requests.post(url=url, headers=Headers, json=Body)
    requests.packages.urllib3.disable_warnings()
    res = requests.post(url=url, json=Body, verify=False)
    # print(json.loads(res.text)['data']['resp_data'][0]['predictresult'])
    return [json.loads(res.text)['data']['resp_data'][0]['predictresult']]
    

@app.route('/ctrl_motor<num>/<speed>')
@cross_origin()
def control_motor(num, speed):
    """
    控制第num个气泵的速度为speed
    :param num: 气泵编号
    :param speed: 控制电机速度 0/1/2
    :return: 响应码（200）
    """
    url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d7" \
          r"9d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
    Headers = {
        "X-Auth-Token": token_jxy,
        'Content-Type': 'application/json'
    }
    Body = {
        "service_id": "Motor_Control_System",
        "command_name": f"Motor{num}_Control",
        "paras": {
            f"Motor{num}": f"{speed}"
        }
    }
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    return str(res)


@app.route('/ctrl_switch<num>/<state>')
@cross_origin()
def control_switch(num, state):
    """
    控制第num个气泵的状态为state
    :param num: 气泵编号
    :param state: 控制状态 ON/OFF
    :return: 响应码（200）
    """
    url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d79" \
          r"d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
    Headers = {
        "X-Auth-Token": token_jxy,
        'Content-Type': 'application/json'
    }
    Body = {
        "service_id": "Switch_Control_System",
        "command_name": f"Switch{num}_Control",
        "paras": {
            f"Switch{num}": f"{state}"
        }
    }
    print({f"Switch{num}": f"{state}"})
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    return str(res)


@app.route('/autoCtrl')
@cross_origin()
def autoCtrl():
    """
    启动多线程自动控制曝气
    :return: Start running automatically
    """
    global autoCtrl_flag
    autoCtrl_flag = True
    Async_autoCtrl().auto_ctrl_thread()  # 启动异步线程
    return 'Start running automatically.'


@app.route('/stopAutoCtrl')
@cross_origin()
def stopAutoCtrl():
    """
    停止多线程自动控制曝气
    :return: Stop running automatically
    """
    global autoCtrl_flag
    autoCtrl_flag = False
    return 'Stop running automatically.'


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
