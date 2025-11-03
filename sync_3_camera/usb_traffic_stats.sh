#!/bin/bash
# usb_traffic_stats.sh

echo "监控USB流量统计 (每秒更新)"
echo "设备: Cypress 04b4:00f5"
echo "=========================="

# 临时文件
TEMP_FILE="/tmp/usb_traffic.tmp"

# 函数：计算流量
calculate_traffic() {
    # 启动usbmon监控并保存到临时文件
    sudo timeout 1s cat /sys/kernel/debug/usb/usbmon/1u > "$TEMP_FILE" 2>/dev/null
    
    if [[ -s "$TEMP_FILE" ]]; then
        # 解析数据包，计算字节数
        total_bytes=$(awk '{
            # 查找数据长度字段
            for(i=1; i<=NF; i++) {
                if($i ~ /^[0-9]+$/ && $i > 0 && $i < 10000) {
                    total += $i
                }
            }
        } END {
            print total + 0
        }' "$TEMP_FILE")
        
        # 转换为KB/s
        kb_per_sec=$(echo "scale=2; $total_bytes / 1024" | bc 2>/dev/null || echo "0")
        
        echo "$(date '+%H:%M:%S') - USB流量: ${kb_per_sec} KB/s (${total_bytes} bytes/s)"
    else
        echo "$(date '+%H:%M:%S') - 无USB活动检测到"
    fi
    
    # 清理临时文件
    rm -f "$TEMP_FILE"
}

# 主循环
while true; do
    calculate_traffic
    sleep 1
done