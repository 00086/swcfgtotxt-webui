# swcfgtotxt-webui

# 🛡️ 網路設備自動備份系統 WebUI 版 (Network Device Auto-Backup System)

<img width="1917" height="931" alt="001B" src="https://github.com/user-attachments/assets/972f5ea7-331e-4b1c-9fe3-f7d6dfd3710f" />
<img width="1917" height="933" alt="002B" src="https://github.com/user-attachments/assets/07d81103-6fba-4479-98ea-f476ba7ad404" />
<img width="1920" height="1040" alt="003B" src="https://github.com/user-attachments/assets/45e80c1a-e1fe-42b4-a316-e43635af204f" />
<img width="1915" height="931" alt="004B" src="https://github.com/user-attachments/assets/a1e04807-b4a0-409c-ba9a-4d192bf9d87b" />
<img width="1917" height="929" alt="005B" src="https://github.com/user-attachments/assets/fc3f9bd6-5a28-4e00-a7cc-59ec7da429a1" />
<img width="1919" height="933" alt="006B" src="https://github.com/user-attachments/assets/96947204-da8a-4287-ad82-903b464da9fb" />


![Windows](https://img.shields.io/badge/OS-Windows-blue)
![Python](https://img.shields.io/badge/Python-3.8+-yellow)
![License](https://img.shields.io/badge/License-MIT-green)

專為網路運維與系統管理員設計的自動化備份工具。本專案已從原先的 **CLI 文字介面** 全新升級為 **直觀、現代化的 Web 網頁操作介面 (WebUI)**！

整合了 Python Flask 後端、Bootstrap 5 前端技術，以及 `pywebview` 桌面視窗封裝，讓您一鍵即可完成全網設備的組態備份，並能即時監控備份狀態、線上編輯設備清單，以及直接預覽歷史備份檔案。

---

## ✨ 功能特點

* **視覺化網頁面板**：採用 Bootstrap 5 響應式佈局，左側設備清單、右側即時日誌，一目了然。
* **桌面化體驗**：透過 `pywebview` 封裝，將 Web 介面轉換為獨立的桌面應用程式視窗，操作更直覺。
* **即時狀態追蹤與高亮**：
    * 動態顯示每台設備的即時進度（⏳ 等待中、🔄 備份中、✔️ 成功、❌ 失敗、⏭️ 跳過）。
    * 當前正在備份的設備會以**亮藍色呼吸燈效果**強烈高亮，並自動捲動至畫面中央。
* **靈活的備份模式**：支援「⚡ 一鍵全部備份」或針對單一設備進行「單機備份 / 強制備份」。
* **安全中斷與自動恢復**：支援「🛑 中斷備份」功能。中斷或備份結束後，系統會自動透過**狀態機轉移機制**重整介面，將設備清單無縫恢復至初始預設狀態（啟用/跳過），防止畫面閃爍。
* **線上 CSV 編輯器**：內建互動式表格編輯器，可直接增刪改 `devices.csv`。在 IP 開頭加上 `#` 即可快速設定「跳過」該設備。
* **自動初始化配置**：若系統偵測到目錄下缺乏 `devices.csv`，**將會自動建立內含標準標頭與範例資料的全新檔案**，實現免設定點擊即開。
* **歷史備份檔案預覽**：無需登入伺服器後台，直接在網頁上開啟彈窗、即時檢視歷史組態文字內容。
* **核心防呆安全鎖**：
    * 備份執行期間自動禁用編輯、單機備份等衝突按鈕，防止重複觸發。
    * 點擊「結束程式」時若任務仍在執行，系統將跳出強烈警告並攔截。

---

## 🖧 已測試支援品牌 (Supported Devices)

本腳本已針對以下設備型號/作業系統進行測試與優化，並會依據廠牌自動儲存對應的副檔名：

* **D-Link**：支援舊版 Telnet 與新版 SSH，支援 TFTP (`.bin`) 與純文字 (`.cfg`) 備份。內建舊版提示字元異常降級處理。
* **Cisco IOS / IOS-XE**：Router, Switch (`.cfg`)。
* **Fortinet FortiGate**：完整設定檔備份 (`.conf`)。
* **Palo Alto Networks**：設定檔備份 (`.set`)。
* **MikroTik**：匯出備份 (`.rsc`)。

---

## 🛠️ 技術棧

* **後端 (Backend)**：Python 3、Flask、Netmiko (用於 SSH/Telnet 設備連線)、PySMB (若有 NAS 備份需求)
* **視窗封裝 (GUI)**：PyWebview
* **前端 (Frontend)**：HTML5、CSS3 (自訂動畫)、JavaScript (Async/Await 異步輪詢)
* **樣式庫 (UI Framework)**：Bootstrap 5 (透過 CDN 載入)

---

## 📂 專案檔案結構

```text
network-backup-webui/
│
├── app.py                 # Flask 後端與 Pywebview 主程式 (含 API 路由與備份邏輯)
├── devices.csv            # 設備清單設定檔 (若不存在，系統啟動時會自動建立)
│
├── templates/
│   └── index.html         # 全新升級的 WebUI 前端網頁
│
└── backups/               # 備份檔案自動生成目錄
    └── 2026-05-20_17-00/  # 依時間戳記分類的備份資料夾
        ├── 192.168.1.1.cfg
        ├── 192.168.1.2.conf
        └── 192.168.1.3.rsc

```

---

## 🚀 快速開始

### 1. 複製專案

```bash
git clone [https://github.com/your-username/network-backup-webui.git](https://github.com/your-username/network-backup-webui.git)
cd network-backup-webui

```

### 2. 安装必要的 Python 模組

本程式依賴以下第三方套件（包含 Flask、Netmiko、PySMB 與 PyWebview 等），請透過 `pip` 進行安裝。

> 💡 **強烈建議使用 Python 3.12 版本。**

**【標準安裝方式】**
適用於大部分的 Python 環境：

```bash
pip install Flask netmiko pysmb pywebview

```

**【Python 3.14 異常處理安裝方式】**
若您使用的是較新的 Python 3.14 版本，且在安裝 `pywebview` 時遇到異常，請依照下列步驟依序安裝：

```bash
# 1. 更新基礎建置工具
python -m pip install --upgrade pip setuptools wheel

# 2. 安裝 pythonnet 預覽版 (pywebview 在 Windows 上所需)
pip install --pre pythonnet

# 3. 再安裝主要套件
pip install Flask netmiko pysmb pywebview

```

### 3. 啟動應用程式

安裝完成後，執行以下指令：

```bash
python app.py

```

程式啟動時會**自動檢查並初始化環境**，接著透過 `pywebview` 彈出獨立的桌面應用程式視窗，您即可開始操作管理介面。

---

## ⚙️ 設定檔說明 (`devices.csv`)

系統啟動時會自動檢查根目錄下的 `devices.csv`。**若檔案不存在，系統會自動建立一個全新的範本檔案**，內含預設欄位名稱，免去手動建檔的麻煩。

您可以直接透過系統的「📝 編輯清單」按鈕進行視覺化修改，其標準格式如下：

| 欄位名稱 | 說明 | 範例 |
| --- | --- | --- |
| `ip` | 設備的 IP 位址。**開頭加上 `#` 代表暫時略過該設備**。 | `192.168.1.1` 或 `#192.168.1.2` |
| `username` | 用於 SSH/Telnet 登入的帳號。 | `admin` |
| `password` | 用於登入的密碼。 | `password123` |
| `secret` | 進入 Enable 模式（特權模式）所需的密碼（若無則留空）。 | `secret123` |
| `device_type` | Netmiko 支援的設備驅動類型。 | `cisco_ios`, `fortinet`, `mikrotik_routeros` |

> ⚠️ **注意**：CSV 檔案的第一行必須為標準標頭：`ip,username,password,secret,device_type`。系統自建時已包含此標頭。

---

## 📖 核心操作指引

### 🔹 暫時略過特定設備

1. 點擊 **「📝 編輯清單」**。
2. 在不想備份的設備 IP 前方加上 `#`（例如 `#10.0.0.1`）。
3. 儲存後，該設備在主畫面上會呈現不透明度降低的「跳過」狀態。一鍵全部備份時會自動跳過它，但若有緊急需求，仍可對其點擊 **「強制備份」**。

### 🔹 中斷備份與重置

* 在備份執行過程中，若發現異常或欲提前停止，可點擊 **「🛑 中斷備份」**。
* 系統收到中斷訊號後會立即停下，並自動重新載入設備清單，將所有畫面的打勾（成功）、打叉（失敗）徽章清除，**無縫回歸到初始的「啟用 / 跳過」狀態**。

### 🔹 安全關閉程式

* 當您點擊 **「❌ 結束程式」** 時，前端會先向後端確認當前狀態。若系統正忙於備份，將會彈出紅色警告視窗攔截此操作，確保備份檔案不會損毀。
* 如果您直接點擊視窗右上角的 `[X]` 關閉，後台會自動呼叫關閉程序的機制，確保 Flask 伺服器同步停止。

---

## 📄 授權條款 (License)

本專案採用 **MIT 授權條款 (MIT License)**。

您可以自由地複製、修改、散布、再授權以及商業化使用本軟體，唯須在所有軟體副本中包含原創作者的**版權聲明**與**本許可聲明**。

*本軟體按「原樣」提供，不附帶任何形式的明示或暗示保證，包括但不限於對適銷性、特定用途適用性和非侵權性的保證。在任何情況下，作者或版權持有人均不對任何索賠、損害或其他責任負責。*
