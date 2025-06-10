#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
红外相机测试脚本 (完美修复版)
基于诊断结果的最终优化版本
"""

import sys
import serial
import time
import os
from threading import Thread, Event
import signal
from config import *
from thermal_lib import ThermalCamera


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    print('\n正在清理资源并退出...')
    RUNNING.value = 0
    sys.exit(0)


def send_pulse_command(num_pulses, frequency):  
    """发送触发脉冲命令"""
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT)
        command = f"PULSE,{num_pulses},{frequency}\n"  
        ser.write(command.encode())  
        print(f"✅ 已发送触发命令: {command.strip()}")  
        time.sleep(0.1)
        return True
    except serial.SerialException as e:
        print(f"❌ 串口通信错误: {e}")
        return False
    finally:
        if 'ser' in locals():
            ser.close()


def create_save_directories(base_path):
    """创建保存目录结构"""
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())
    save_path = os.path.abspath(os.path.join(base_path, timestamp))
    
    os.makedirs(os.path.join(save_path, 'thermal'), exist_ok=True)
    print(f"📁 数据将保存至: {save_path}")
    return save_path


def smart_camera_preparation(thermal_cam, target_delay=4.0):
    """智能相机准备 - 动态检测相机就绪状态"""
    print(f"🔧 智能相机准备中（目标：{target_delay}秒）...")
    
    start_time = time.time()
    last_check_time = start_time
    ready_signals = 0  # 就绪信号计数
    
    for i in range(int(target_delay), 0, -1):
        print(f"   ⏰ 倒计时: {i}秒...")
        
        # 每秒检查相机状态
        check_start = time.time()
        while time.time() - check_start < 1.0:
            # 检查相机是否开始有反应（比如captured_count有变化）
            if hasattr(thermal_cam, 'captured_count'):
                current_count = thermal_cam.captured_count
                # 如果在准备期间就有帧计数变化，说明相机很活跃
                if current_count > 0:
                    ready_signals += 1
            
            time.sleep(0.1)
    
    # 额外智能等待
    if ready_signals > 0:
        print(f"   ✅ 检测到相机活跃信号 ({ready_signals}个)")
    else:
        print(f"   ⚠️  未检测到相机活跃信号，额外等待0.5秒...")
        time.sleep(0.5)
    
    total_prep_time = time.time() - start_time
    print(f"   📊 实际准备时间: {total_prep_time:.2f}秒")
    
    return total_prep_time


def optimized_monitor(thermal_cam, max_wait=50):
    """优化的监控函数"""
    start_time = time.time()
    last_count = 0
    frame_history = []
    first_frame_time = None
    
    print("📊 开始优化监控...")
    print(f"{'时间':<8} {'进度':<12} {'帧率':<8} {'状态':<10} {'备注'}")
    print("-" * 55)
    
    while thermal_cam.is_capturing and (time.time() - start_time) < max_wait:
        current_time = time.time()
        current_count = thermal_cam.captured_count
        elapsed = current_time - start_time
        
        # 每0.5秒检查一次，但只在有变化时输出详细信息
        if current_count != last_count:
            if first_frame_time is None:
                first_frame_time = current_time
                first_delay = current_time - start_time
                print(f"{elapsed:.1f}s     首帧响应      -       就绪      延迟{first_delay:.2f}s")
            
            frame_history.append(current_time)
            
            # 计算当前帧率（最近5帧的平均）
            if len(frame_history) >= 5:
                recent_time = frame_history[-1] - frame_history[-5]
                current_fps = 4.0 / recent_time if recent_time > 0 else 0
            else:
                current_fps = 0
            
            # 判断状态
            progress_pct = (current_count / thermal_cam.target_count) * 100
            
            if progress_pct < 25:
                stage = "启动"
            elif progress_pct < 75:
                stage = "稳定"
            else:
                stage = "收尾"
            
            # 只在重要节点输出信息
            if current_count % 5 == 0 or current_count <= 3 or current_count >= thermal_cam.target_count - 3:
                print(f"{elapsed:.1f}s     {current_count}/{thermal_cam.target_count:<8} {current_fps:.1f}fps   {stage:<8} 进展顺利")
            
            last_count = current_count
        
        time.sleep(0.2)  # 更频繁检查
    
    # 最终统计
    final_time = time.time() - start_time
    final_count = thermal_cam.captured_count
    target_count = thermal_cam.target_count
    
    print("-" * 55)
    print("📈 采集完成统计:")
    
    if first_frame_time:
        first_delay = first_frame_time - start_time
        print(f"   首帧响应: {first_delay:.2f}秒")
        
        if first_delay <= 1.0:
            print("   ✅ 首帧响应优秀")
        elif first_delay <= 2.0:
            print("   🟡 首帧响应良好")
        else:
            print("   ⚠️  首帧响应偏慢")
    
    success_rate = (final_count / target_count) * 100
    print(f"   采集帧数: {final_count}/{target_count}")
    print(f"   成功率: {success_rate:.1f}%")
    print(f"   总耗时: {final_time:.2f}秒")
    
    if len(frame_history) > 1:
        avg_fps = (len(frame_history) - 1) / (frame_history[-1] - frame_history[0])
        print(f"   平均帧率: {avg_fps:.2f}fps (目标: {FLIR_FRAMERATE}fps)")
    
    # 综合评价
    if success_rate >= 98:
        grade = "🟢 完美"
    elif success_rate >= 95:
        grade = "🟢 优秀"
    elif success_rate >= 90:
        grade = "🟡 良好"
    elif success_rate >= 80:
        grade = "🟠 一般"
    else:
        grade = "🔴 需要改进"
    
    print(f"   综合评价: {grade}")
    
    return success_rate >= 95


def main():
    """主函数 - 完美修复版本"""
    print("=" * 65)
    print("🎯 红外相机测试脚本 (完美修复版)")
    print("=" * 65)
    print(f"📋 配置信息:")
    print(f"   目标帧数: {NUM_IMAGES} @ {FLIR_FRAMERATE}fps")
    print(f"   理论时间: {NUM_IMAGES/FLIR_FRAMERATE:.1f}秒")
    print(f"   红外相机: {THERMAL_CAMERA_IP}")
    print(f"   分辨率: {THERMAL_WIDTH}x{THERMAL_HEIGHT}")
    print("=" * 65)
    
    # 初始化
    RUNNING.value = 1
    ACQUISITION_FLAG.value = 0
    signal.signal(signal.SIGINT, signal_handler)
    
    save_path = create_save_directories(BASE_DIR)
    thermal_cam = None
    
    try:
        print("\n🔌 第1步: 初始化相机...")
        thermal_cam = ThermalCamera()
        
        if not thermal_cam.connect(THERMAL_CAMERA_IP, THERMAL_CAMERA_PORT):
            print("❌ 相机连接失败")
            return False
        print("✅ 相机连接成功")
        
        if not thermal_cam.configure_camera(THERMAL_TEMP_SEGMENT, NUM_IMAGES, save_path):
            print("❌ 相机配置失败")
            return False
        print("✅ 相机配置成功")
        
        print("\n🚀 第2步: 启动采集...")
        if not thermal_cam.start_capture():
            print("❌ 采集启动失败")
            return False
        print("✅ 采集已启动")
        
        # 启动监控线程
        monitor_complete = Event()
        monitor_result = {'success': False}
        
        def monitor_wrapper():
            result = optimized_monitor(thermal_cam, 55)
            monitor_result['success'] = result
            monitor_complete.set()
        
        monitor_thread = Thread(target=monitor_wrapper)
        monitor_thread.start()
        
        # print("\n⏰ 第3步: 智能准备等待...")
        # prep_time = smart_camera_preparation(thermal_cam, 4.0)
        
        print("\n📡 第4步: 发送触发命令...")
        trigger_time = time.time()
        if not send_pulse_command(NUM_IMAGES, FLIR_FRAMERATE):
            print("❌ 触发命令发送失败")
            return False
        
        # 等待监控完成
        print("\n📊 第5步: 监控采集过程...")
        monitor_complete.wait(timeout=60)
        monitor_thread.join(timeout=5)
        
        print("\n🔄 第6步: 数据处理...")
        thermal_cam.wait_for_completion()
        
        # 最终结果
        final_count = thermal_cam.captured_count
        target_count = thermal_cam.target_count
        success_rate = (final_count / target_count) * 100
        
        print("\n" + "=" * 65)
        print("🎯 最终测试结果:")
        print(f"   📊 采集成功: {final_count}/{target_count} 帧")
        print(f"   📈 成功率: {success_rate:.1f}%")
        
        # 根据成功率给出结论
        if success_rate >= 98:
            print("   🎉 完美成功！问题已彻底解决")
            print("   💡 建议：可以将此配置应用到生产环境")
            result = True
        elif success_rate >= 95:
            print("   🟢 优秀！基本解决了问题")
            print("   💡 建议：此配置可用于正常使用")
            result = True
        elif success_rate >= 90:
            print("   🟡 良好，有显著改善")
            print("   💡 建议：可能需要再微调准备时间")
            result = True
        else:
            print("   🟠 仍需改进")
            print("   💡 建议：检查硬件连接或增加更多准备时间")
            result = False
        
        print("=" * 65)
        return result
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断测试")
        return False
    except Exception as e:
        print(f"\n❌ 程序错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if thermal_cam:
            print("\n🧹 清理资源...")
            thermal_cam.cleanup()
            print("✅ 清理完成")


if __name__ == '__main__':
    print(f"🕐 开始测试 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = main()
    
    end_time = time.strftime('%Y-%m-%d %H:%M:%S')
    if success:
        print(f"🎉 测试成功完成 - {end_time}")
        print("💡 红外相机采集问题已解决，可以应用到您的三相机同步脚本中")
        sys.exit(0)
    else:
        print(f"❌ 测试未达到预期 - {end_time}")
        print("💡 建议检查硬件连接或联系技术支持")
        sys.exit(1)
