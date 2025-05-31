#!/bin/bash
echo "开始Xavier NX性能优化..."

# 1. 设置电源模式为最高性能
echo "设置电源模式..."
sudo nvpmodel -m 0 2>/dev/null || sudo nvpmodel -m 2 2>/dev/null || echo "电源模式设置失败"

# 2. 启用jetson_clocks
echo "启用最大时钟频率..."
sudo jetson_clocks

# 3. 设置CPU调节器
echo "设置CPU性能模式..."
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null

# 4. 禁用USB自动挂起
echo "禁用USB自动挂起..."
echo -1 | sudo tee /sys/module/usbcore/parameters/autosuspend > /dev/null

# 5. 网络优化
echo "优化网络设置..."
sudo ethtool -K eth0 gro off lro off 2>/dev/null || echo "网络GRO/LRO优化跳过"
sudo ethtool -s eth0 wol d 2>/dev/null || echo "Wake-on-LAN禁用跳过"

# 6. 显示当前状态
echo "优化完成，当前状态："
echo "电源模式:"
sudo nvpmodel -q
echo "CPU调节器:"
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo "USB autosuspend:"
cat /sys/module/usbcore/parameters/autosuspend

echo "Xavier NX性能优化完成！"