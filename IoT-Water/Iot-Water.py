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
import numpy as np

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
token_gjq = ""  # Token 调用ModelArts、IEF
token_flag = False  # 已获取Token标识


class perceive_system:
    """
    用于根据预测COD同步模拟感知系统属性DO
    """

    def __init__(self):
        self.DO_set = 2.4
        self.DO_virtual = 2.3
        self.COD_virtual = 250
        self.COD_predict = 276
        self.getData_flag = False  # 启动数据获取标识
        self.valid_data_num = 0  # 存入数据库的有效数据量

    def start_get(self):
        self.getData_flag = True
        Async_getData().get_data_thread()  # 启动异步线程

    def stop_get(self):
        self.getData_flag = False


class ctrl_system:
    """
    用于同步控制系统的状态
    """

    def __init__(self):
        self.switch = ['OFF', 'OFF', 'OFF', 'OFF', 'OFF', 'OFF']
        self.motor = [0, 0, 0, 0, 0, 0]
        self.pump = ['OFF', 'OFF', 'OFF']
        self.power = None
        self.autoCtrl_flag = False  # 启动自动控制标识
        self.ctrlGet_flag = False  # 使用自动控制开启获取数据标识
        self.auto_time = 0  # 自动运行多少个5s周期（以5s为周期控制智能模式）

    def ctrl_switch(self, id, state):
        self.switch[id] = state
        print(f'Switch{id}: {state}')

    def ctrl_motor(self, id, speed):
        self.motor[id] = speed
        print(f'Motor{id}: {speed}')

    def ctrl_pump(self, id, state):
        self.pump[id] = state
        print(f'Pump{id}: {state}')

    def frame_ctrl(self, frame):
        self.switch[0] = 'ON' if frame[20] == 'T' else 'OFF'
        self.switch[1] = 'ON' if frame[21] == 'T' else 'OFF'
        self.switch[2] = 'ON' if frame[22] == 'T' else 'OFF'
        self.switch[3] = 'ON' if frame[23] == 'T' else 'OFF'
        self.switch[4] = 'ON' if frame[24] == 'T' else 'OFF'
        self.switch[5] = 'ON' if frame[25] == 'T' else 'OFF'
        self.pump[0] = 'ON' if frame[26] == 'T' else 'OFF'
        self.pump[1] = 'ON' if frame[27] == 'T' else 'OFF'
        self.pump[2] = 'ON' if frame[28] == 'T' else 'OFF'
        self.motor[0] = int(frame[29]) if frame[29] != 'A' else 10
        self.motor[1] = int(frame[30]) if frame[30] != 'A' else 10
        self.motor[2] = int(frame[31]) if frame[31] != 'A' else 10
        self.motor[3] = int(frame[32]) if frame[32] != 'A' else 10
        self.motor[4] = int(frame[33]) if frame[33] != 'A' else 10
        self.motor[5] = int(frame[34]) if frame[34] != 'A' else 10

    def start_auto(self):
        if not perceiveSystem.getData_flag:  # 如果没有手动启动获取数据，需要先启动获取数据
            perceiveSystem.getData_flag = True
            Async_getData().get_data_thread()  # 启动异步线程
            self.ctrlGet_flag = True
        self.autoCtrl_flag = True
        Async_autoCtrl().auto_ctrl_thread()  # 启动自动控制线程
        print('Start auto control.')

    def stop_auto(self):
        if self.ctrlGet_flag:  # 如果是自动控制开启的数据获取，则终止线程
            perceiveSystem.getData_flag = False
            self.ctrlGet_flag = False
        self.autoCtrl_flag = False
        print('Stop auto control.')


class expert_system:
    """
    专家系统，提供控制参考
    """

    def __init__(self):
        self.cod_valid = pd.read_csv('COD_valid.csv', index_col=False)
        self.hours_weight = [[0.98252977], [1.], [0.94414396], [0.80917324], [0.36559509], [0.18254638], [0.05554637],
                             [0.], [0.06089251], [0.14743402], [0.37075089], [
                                 0.49937936], [0.50749575], [0.58988084],
                             [0.63060292], [0.79432664], [0.87635415], [
                                 0.81332173], [0.66796073], [0.62331583],
                             [0.65741986], [0.72028482], [0.71353762], [0.75597631]]  # 每日权重
        self.weekdays_weight = [[0.83437227], [0.6625369], [
            0.52733128], [0.6964075], [1.], [0.], [0.11924007]]  # 每周权重
        self.weights = [-0.474074, 0.005334, 0.995509,
                        0.672805, 0.030601]  # 四项参照最小二乘法权重
        self.ctrl_rule1 = list(range(150, 526, 25))  # 16档曝气石大调
        self.ctrl_rule2 = [-40, -20, -10, -4, -
                           1, 0, 1, 4, 10, 20, 40]  # 11档曝气盘微调


perceiveSystem = perceive_system()  # 创建感知系统
ctrlSystem = ctrl_system()  # 创建控制系统
expertSystem = expert_system()  # 创建专家系统


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
        with app.app_context():
            db.create_all()  # 在数据库中生成数据表
            db.session.commit()
        if perceiveSystem.valid_data_num == 0:  # 每次启动先存入48个历史数据，便于复现
            with app.app_context():
                for i in range(48):
                    add = WaterData(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    temperature=0, PH=0, ORP=0, TDS=0, TU=0, DO=2,
                                    COD=cod_valid[perceiveSystem.valid_data_num])
                    db.session.add(add)
                    db.session.commit()
                    perceiveSystem.valid_data_num += 1

        while token_flag and perceiveSystem.getData_flag:  # 已获取token且开启数据获取
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
            # print(res)
            with app.app_context():
                try:
                    add = WaterData(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    temperature=res['response']['services'][0]['properties']['temperature'],
                                    PH=res['response']['services'][0]['properties']['PH'] / 100,
                                    ORP=res['response']['services'][0]['properties']['ORP'] / 100,
                                    TDS=res['response']['services'][0]['properties']['TDS'],
                                    TU=res['response']['services'][0]['properties']['turbidity'],
                                    DO=perceiveSystem.DO_virtual,
                                    COD=cod_valid[perceiveSystem.valid_data_num])
                    db.session.add(add)
                    db.session.commit()
                except KeyError:  # 如果数据获取有误
                    # 演示之前注释掉！！！！！！！！
                    add = WaterData(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), temperature=100.0,
                                    PH=5.9, ORP=2.5, TDS=0.56, TU=2946, DO=perceiveSystem.DO_virtual,
                                    COD=cod_valid[perceiveSystem.valid_data_num])
                    db.session.add(add)
                    db.session.commit()
                    pass
                except IndexError:
                    perceiveSystem.valid_data_num = 0  # 数据超过10000多，cod数据不够，从头开始
                    pass
            time.sleep(1)
            perceiveSystem.valid_data_num += 1
            # print(perceiveSystem.valid_data_num)


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
        while ctrlSystem.autoCtrl_flag:
            with app.app_context():
                data = query2dict(WaterData.query.all())
                perceiveSystem.COD_virtual = data[-5]['COD']
                # LSTM预测
                cods = []
                for i in range(-48, 0):
                    cods.append(data[i * 5]['COD'])
                Body = {
                    "history": cods
                }
                requests.packages.urllib3.disable_warnings()
                res = requests.post(url=Edge_URL + LSTM_port,
                                    json=Body, verify=False)
                lstm_res = json.loads(res.text)[0]['predict']
                # print(lstm_res)
                # SVR预测
                cods = []
                for i in range(-3, 0):
                    cods.append(data[i * 5]['COD'])
                print(cods)
                Body = {
                    "history": cods
                }
                res = requests.post(url=Edge_URL+SVR_port,
                                    json=Body, verify=False)
                svr_res = json.loads(res.text)[
                    'data']['resp_data'][0]['predictresult']
                # print(svr_res)
                # 结合专家系统
                perceiveSystem.COD_predict = sum(np.multiply(np.array(expertSystem.weights), np.array([1, lstm_res, svr_res,
                                                                                                       expertSystem.hours_weight[expertSystem.cod_valid[
                                                                                                           'hour'][perceiveSystem.valid_data_num]][0],
                                                                                                       expertSystem.weekdays_weight[expertSystem.cod_valid['week'][perceiveSystem.valid_data_num]][0]])))
                print(perceiveSystem.COD_predict)
                # 预测残差进行控制
                ctrl = perceiveSystem.COD_predict - perceiveSystem.COD_virtual
                ctrl_index1 = len(expertSystem.ctrl_rule1)
                for i in range(ctrl_index1):
                    if perceiveSystem.COD_predict < expertSystem.ctrl_rule1[i]:
                        ctrl_index1 = i
                        break

                ctrl_index2 = len(expertSystem.ctrl_rule2)
                for i in range(ctrl_index2):
                    if ctrl < expertSystem.ctrl_rule2[i]:
                        ctrl_index2 = i
                        break

                print(perceiveSystem.DO_set, perceiveSystem.DO_virtual)
                perceiveSystem.DO_set = 2 + 0.05 * ctrl_index1
                print(ctrl_index1, ctrl_index2)
                ctrl_index2 = min(max(ctrl_index2 + round((perceiveSystem.DO_set - perceiveSystem.DO_virtual) * 40), 0),
                                  10)  # DO反馈

                # 桨叶定时开关，开5s 关10s
                if ctrlSystem.switch[0] == 'OFF' and ctrlSystem.switch[1] == 'OFF':
                    if ctrlSystem.auto_time % 3 == 0:
                        fan_commend = 'TT'
                    else:
                        fan_commend = 'FF'
                elif ctrlSystem.switch[0] == 'ON' and ctrlSystem.switch[1] == 'ON':
                    fan_commend = 'FF'

                # 曝气石间歇曝气
                switch_commends = ['FFFF', 'FFTF', 'FTFF', 'FFFT', 'TFFF',
                                   'TTFF', 'TFFT', 'FTFT', 'FTTF', 'FFTT',
                                   'TFTF', 'TTTF', 'FTTT', 'TFTT', 'TTFT',
                                   'TTTT']
                switch_commend = switch_commends[ctrl_index1]
                if switch_commend.count('T') == 1:
                    temp = list('FFFF')
                    temp[(switch_commend.index('T') +
                          ctrlSystem.auto_time) % 4] = 'T'
                    switch_commend = ''.join(temp)
                elif switch_commend.count('T') == 2:
                    if ctrlSystem.auto_time % 2 == 0:
                        temp = list(switch_commend)
                        for i in range(len(temp)):
                            temp[i] = 'T' if temp[i] == 'F' else 'F'
                        switch_commend = ''.join(temp)
                elif switch_commend.count('T') == 3:
                    temp = list('TTTT')
                    temp[(switch_commend.index('F') +
                          ctrlSystem.auto_time) % 4] = 'F'
                    switch_commend = ''.join(temp)
                else:
                    pass

                # 回流泵根据COD常开
                pump_commends = ['FTF', 'FTF', 'FTF', 'FTF', 'FTF',
                                 'TFT', 'TFT', 'TFT', 'TFT', 'TFT',
                                 'TTT', 'TTT', 'TTT', 'TTT', 'TTT', 'TTT']
                pump_commend = pump_commends[ctrl_index1]
                large_commend = fan_commend + switch_commend + pump_commend  # 大调

                # 曝气盘精确曝气
                little_commends = ['000000', '111111', '222222', '333333', '444444',
                                   '555555', '666666', '777777', '888888', '999999', 'AAAAAA']
                little_commend = little_commends[ctrl_index2]  # 微调
                ctrl_commends = '20230810190159000000' + large_commend + little_commend

                url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot" \
                      r"/35bacf8d0d634b3f8a70fc9b5286d79d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
                Headers = {
                    "X-Auth-Token": token_jxy,
                    'Content-Type': 'application/json'}
                Body = {
                    "service_id": "All_Control_System",
                    "command_name": f"All_Control",
                    "paras": {
                        "Control_Flags": ctrl_commends
                    }
                }
                command = requests.post(url=url, json=Body, headers=Headers)
                # if command.status_code == 200:
                perceiveSystem.DO_virtual = max(min(perceiveSystem.DO_virtual + (ctrl_index1 - 8) * 0.02 +
                                                    0.005 * (ctrl_index2 - 5) + 0.001 * random.randint(-10, 10), 3), 2)
                print(perceiveSystem.DO_set, perceiveSystem.DO_virtual)
                print(ctrl_commends)
                print('***********************')
                ctrlSystem.auto_time += 1  # 自动控制次数+1
                ctrlSystem.frame_ctrl(ctrl_commends)
                ctrlSystem.power = ctrl_index1 * 0.5 + 0.1 * ctrl_index2
                time.sleep(5)


@app.route('/')
@cross_origin()
def start():
    """
    根目录，获取token，每次必须先启动以更新token
    :return: Get Token OK / Get Token Failed
    """

    def get_token(user_name, user_password, domain_name, scope_name='cn-north-4'):
        url = 'https://iam.' + scope_name + '.myhuaweicloud.com/v3/auth/tokens'
        Headers = {
            "Content-Type": "application/json"
        }
        Body = {
            "auth": {
                "identity": {
                    "methods": [
                        "password"
                    ],
                    "password": {
                        "user": {
                            "name": user_name,
                            "password": user_password,
                            "domain": {
                                "name": domain_name
                            }
                        }
                    }
                },
                "scope": {
                    "project": {
                        "name": scope_name
                    }
                }
            }
        }
        return requests.post(url=url, headers=Headers, json=Body)

    try:
        response_jxy = get_token(
            user_name='jx1', user_password='mayuguojia4', domain_name='hw091458930')
        response_gjq = get_token(
            user_name='IoT-Water', user_password='GJQ1030ab', domain_name='jiaqiyun')
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
    perceiveSystem.start_get()
    return 'Start get data and store into MySQL.'


@app.route('/stop_get')
@cross_origin()
def stop_get_data():
    """
    关闭获取数据线程
    :return: Stop get data and store into MySQL
    """
    perceiveSystem.stop_get()
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
            "history": [420.116, 425.049, 418.906]
            # "history": cods
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
    查询系统状态
    :return: 状态dict
    """
    return {'switch': ctrlSystem.switch, 'motor': ctrlSystem.motor, 'pump': ctrlSystem.pump,
            'COD': perceiveSystem.COD_virtual, 'COD_pre': perceiveSystem.COD_predict,
            'DO': perceiveSystem.DO_virtual, 'power': ctrlSystem.power}


@app.route('/AllControl', methods=['POST'])
@cross_origin()
def control_all():
    """
    统一控制格式
    :return: 状态码
    """
    url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d79d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
    Headers = {
        "X-Auth-Token": token_jxy,
        'Content-Type': 'application/json'}
    Body = {
        "service_id": "All_Control_System",
        "command_name": f"All_Control",
        "paras": {
            "Control_Flags": request.get_json()
        }
    }
    # print(request.get_data())  # 二进制字节流
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    if res == 200:
        ctrlSystem.frame_ctrl(request.get_json())
    return str(res)


@app.route('/reset')
@cross_origin()
def reset_ctrl():
    """
    重置控制系统
    :return: 状态码
    """
    url = r"https://59a6084cfa.st1.iotda-app.cn-north-4.myhuaweicloud.com:443/v5/iot/35bacf8d0d634b3f8a70fc9b5286d79d/devices/63dcdaa2352830580e47364e_2023_3_25/commands"
    Headers = {
        "X-Auth-Token": token_jxy,
        'Content-Type': 'application/json'}
    Body = {
        "service_id": "All_Control_System",
        "command_name": f"All_Control",
        "paras": {
            "Control_Flags": "00000000000000000000FFFFFFFFF000000"
        }
    }
    # print(request.get_data())  # 二进制字节流
    command = requests.post(url=url, json=Body, headers=Headers)
    res = command.status_code
    # print(res)
    if res == 200:
        ctrlSystem.frame_ctrl("00000000000000000000FFFFFFFFF000000")
        ctrlSystem.stop_auto()
    return str(res)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
