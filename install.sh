#!/bin/bash

# ==========================================
# Windows 10 UAC 全局安装器 (终极防卡死版)
# ==========================================

SELF_PATH="$(readlink -f "$0")"
SRC_DIR="$(dirname "$SELF_PATH")"

# 核心安全机制：只要不是 root 权限，立刻弹出系统原生密码框
if [ "$(id -u)" -ne 0 ]; then
    exec pkexec env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" bash "$SELF_PATH" "$@"
fi

# ==========================================
# 以下代码 100% 只有在获得 root 权限后才会执行
# ==========================================

# 检查依赖
if ! command -v zenity &> /dev/null; then
    zenity --error --title="错误" --text="缺少 zenity，请在终端运行：/usr/bin/sudo apt install zenity" --width=350
    exit 1
fi

# 检查核心文件是否存在
if [ ! -f "$SRC_DIR/uac.py" ] || [ ! -f "$SRC_DIR/windows-10-uac.mp3" ]; then
    zenity --error --title="错误" --text="找不到 uac.py 或 windows-10-uac.mp3！\n请确保它们和本脚本放在一起。" --width=350
    exit 1
fi

# 弹出主选择菜单
ACTION=$(zenity --list --title="Windows 10 UAC 体验包" \
    --text="权限已验证。请选择你要执行的操作：" \
    --column="操作选项" \
    "🚀 安装到系统" \
    "🗑️ 从系统卸载" \
    --width=400 --height=250)

if [ -z "$ACTION" ]; then
    exit 0
fi

# ==========================================
# 执行安装
# ==========================================
if [ "$ACTION" == "🚀 安装到系统" ]; then
    UAC_DIR="/usr/local/lib/sudo-uac"
    SUDO_WRAPPER="/usr/local/bin/sudo"
    
    mkdir -p "$UAC_DIR"
    cp "$SRC_DIR/uac.py" "$UAC_DIR/uac.py"
    cp "$SRC_DIR/windows-10-uac.mp3" "$UAC_DIR/windows-10-uac.mp3"
    chmod -R 755 "$UAC_DIR"

    # 写入终极完美包装器（带外层循环验证）
    cat << 'EOF' > "$SUDO_WRAPPER"
#!/bin/bash
REAL_SUDO="/usr/bin/sudo"
UAC_SCRIPT="/usr/local/lib/sudo-uac/uac.py"

# 1. 每次强制清空缓存，保证必须弹窗
"$REAL_SUDO" -k
unset SUDO_ASKPASS

# 2. 只在交互式终端 + 图形界面时拦截（后台任务直接放行）
if tty -s && { [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; }; then
    if [ -x "$UAC_SCRIPT" ]; then
        
        if [ $# -eq 0 ]; then
            exec "$REAL_SUDO" "$@"
        fi

        # 过滤掉可能混入的 -A 参数
        ARGS=()
        for arg in "$@"; do
            if [ "$arg" != "-A" ]; then
                ARGS+=("$arg")
            fi
        done

        # 把当前命令写给 uac.py 显示
        UID_VAL=$(id -u)
        CMD_FILE="/tmp/.sudo-uac-cmd-$UID_VAL"
        echo "$*" > "$CMD_FILE"
        
        # 初始化错误状态标记
        export UAC_ERROR=0

        # 验证死循环（防止假死）
        while true; do
            # 弹窗获取密码
            PW=$("$UAC_SCRIPT")
            ret=$?
            
            if [ $ret -ne 0 ] || [ -z "$PW" ]; then
                # 用户点取消或关闭窗口
                echo -e "\n\033[90m提示: UAC 已取消。可用原生终端密码重试: /usr/bin/sudo $*\033[0m"
                rm -f "$CMD_FILE"
                exit 1
            fi
            
            # 把密码喂给系统原生 sudo 去执行
            printf "%s\n" "$PW" | "$REAL_SUDO" -S -p "" "${ARGS[@]}"
            ret=$?
            
            if [ $ret -eq 0 ]; then
                # 执行成功，清理临时文件退出
                rm -f "$CMD_FILE"
                exit 0
            else
                # 密码错误，将状态设为 1，外层循环会再次启动 uac.py，uac.py 看到这个标记就会显示红字
                export UAC_ERROR=1
            fi
        done
    fi
fi

# 后台调用或非图形环境，退回原生
exec "$REAL_SUDO" "$@"
EOF

    chmod +x "$SUDO_WRAPPER"
    
    # 创建 tsudo 逃生舱
    ln -sf "/usr/bin/sudo" "/usr/local/bin/tsudo"
    
    zenity --info --title="安装成功" --text="✅ 安装成功！\n\n只有在终端手动敲 sudo 才会弹窗。\n如果输错密码会秒重弹并提示红字，绝不卡死！\n\n💡 终端原生密码请用: tsudo" --width=350

# ==========================================
# 执行卸载
# ==========================================
elif [ "$ACTION" == "🗑️ 从系统卸载" ]; then
    rm -f "/usr/local/bin/sudo"
    rm -f "/usr/local/bin/tsudo"
    rm -rf "/usr/local/lib/sudo-uac"
    
    zenity --info --title="卸载成功" --text="✅ 卸载成功！\n\n系统的 sudo 已恢复原状。" --width=350
fi