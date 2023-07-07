# Web-env
IoT-Water下的python文件为项目后端
定义路由：
/：启动获取token
/start_get：启动获取数据并存入数据库
/stop_get：停止获取数据并存入数据库
/query<num>：查询最新num条数据
/queryIn<period>：支持GET/POST方法，GET查询最近一小时/一天/一月的数据，POST提交form查询某一时间段的数据
/lstm：使用LSTM算法预测下一个COD数据（维护中）
/svm：使用SVM算法预测下一个COD数据（维护中）
/ctrl_motor<num>/<speed>：控制第num个气泵的速度为speed
/ctrl_switch<num>/<state>：控制第num个气泵的状态为state
/autoCtrl：启动自动控制曝气，原理为查询数据库最新48个COD数据进行预测，根据LSTM预测结果，手动划分共13个挡位
/stopAutoCtrl：停止自动控制曝气
