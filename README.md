# Web-env
#### *IoT-Water —— 项目后端*  
**定义路由：**  
* /：启动获取token  
* /start_get：启动获取数据并存入数据库  
* /query：查询历史数据并取最后一个  
* /lstm：使用LSTM算法预测下一个COD数据（维护中）  
* /svm：使用SVM算法预测下一个COD数据（维护中）  

***2023-07-07***  
* 添加 /stop_get：停止获取数据并存入数据库  
* 细化 /query：  
/query&lt;num>：查询最新num条数据  
/queryIn&lt;period>：支持GET/POST方法，GET查询最近一小时/一天/一月的数据，POST提交form查询某一时间段的数据  
* 添加 /ctrl_motor&lt;num>/&lt;speed>：控制第num个气泵的速度为speed  
* 添加 /ctrl_switch&lt;num>/&lt;state>：控制第num个气泵的状态为state  
* 添加 /autoCtrl：启动自动控制曝气，原理为查询数据库最新48个COD数据进行预测，根据LSTM预测结果，手动划分共13个挡位（可更改）  
* 添加 /stopAutoCtrl：停止自动控制曝气  

***2023-07-25***
* 创建ctrl_system：同步控制系统状态，并设置自动控制
* 添加 /ctrl_pump&lt;num>/&lt;state>：控制第num个蠕动泵的状态为state
* 添加 /query_state：查询控制系统状态

***2023-08-17***
* 创建perceive_system，同步模拟COD和DO数据
* 创建expert_system，专家系统，修改自动控制曝气规则
* 添加 /control_all：统一控制指令数据格式，实现批量控制
* 添加 /reset：一键重置控制系统状态
* 启动自动控制多线程

* **2023-08-25***
* First Prize!
