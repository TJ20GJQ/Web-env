import time
import serial

ser = serial.Serial(  # 下面这些参数根据情况修改
    port='COM5',  # 串口
    baudrate=19200,  # 波特率
    parity='O',
    stopbits=serial.STOPBITS_TWO,
    bytesize=serial.SEVENBITS

)
every_time = time.strftime('%Y-%m-%d %H:%M:%S')  # 时间戳
data = ''
a = "0d 03 00 02 00 02"
while True:
    ser.write(bytes.fromhex(a))
    time.sleep(1)
    print(1)
    data = ser.readline()
    print(every_time, data)
