import threading
import time
def increment(msg,sleep_time):
    val = 0
    print("Inside increment")
    for x in range(500):
        val += 1
        print("%s : %d\n" % (msg,val))
        time.sleep(sleep_time)
thread1 = threading.Thread(target=increment, args=("thread_01",0.5))
thread2 = threading.Thread(target=increment, args=("thread_02",0.5))
thread1.start()
thread2.start()
thread1.join()
thread2.join()