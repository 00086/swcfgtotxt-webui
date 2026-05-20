import csv
import datetime
import os
import re
import socket
import struct
import threading
import time
from flask import Flask, render_template, jsonify, request
from netmiko import ConnectHandler
import webview  # 記得在檔案最上方或是這裡 import webview

# --- Flask 初始化 ---
app = Flask(__name__)

# --- 參數設定 ---
VERSION = "v3.0 (Flask WebUI Edition)"
CSV_FILE = 'devices.csv'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_RETRIES = 3

# --- 參數設定 ---
VERSION = "v1.0 (WebUI + CSV Editor)"
CSV_FILE = 'devices.csv'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_RETRIES = 3 

# ================= 新增：自動初始化 CSV =================
def init_csv_file():
    """如果 CSV 檔案不存在，自動建立並寫入標題行"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', encoding='utf-8') as f:
            f.write("ip,username,password,secret,device_type\n")
            
# 程式啟動時執行一次檢查
init_csv_file()
# ======================================================

# 全域變數：用於網頁前端抓取即時日誌與狀態
global_logs = []
backup_is_running = False
current_timestamp_dir = ""

# 👇 新增：用來記錄每台 IP 目前的備份狀態 (例如: 'waiting', 'running', 'success', 'fail')
device_status_map = {}

# ================= 新增：中斷訊號旗標 =================
backup_cancel_event = threading.Event() 
# ======================================================

# ================= 新增：記錄目前正在備份的設備 IP =================
current_running_ip = None  
# ==============================================================

def web_log(msg):
    """將原本的 print 替換為 web_log，同時輸出至終端機與網頁暫存"""
    clean_msg = str(msg).replace('\r', '')
    print(clean_msg)
    global_logs.append(clean_msg)

# ---------------- TFTP 伺服器 (與原本相同) ----------------
def get_local_ip_fallback(target_host):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_host, 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()
    return local_ip

class GlobalTFTPServer:
    def __init__(self):
        self.save_dir = ""
        self.sock = None
        self.running = False
        self.current_bind_ip = '0.0.0.0'
        self.completed_transfers = set()

    def start(self, save_dir):
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        
        if self.running: return
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(('0.0.0.0', 69))
            self.running = True
            threading.Thread(target=self._listen_loop, daemon=True).start()
            web_log("[*] 內建 TFTP 伺服器已啟動 (強制標準相容模式)")
        except Exception as e:
            web_log(f"[!] TFTP 啟動失敗: {e}")

    def stop(self):
        self.running = False
        if self.sock:
            try: self.sock.close()
            except: pass

    def _listen_loop(self):
        self.sock.settimeout(1.0) 
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
                if len(data) < 4: continue
                opcode = struct.unpack("!H", data[0:2])[0]
                if opcode == 2:
                    parts = data[2:].split(b'\x00')
                    filename = parts[0].decode('utf-8', errors='ignore')
                    safe_filename = os.path.basename(filename) 
                    save_path = os.path.join(self.save_dir, safe_filename)
                    web_log(f"    [TFTP] 收到備份請求: {safe_filename}")
                    threading.Thread(target=self._handle_transfer, args=(addr, save_path, safe_filename), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                pass

    def _handle_transfer(self, client_addr, save_path, safe_filename):
        transfer_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: transfer_sock.bind((self.current_bind_ip, 0))
        except: transfer_sock.bind(('0.0.0.0', 0))
            
        blksize = 512
        init_packet = struct.pack("!HH", 4, 0)
        try: transfer_sock.sendto(init_packet, client_addr)
        except Exception as e: return
            
        expected_block = 1
        last_active = time.time()
        transfer_sock.settimeout(2.0)
        has_written = False
        try:
            with open(save_path, "wb") as f:
                while self.running:
                    if time.time() - last_active > 15: break
                    try:
                        packet, addr = transfer_sock.recvfrom(blksize + 128)
                        if addr[0] != client_addr[0] or len(packet) < 4: continue  
                        op, block = struct.unpack("!HH", packet[:4])
                        if op == 3:
                            if block == expected_block:
                                f.write(packet[4:])
                                has_written = True
                                transfer_sock.sendto(struct.pack("!HH", 4, block), client_addr)
                                expected_block += 1
                                last_active = time.time() 
                                if len(packet[4:]) < blksize:
                                    web_log(f"    [TFTP] 二進位檔案 [{safe_filename}] 傳輸完成！")
                                    self.completed_transfers.add(safe_filename)
                                    break
                            elif block < expected_block:
                                transfer_sock.sendto(struct.pack("!HH", 4, block), client_addr)
                    except Exception:
                        continue
        finally:
            transfer_sock.close()
            if not has_written and os.path.exists(save_path):
                try: os.remove(save_path)
                except: pass

global_tftp = GlobalTFTPServer()

# ---------------- 備份核心邏輯 ----------------
def clean_hostname(prompt):
    if not prompt: return "Unknown_Host"
    name = re.sub(r'^(telnet|ssh)@', '', prompt)
    if '@' in name and '[' in name: name = name.split('@')[-1].split(']')[0]
    name = name.split('(')[0].split(' ')[0].split(':')[0]
    return name.replace('#', '').replace('>', '').replace('[', '').replace(']', '').replace('$', '').strip()

def clean_config_content(config_text, hostname):
    if not config_text: return ""
    cleaned = config_text.replace('\x1b[0K', '').replace('\x1b[K', '')
    lines = cleaned.splitlines()
    final_lines = []
    skip_keys = ["show running-config", "show run", "/export", "show config current_config", "show config running", "show full-configuration", "set cli pager off", "set cli config-output-format set", "set output standard", "disable clipaging", "Building configuration", "Current Configuration", "More:", "--More--", "a All", "Next Page", "CTRL+C", "Quit:", "config system console", "Command:", "Invalid input"]
    for line in lines:
        clean_line = line.strip()
        if not clean_line or any(key.lower() in clean_line.lower() for key in skip_keys): continue
        if len(clean_line) < 60 and (clean_line.endswith('#') or clean_line.endswith('>')):
            if hostname.lower() in clean_line.lower(): continue
        final_lines.append(line)
    return "\n".join(final_lines).strip()

def run_backup(device_params, backup_dir):
    ip = device_params['host']
    d_type = device_params.get('device_type', 'generic').lower()
    is_old_dlink = False 
    
    for attempt in range(1, MAX_RETRIES + 1):
        net_connect = None
        try:
            web_log(f"\n[*] [{attempt}/{MAX_RETRIES}] 連線至: {ip} ({d_type})...")
            device_params['global_delay_factor'] = 4
            device_params['timeout'] = 30
            device_params['session_timeout'] = 60
            
            if 'fortinet' in d_type or 'dlink' in d_type:
                device_params['global_delay_factor'] = 6
                device_params['fast_cli'] = False

            try:
                net_connect = ConnectHandler(**device_params)
            except Exception as e:
                if 'dlink' in d_type and ('Pattern not detected' in str(e) or 'timeout' in str(e).lower()):
                    device_params['device_type'] = 'cisco_ios_telnet' if 'telnet' in device_params['device_type'] else 'cisco_ios'
                    net_connect = ConnectHandler(**device_params)
                    is_old_dlink = True 
                else:
                    raise e

            prompt = net_connect.find_prompt()
            hostname = clean_hostname(prompt)
            web_log(f"    [>] 主機識別: {hostname}")

            ext = ".cfg"
            if 'mikrotik' in d_type: ext = ".rsc"
            elif 'paloalto' in d_type: ext = ".set"
            elif 'fortinet' in d_type: ext = ".conf"
            elif 'dlink' in d_type: ext = ".bin"
            
            filename = f"{ip}_{hostname}_{datetime.datetime.now().strftime('%Y%m%d')}{ext}"
            filepath = os.path.join(backup_dir, filename)

            if 'fortinet' in d_type:
                net_connect.send_command("config system console", expect_string=r'[#>]')
                net_connect.send_command("set output standard", expect_string=r'[#>]')
                net_connect.send_command("end", expect_string=r'[#>]')
                cmd_list = ["show full-configuration"]
            elif 'dlink' in d_type:
                if is_old_dlink: cmd_list = ["USE_TFTP_MODE_URL", "USE_TFTP_MODE_IP"]
                else:
                    net_connect.send_command("disable clipaging", expect_string=r'[#>]')
                    cmd_list = ["show config current_config", "show running-config", "USE_TFTP_MODE_URL", "USE_TFTP_MODE_IP"]
            elif 'paloalto' in d_type:
                net_connect.send_command("set cli pager off", expect_string=r'[#>]')
                net_connect.send_command("set cli config-output-format set", expect_string=r'[#>]')
                cmd_list = ["show config running"]
            elif 'mikrotik' in d_type: cmd_list = ["/export"]
            else:
                if ">" in prompt: net_connect.enable()
                if 'cisco' in d_type: net_connect.send_command("terminal length 0")
                cmd_list = ["show running-config"]

            config_data, tftp_success = "", False

            for cmd in cmd_list:
                if cmd.startswith("USE_TFTP_MODE"):
                    local_ip = None
                    try: local_ip = net_connect.remote_conn.get_socket().getsockname()[0]
                    except: local_ip = get_local_ip_fallback(ip)
                            
                    global_tftp.current_bind_ip = local_ip
                    global_tftp.completed_transfers.discard(filename)
                    tftp_cmd = f"upload cfg_toTFTP tftp://{local_ip}/{filename}" if cmd == "USE_TFTP_MODE_URL" else f"upload cfg_toTFTP {local_ip} {filename}"
                        
                    web_log(f"    [+] 寫入指令: {tftp_cmd}")
                    net_connect.write_channel(f"{tftp_cmd}\n")
                    
                    web_log("    [+] 等待檔案傳輸...")
                    wait_time = 0
                    while wait_time < 40:
                        if filename in global_tftp.completed_transfers:
                            tftp_success = True
                            break
                        try: net_connect.read_channel() 
                        except: pass
                        time.sleep(1)
                        wait_time += 1
                        
                    if tftp_success: break 
                    else: web_log(f"    [!] TFTP 超時，嘗試退回純文字模式...")
                    continue

                web_log(f"    [+] 嘗試擷取畫面: {cmd}")
                net_connect.write_channel(f"{cmd}\n")
                time.sleep(3)
                
                temp_data, idle_count = "", 0
                while idle_count < 12:
                    new_data = net_connect.read_channel()
                    if new_data:
                        temp_data += new_data
                        idle_count = 0
                        if any(x in new_data for x in ["Next Page", "a All", "Quit:"]): net_connect.write_channel("a") 
                        elif any(x in new_data for x in ["More:", "--More--"]): net_connect.write_channel(" ") 
                    else:
                        idle_count += 1
                        time.sleep(1)
                
                if "Invalid input" not in temp_data and "Unknown command" not in temp_data and len(temp_data) > 500:
                    config_data = temp_data
                    break

            if tftp_success:
                web_log(f"[OK] {ip} 透過內建 TFTP 備份完成")
                return True

            final_config = clean_config_content(config_data, hostname)
            if len(final_config) < 300: raise ValueError("備份內容過短或所有指令皆失敗")

            if filepath.endswith('.bin'): filepath = filepath[:-4] + ".cfg"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(final_config)
            web_log(f"[OK] {ip} 文字備份成功")
            return True

        except Exception as e:
            web_log(f"[!] {ip} 失敗: {str(e)}")
            if attempt < MAX_RETRIES: time.sleep(3)
        finally:
            if net_connect:
                try: net_connect.disconnect()
                except: pass
    return False

def get_device_list():
    devices = []
    if not os.path.exists(CSV_FILE): return devices
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row and row.get('ip'): devices.append(row)
    return devices

def run_backup_task(target_ip=None):
    global backup_is_running, current_timestamp_dir, current_running_ip, device_status_map

    backup_is_running = True
    global_logs.clear()
    backup_cancel_event.clear() 

    # 👇 每次任務開始前，重置所有設備的狀態為 'waiting' (等待中)
    devices = get_device_list()
    device_status_map = {dev['ip'].strip().lstrip('#'): 'waiting' for dev in devices}

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    current_timestamp_dir = os.path.join(BASE_DIR, "network_backups", timestamp)

    global_tftp.start(current_timestamp_dir)
    time.sleep(1)

    summary = {"success": 0, "fail": 0, "skipped": 0}
    failed_ips = []
    start_time_ts = time.time()
    web_log(f"========== 備份任務開始 ({'全部' if not target_ip else target_ip}) ==========")

    for dev in devices:
        if backup_cancel_event.is_set():
            web_log("\n[🛑] 收到使用者中斷指令，停止後續備份任務。")
            break

        raw_ip = dev['ip'].strip()
        clean_ip = raw_ip.lstrip('#')

        if target_ip and clean_ip != target_ip:
            # 如果不是本次指定的單機備份目標，不改動其狀態（維持 waiting 或不顯示）
            continue

        if raw_ip.startswith('#') and not target_ip:
            summary["skipped"] += 1
            web_log(f"[跳過] {clean_ip} (已在 CSV 中標記 #)")
            device_status_map[clean_ip] = 'skipped' # 標記跳過
            continue

        current_running_ip = clean_ip
        # 👇 標記目前這台正在執行
        device_status_map[clean_ip] = 'running'

        params = {
            'device_type': (dev.get('device_type') or "").strip(),
            'host': clean_ip,
            'username': (dev.get('username') or "").strip(),
            'password': (dev.get('password') or "").strip(),
            'secret': (dev.get('secret') or "").strip(),
        }

        if run_backup(params, current_timestamp_dir): 
            summary["success"] += 1
            device_status_map[clean_ip] = 'success'  # 👇 備份成功
        else:
            summary["fail"] += 1
            failed_ips.append(clean_ip)
            device_status_map[clean_ip] = 'fail'     # 👇 備份失敗

    current_running_ip = None
    end_time_ts = time.time()
    elapsed_seconds = int(end_time_ts - start_time_ts)
    m, s = divmod(elapsed_seconds, 60)
    h, m = divmod(m, 60)
    elapsed_str = f"{h}時 {m}分 {s}秒" if h > 0 else f"{m}分 {s}秒"
    
    web_log(f"\n================ 任務摘要 ================")
    web_log(f"成功: {summary['success']} | 失敗: {summary['fail']} | 跳過: {summary['skipped']}")
    web_log(f"花費時間: {elapsed_str}")
    if failed_ips:
        web_log(f"[!] 失敗清單: {', '.join(failed_ips)}")
    web_log(f"儲存目錄: {current_timestamp_dir}")
    web_log("==========================================")
    
    backup_is_running = False

# --- Flask 路由 ---
@app.route('/')
def index():
    return render_template('index.html', version=VERSION)

@app.route('/api/backups')
def api_backups():
    """取得所有備份資料夾與檔案清單"""
    backups_dir = os.path.join(BASE_DIR, "network_backups")
    if not os.path.exists(backups_dir):
        return jsonify([])
    
    result = []
    # 取得所有時間戳記資料夾，並反向排序 (最新的在最上面)
    folders = sorted([f for f in os.listdir(backups_dir) if os.path.isdir(os.path.join(backups_dir, f))], reverse=True)
    
    for folder in folders:
        folder_path = os.path.join(backups_dir, folder)
        files = sorted(os.listdir(folder_path))
        result.append({
            "folder": folder,
            "files": files
        })
    return jsonify(result)

@app.route('/api/backup_content')
def api_backup_content():
    """讀取特定備份檔案的內容"""
    folder = request.args.get('folder')
    filename = request.args.get('filename')
    
    # 安全防護：避免目錄穿越漏洞 (Directory Traversal)
    if not folder or not filename or '..' in folder or '..' in filename or '/' in folder or '/' in filename:
        return jsonify({"error": "不合法的路徑或參數錯誤"}), 400
        
    filepath = os.path.join(BASE_DIR, "network_backups", folder, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "找不到該檔案"}), 404
        
    # 如果是二進位檔 (.bin)，阻止讀取以免網頁崩潰顯示亂碼
    if filename.endswith('.bin'):
        return jsonify({"content": "[系統提示]\n\n此為設備匯出的二進位檔案 (.bin)。\n為避免亂碼，無法直接於網頁預覽，請至實體資料夾開啟。"})
        
    try:
        # 讀取純文字設定檔
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": f"讀取失敗: {str(e)}"}), 500

@app.route('/api/devices')
def api_devices():
    devices = get_device_list()
    return jsonify(devices)

@app.route('/api/csv', methods=['GET'])
def get_csv():
    """讀取 devices.csv 原始內容"""
    init_csv_file() # 確保檔案存在
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/csv', methods=['POST'])
def save_csv():
    """儲存 devices.csv 內容"""
    data = request.json
    content = data.get('content', '')
    try:
        with open(CSV_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({"status": "success", "message": "檔案已成功儲存"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"儲存失敗: {str(e)}"})

@app.route('/api/logs')
def api_logs():
    """供前端抓取即時狀態與日誌"""
    return jsonify({
        "is_running": backup_is_running,
        "current_ip": current_running_ip,  # 👈 新增這一行
        "logs": global_logs,
        "device_status": device_status_map  # 👇 新增：傳送每台設備的即時狀態
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    global backup_is_running
    if backup_is_running:
        return jsonify({"status": "error", "message": "目前已有備份任務正在執行中！"})
        
    data = request.json
    target = data.get('target') # 'all' 或是 特定 IP
    
    ip_to_backup = None if target == 'all' else target
    thread = threading.Thread(target=run_backup_task, args=(ip_to_backup,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "message": "備份任務已於背景啟動"})

@app.route('/api/cancel', methods=['POST'])
def api_cancel():
    """發送中斷訊號"""
    global backup_is_running
    if not backup_is_running:
        return jsonify({"status": "error", "message": "目前沒有正在執行的備份任務"})
        
    backup_cancel_event.set() # 觸發中斷旗標
    web_log("\n[⏳] 正在發送中斷訊號，請稍候目前切換設備的空檔...")
    return jsonify({"status": "success", "message": "已發送中斷請求"})

@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    """接收前端傳來的關閉指令，強制結束程式"""
    import os
    os._exit(0)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    #print("啟動 Web UI... 請打開瀏覽器輸入 http://127.0.0.1:5000")
    #app.run(host='0.0.0.0', port=5001, debug=True)
    
    # 建立視窗，並綁定 Flask app
    # 關鍵參數：fullscreen=True (全螢幕)
    webview.create_window(
        title='設備備份系統',       # 視窗標題
        url=app,                  # 直接傳入 Flask app 實例
        fullscreen=True,          # 👈 設定為全螢幕
        #confirm_close=True        # (選用) 關閉時跳出確認視窗，避免誤觸
        maximized=True,           # 啟動時自動最大化
        resizable=False           # 禁止使用者調整視窗大小
    )
    
    # 啟動 pywebview
    webview.start()