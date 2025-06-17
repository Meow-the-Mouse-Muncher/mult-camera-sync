#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时线程优先级管理模块
用于Xavier NX开发板上的多相机同步采集系统
"""

import os
import sys
import threading
import ctypes
import ctypes.util
from ctypes import c_int, c_uint, c_ulong, c_void_p, Structure, POINTER

# 调度策略常量
SCHED_NORMAL = 0
SCHED_FIFO = 1
SCHED_RR = 2

# 加载系统库
libc = ctypes.CDLL(ctypes.util.find_library('c'))

class sched_param(Structure):
    _fields_ = [("sched_priority", c_int)]

def check_tegra_rt_support():
    """检查Tegra平台的实时调度支持"""
    try:
        # 检查/proc/sys/kernel/sched_rt_*
        rt_period = 0
        rt_runtime = 0
        try:
            with open('/proc/sys/kernel/sched_rt_period_us', 'r') as f:
                rt_period = int(f.read().strip())
            with open('/proc/sys/kernel/sched_rt_runtime_us', 'r') as f:
                rt_runtime = int(f.read().strip())
        except:
            pass
            
        # 如果rt_runtime为-1，表示禁用了实时调度限制
        if rt_runtime == -1:
            return True
        elif rt_runtime == 0:
            return False
        else:
            return True
            
    except Exception as e:
        return False

def set_thread_priority_xavier_compatible(priority, policy=SCHED_FIFO, thread_id=None):
    """Xavier兼容的线程优先级设置"""
    if thread_id is None:
        thread_id = threading.get_native_id()
    
    param = sched_param()
    param.sched_priority = priority
    
    # 方法1: 尝试实时调度
    for try_policy in [SCHED_FIFO, SCHED_RR]:
        result = libc.sched_setscheduler(thread_id, try_policy, ctypes.byref(param))
        if result == 0:
            return True
    
    # 方法2: 如果实时调度失败，尝试CFS调度 + nice值
    try:
        # 设置为SCHED_NORMAL，但调整nice值
        param.sched_priority = 0  # SCHED_NORMAL的优先级必须是0
        result = libc.sched_setscheduler(thread_id, SCHED_NORMAL, ctypes.byref(param))
        
        if result == 0:
            # 设置nice值以提高优先级
            nice_value = -15  # 高优先级nice值
            nice_result = libc.setpriority(0, thread_id, nice_value)  # PRIO_PROCESS = 0
            
            if nice_result == 0:
                return True
    except Exception as e:
        pass
    
    # 方法3: 如果都失败，至少尝试调整进程级别的优先级
    try:
        pid = os.getpid()
        nice_result = libc.setpriority(0, pid, -10)  # PRIO_PROCESS = 0
        if nice_result == 0:
            return True
    except Exception as e:
        pass
    
    # 最后的备选方案：不设置优先级但继续运行
    return False

def setup_realtime_thread_xavier_compatible(priority=99, policy=SCHED_FIFO, cpu_list=None):
    """Xavier兼容的实时线程设置"""
    thread_id = threading.get_native_id()
    
    # 1. 尝试设置优先级（不强制成功）
    priority_success = set_thread_priority_xavier_compatible(priority, policy, thread_id)
    
    # 2. 设置CPU亲和性
    cpu_success = True
    if cpu_list:
        cpu_success = set_cpu_affinity(cpu_list, thread_id)
    
    return priority_success or cpu_success  # 只要有一个成功就算成功

def set_cpu_affinity(cpu_list, thread_id=None):
    """设置CPU亲和性"""
    if thread_id is None:
        thread_id = threading.get_native_id()
    
    try:
        cpu_set = 0
        for cpu in cpu_list:
            if cpu < 6:  # Xavier NX有6个核心
                cpu_set |= (1 << cpu)
        
        result = libc.sched_setaffinity(thread_id, 8, ctypes.byref(ctypes.c_ulong(cpu_set)))
        
        if result == 0:
            return True
        else:
            return False
            
    except Exception as e:
        return False

def check_realtime_permissions():
    """检查实时权限 - Xavier兼容版"""
    uid = os.getuid()
    
    if uid != 0:
        # print("运行权限: 非root (某些优化可能受限)")
        return False
    
    print("运行权限: root (优化功能已启用)")
    
    # 检查Xavier特定的实时调度支持
    rt_support = check_tegra_rt_support()
    
    return True

def print_system_info():
    """打印系统信息 - Xavier兼容版"""
    # print("=== Xavier NX 三相机同步采集系统 ===")
    
    # 检查权限（不强制退出）
    check_realtime_permissions()
    
    # 检查CPU信息
    try:
        cpu_count = os.cpu_count()
        # print(f"CPU配置: {cpu_count}核心 (Denver 0-1, ARM A78 2-5)")
    except:
        print("CPU配置: 未知")
    
    print("=" * 35)
    return True

# 兼容性别名
setup_realtime_thread = setup_realtime_thread_xavier_compatible
set_thread_priority = set_thread_priority_xavier_compatible

class HighPriorityThreadPool:
    """Xavier兼容的高优先级线程池"""
    
    def __init__(self, max_workers=4, thread_priority=30):
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.thread_priority = thread_priority
        self._setup_threads()
    
    def _setup_threads(self):
        """为线程池中的线程设置优先级"""
        futures = []
        for i in range(self.executor._max_workers):
            future = self.executor.submit(self._setup_worker_thread, i)
            futures.append(future)
        
        # 等待所有线程设置完成
        for future in futures:
            try:
                future.result(timeout=2)
            except:
                pass
    
    def _setup_worker_thread(self, worker_id):
        """设置工作线程的优先级"""
        if worker_id < 2:
            cpu_list = [2, 3]
        else:
            cpu_list = [4, 5]
            
        setup_realtime_thread_xavier_compatible(
            priority=self.thread_priority, 
            policy=SCHED_FIFO, 
            cpu_list=cpu_list
        )
    
    def submit(self, fn, *args, **kwargs):
        """提交任务"""
        return self.executor.submit(fn, *args, **kwargs)
    
    def shutdown(self, wait=True):
        """关闭线程池"""
        self.executor.shutdown(wait=wait)

def set_thread_nice_priority(nice_value, thread_id=None, cpu_list=None):
    """基于nice值设置线程优先级
    Args:
        nice_value: nice值 (-20到19，数值越小优先级越高)
        thread_id: 线程ID，None表示当前线程
        cpu_list: CPU亲和性列表
    Returns:
        bool: 设置是否成功
    """
    if thread_id is None:
        thread_id = threading.get_native_id()
    
    success_count = 0
    total_operations = 2  # nice值设置 + CPU亲和性设置
    
    # 1. 设置nice值
    try:
        # 使用setpriority系统调用设置线程的nice值
        # PRIO_PROCESS = 0, 对指定的线程ID设置优先级
        result = libc.setpriority(0, thread_id, nice_value)
        if result == 0:
            success_count += 1
        else:
            errno = ctypes.get_errno()
            print(f"✗ 线程 {thread_id} nice值设置失败: errno={errno}")
    except Exception as e:
        print(f"✗ 线程 {thread_id} nice值设置异常: {e}")
    
    # 2. 设置CPU亲和性
    if cpu_list:
        if set_cpu_affinity(cpu_list, thread_id):
            success_count += 1
        else:
            print(f"✗ 线程 {thread_id} CPU亲和性设置失败")
    else:
        total_operations = 1  # 只有nice值设置
    
    success = success_count == total_operations
    
    return success

def setup_nice_thread(nice_value, cpu_list=None):
    """设置当前线程的nice优先级和CPU亲和性
    Args:
        nice_value: nice值 (-20到19，数值越小优先级越高)
        cpu_list: CPU亲和性列表
    Returns:
        bool: 设置是否成功
    """
    thread_id = threading.get_native_id()
    return set_thread_nice_priority(nice_value, thread_id, cpu_list)
