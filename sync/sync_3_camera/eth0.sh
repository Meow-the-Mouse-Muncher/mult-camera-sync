# 1. 将网络中断绑定到专用CPU核心
echo 4-5 > /proc/irq/$(grep etn0 /proc/interrupts | cut -d: -f1 | head -1)/smp_affinity_list

# 2. 设置网络接收缓冲区
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.rmem_default=1048576
sudo sysctl -w net.core.netdev_max_backlog=5000