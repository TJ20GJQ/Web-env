from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import cross_origin
from datetime import datetime, timedelta
import time
from threading import Thread
import requests
import json
import random
from flask import request
import pandas as pd

app = Flask(__name__, static_url_path='/s',
            static_folder='static', template_folder='templates')

# 连接数据库
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

# 连接边缘节点
Edge_URL = "https://192.168.203.131:"
LSTM_port = '1029'
SVR_port = '1031'

# 连接华为云
token_jxy = ""  # Token 调用IoTDA
token_gjq = ""  # Token 调用ModelArts
token_flag = False  # 已获取Token标识
getData_flag = False  # 启动数据获取标识


class ctrl_system:
    """
    用于同步控制系统的状态
    """

    def __init__(self):
        self.switch = ['OFF', 'OFF', 'OFF', 'OFF', 'OFF', 'OFF']
        self.motor = [0, 0, 0, 0, 0, 0]
        self.pump = ['OFF', 'OFF', 'OFF']
        self.autoCtrl_flag = False  # 启动自动控制标识

    def ctrl_switch(self, id, state):
        self.switch[id] = state
        print(f'Switch{id}: {state}')

    def ctrl_motor(self, id, speed):
        self.motor[id] = speed
        print(f'Motor{id}: {speed}')

    def ctrl_pump(self, id, state):
        self.pump[id] = state
        print(f'Pump{id}: {state}')

    def start_auto(self):
        self.autoCtrl_flag = True
        Async_autoCtrl().auto_ctrl_thread()  # 启动自动控制线程
        print('Start auto-control.')

    def stop_auto(self):
        self.autoCtrl_flag = False
        print('Stop auto-control.')


ctrlSystem = ctrl_system()


class WaterData(db.Model):
    """
    定义存储数据表table WaterData及其column
    """
    __tablename__ = "waterData"

    id = db.Column("id", db.Integer, primary_key=True, autoincrement=True)
    datetime = db.Column(db.DateTime)
    temperature = db.Column(db.Float)
    ORP = db.Column(db.Float)
    PH = db.Column(db.Float)
    TDS = db.Column(db.Float)
    TU = db.Column(db.Float)
    DO = db.Column(db.Float)
    COD = db.Column(db.Float)


virtual_DO = 2.5
valid_data_num = 0  # 存入数据库的有效数据量


def query2dict(model_list):
    """
    将MySQL查询到的数据对象（list/object）转为字典格式
    :param model_list:查询结果 list/object
    :return:dict
    """
    if isinstance(model_list, list):  # 如果传入的参数是一个list类型的，说明是使用的all()的方式查询的
        # 这种方式是获得的整个对象，相当于 select * from table
        if isinstance(model_list[0], db.Model):
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
        global valid_data_num  # 循环次数，用来存储实际污水厂COD数据
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
                                    PH=res['response']['services'][0]['properties']['PH'] / 100,
                                    ORP=res['response']['services'][0]['properties']['ORP'] / 100,
                                    TDS=res['response']['services'][0]['properties']['TDS'],
                                    TU=res['response']['services'][0]['properties']['turbidity'],
                                    DO=virtual_DO,
                                    COD=cod_valid[valid_data_num])
                    db.session.add(add)
                    db.session.commit()
                except KeyError:  # 如果数据获取有误
                    add = WaterData(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), temperature=100.0,
                                    PH=5.9, ORP=2.5, TDS=0.56, TU=2946, DO=virtual_DO, COD=cod_valid[valid_data_num])
                    db.session.add(add)
                    db.session.commit()
                    pass
            time.sleep(1)
            valid_data_num = valid_data_num + 1


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
        cod_valid = pd.read_csv('COD_valid.csv', index_col=False)
        while ctrlSystem.autoCtrl_flag:
            with app.app_context():
                data = query2dict(WaterData.query.all())
                # LSTM
                cods = []
                for dic in data[-48:]:
                    cods.append(dic['COD'])
                Body = {
                    "history": cods
                }
                requests.packages.urllib3.disable_warnings()
                res = requests.post(url=Edge_URL + LSTM_port, json=Body, verify=False)
                lstm_res = json.loads(res.text)[0]['predict']
                # print(lstm_res)
                # SVR
                cods = []
                for dic in data[-3:]:
                    cods.append(dic['COD'])
                Body = {
                    "history": cods
                }
                res = requests.post(url=Edge_URL + SVR_port, json=Body, verify=False)
                svr_res = json.loads(res.text)['data']['resp_data'][0]['predictresult']
                # print(svr_res)
                # 专家系统
                hours_weight = [[0.98252977], [1.], [0.94414396], [0.80917324], [0.36559509], [0.18254638],
                                [0.05554637], [0.], [0.06089251], [0.14743402], [0.37075089], [0.49937936],
                                [0.50749575], [0.58988084], [0.63060292], [0.79432664], [0.87635415], [0.81332173],
                                [0.66796073], [0.62331583], [0.65741986], [0.72028482], [0.71353762], [0.75597631]]
                weekdays_weight = [[0.83437227], [0.6625369], [0.52733128], [0.6964075], [1.], [0.], [0.11924007]]
                pred = -0.317249 + 0.005082 * lstm_res + 0.995783 * svr_res + \
                       0.672760 * hours_weight[cod_valid['hour'][valid_data_num]][0] - 0.265673 * \
                       weekdays_weight[cod_valid['week'][valid_data_num]][0]
                print(pred)
                # 预测残差
                ctrl = pred - data[-1]['COD']

                ctrl_rule = [-60, -54, -48, -42, -36, -30, -24, -18, -12, -6, 0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60]
                ctrl_index = -1
                for i in range(len(ctrl_rule)):
                    if ctrl < ctrl_rule[i]:
                        ctrl_index = i
                        break
                if ctrl_index == -1:
                    ctrl_index = len(ctrl_rule)

                ctrl_commends = ['20230810190159000000FFFFFFFFF111111',
                                 '20230810190159000000FFFFFFFFF333333',
                                 '20230810190159000000FFFFFFFFF555555',
                                 '20230810190159000000FFFFFFFFF777777',
                                 '20230810190159000000FFFFFFFFF999999',
                                 '20230810190159000000FFFFFTFFF111111',
                                 '20230810190159000000FFFFFTFFF333333',
                                 '20230810190159000000FFFFFTFFF555555',
                                 '20230810190159000000FFFFFTFFF777777',
                                 '20230810190159000000FFFFFTFFF999999',
                                 '20230810190159000000FFFTFTTFT111111',
                                 '20230810190159000000TTFTFTTTT333333',
                                 '20230810190159000000TTFTFTTTT555555',
                                 '20230810190159000000TTFTFTTTT777777',
                                 '20230810190159000000TTFTFTTTT999999',
                                 '20230810190159000000TTFTTTTTT111111',
                                 '20230810190159000000TTFTTTTTT333333',
                                 '20230810190159000000TTFTTTTTT555555',
                                 '20230810190159000000TTFTTTTTT777777',
                                 '20230810190159000000TTFTTTTTT999999',
                                 '20230810190159000000TTTTTTTTT111111',
                                 ]
                cmd = ctrl_commends[ctrl_index]
                url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d79d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
                Headers = {
                    "X-Auth-Token": token_jxy,
                    'Content-Type': 'application/json'}
                Body = {
                    "service_id": "All_Control_System",
                    "command_name": f"All_Control",
                    "paras": {
                        "Control_Flags": cmd
                    }
                }
                command = requests.post(url=url, json=Body, headers=Headers)
                global virtual_DO
                virtual_DO = virtual_DO + (ctrl_index-10)*0.01
                print(ctrl_index)
                time.sleep(5)


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
            res = WaterData.query.filter(
                WaterData.datetime >= time_now - timedelta(hours=1)).all()
        elif period == 'Day':
            res = WaterData.query.filter(
                WaterData.datetime >= time_now - timedelta(days=1)).all()
        elif period == 'Month':
            res = WaterData.query.filter(
                WaterData.datetime >= time_now - timedelta(days=30)).all()
        else:
            res = []
    else:  # POST获取历史时间的区间数据
        time_form = request.form.to_dict()
        if period == 'Hour':
            time_query = datetime(int(time_form["year"]), int(time_form["month"]), int(time_form["day"]),
                                  int(time_form["hour"]))
            res = WaterData.query.filter(time_query <= WaterData.datetime).filter(
                WaterData.datetime < time_query + timedelta(hours=1)).all()
        elif period == 'Day':
            time_query = datetime(int(time_form["year"]), int(
                time_form["month"]), int(time_form["day"]))
            res = WaterData.query.filter(time_query <= WaterData.datetime).filter(
                WaterData.datetime < time_query + timedelta(days=1)).all()
        elif period == 'Month':
            time_query = datetime(
                int(time_form["year"]), int(time_form["month"]), 1)
            if int(time_form["month"]) < 12:
                time_query_till = datetime(
                    int(time_form["year"]), int(time_form["month"]) + 1, 1)
            else:
                time_query_till = datetime(int(time_form["year"]) + 1, 1, 1)
            res = WaterData.query.filter(time_query <= WaterData.datetime).filter(
                WaterData.datetime < time_query_till).all()
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


@app.route('/lstm')
@cross_origin()
def predict_data_lstm():
    """
    使用LSTM算法预测下一个COD
    :return: [COD预测值]
    """
    with app.app_context():
        data = query2dict(WaterData.query.all())
        cods = []
        for dic in data[-48:]:
            cods.append(dic['COD'])
        url = Edge_URL + LSTM_port
        Body = {
            # "history": [428.847, 422.564, 416.514, 410.696, 405.111, 399.758, 394.638, 389.750, 385.095, 380.672,
            #             376.482, 372.524, 368.799, 365.307, 362.046, 359.019, 356.224, 353.661, 351.331, 349.233,
            #             347.368, 345.736, 344.336, 343.168, 341.125, 340.293, 341.150, 342.997, 345.267, 347.698,
            #             348.516, 349.393, 352.321, 355.089, 356.239, 356.967, 357.737, 358.178, 354.248, 351.348,
            #             348.909, 347.552, 353.144, 358.907, 365.038, 370.885, 374.398, 377.583]
            "history": cods
        }
        # res = requests.post(url=url, headers=Headers, json=Body)
        requests.packages.urllib3.disable_warnings()
        res = requests.post(url=url, json=Body, verify=False)
        # print(json.loads(res.text)[0]['predict'])
        return [json.loads(res.text)[0]['predict']]


@app.route('/svm')
@cross_origin()
def predict_data_svm():
    """
    使用SVM算法预测下一个COD
    :return: [COD预测值]
    """
    with app.app_context():
        data = query2dict(WaterData.query.all())
        cods = []
        for dic in data[-3:]:
            cods.append(dic['COD'])
        url = Edge_URL + SVR_port
        Body = {
            # "history": [428.847, 422.564, 416.514]
            "history": cods
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
    if res == 200:
        ctrlSystem.ctrl_motor(int(num), int(speed))  # 同步设备状态
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
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    if res == 200:
        ctrlSystem.ctrl_switch(int(num), state)  # 同步设备状态
    return str(res)


@app.route('/ctrl_pump<num>/<state>')
@cross_origin()
def control_pump(num, state):
    """
    控制第num个蠕动泵的状态为state
    :param num: 蠕动泵编号
    :param state: 控制状态 ON/OFF
    :return: 响应码（200）
    """
    url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d79d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
    Headers = {
        "X-Auth-Token": token_jxy,
        'Content-Type': 'application/json'
    }
    Body = {
        "service_id": "WP_Control_System",
        "command_name": "WP0_Control",
        "paras": {
            f"WP{num}": f"{state}"
        }
    }
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    if res == 200:
        ctrlSystem.ctrl_pump(int(num), state)  # 同步设备状态
    return str(res)


@app.route('/autoCtrl')
@cross_origin()
def autoCtrl():
    """
    启动多线程自动控制曝气
    :return: Start running automatically
    """
    ctrlSystem.start_auto()
    return 'Start running automatically.'


@app.route('/stopAutoCtrl')
@cross_origin()
def stopAutoCtrl():
    """
    停止多线程自动控制曝气
    :return: Stop running automatically
    """
    ctrlSystem.stop_auto()
    return 'Stop running automatically.'


@app.route('/query_state')
@cross_origin()
def queryState():
    """
    查询控制系统状态
    :return: 状态dict
    """
    return {'switch': ctrlSystem.switch, 'motor': ctrlSystem.motor}


@app.route('/AllControl', methods=['POST'])
@cross_origin()
def control_all():
    url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d79d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
    Headers = {
        "X-Auth-Token": token_jxy,
        'Content-Type': 'application/json'}
    Body = {
        "service_id": "All_Control_System",
        "command_name": f"All_Control",
        "paras": {
            "Control_Flags": "20230810190159000000TTTTTTTTT777777"
        }
    }
    print(request.get_json())
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    return str(res)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
