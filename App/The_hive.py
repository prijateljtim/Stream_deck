import customtkinter as ctk
from customtkinter import filedialog
import serial
import serial.tools.list_ports
import threading
import time
import pyautogui
import os
import sys
import json 
import ctypes
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from PIL import Image
import pystray
from pystray import MenuItem as item

# To get to the application from arrow up near clock
app = None
tray_ikona = None

#Neki za exe 
def dobi_pot(datoteka, za_pisanje=False):
    if hasattr(sys, '_MEIPASS') and not za_pisanje:
        return os.path.join(sys._MEIPASS, datoteka)
    if hasattr(sys, 'frozen'):
        mapa_programa = os.path.dirname(sys.executable)
    else:
        mapa_programa = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(mapa_programa, datoteka)


try:
    moj_appid = 'thehive.v1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(moj_appid)
except Exception as e:
    print(f"Tole ti ni ratal: {e}")

#For audio control
def get_volume_control():
    try:
        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, 'Activate'):
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        else:
            raise AttributeError("Device missing Activate method.")
    except Exception as e:
        print(f"Standard audio init failed, trying fallback... ({e})")
        try:
            from comtypes.client import CreateObject
            from pycaw.pycaw import IMMDeviceEnumerator, EDataFlow, ERole
            device_enumerator = CreateObject("{BCDE0395-E52F-467C-8E3D-C4579291692E}", interface=IMMDeviceEnumerator)
            device = device_enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as fallback_e:
            print(f"Audio totally failed: {fallback_e}")
            return None

volume_control = get_volume_control()

def change_volume(direction):
    if volume_control is None: return "--"
    if direction == "BTN_EN":
        is_muted = volume_control.GetMute()
        volume_control.SetMute(1 - is_muted, None)
        return "Muted" if not is_muted else "Unmuted"
    current_vol = volume_control.GetMasterVolumeLevelScalar()
    if direction == "UP": new_vol = min(1.0, current_vol + 0.02)
    else: new_vol = max(0.0, current_vol - 0.02)
    volume_control.SetMasterVolumeLevelScalar(new_vol, None)
    return int(new_vol * 100)

# Scaning apps in computer
def get_start_menu_apps():
    apps = {}
    paths = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop")
    ]
    for path in paths:
        if not os.path.exists(path): continue
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(".lnk") or file.lower().endswith(".url"): 
                    name = file.rsplit(".", 1)[0] 
                    if name not in apps: apps[name] = os.path.join(root, file)
    return apps

# UI app
ctk.set_appearance_mode("dark") 

class TheHiveAPP(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hive Center")
        self.geometry("1000x600") 
        self.configure(fg_color="#000000") 
        self.minsize(1000, 600)
        
        try:
            self.iconbitmap(dobi_pot("logo.ico"))
        except Exception as e:
            print(f"Ikone .ico ni mogoče naložiti: {e}")
        
        # That app goes to tray when you click X
        self.protocol('WM_DELETE_WINDOW', self.skrij_v_tray)

        self.active_connections = {} 
        self.running = True 
        self.accent_color = "#FFB300" 
        self.bg_secondary = "#0D0D0D" 
        self.border_color = "#1F1F1F" 
        
        self.settings_file = dobi_pot("hive_settings.json", za_pisanje=True)
        self.installed_apps, self.app_names, self.macros = {}, [], {}
        self.dragging_app, self.drag_window, self.listening_for = None, None, None

        # Top menu bar,  maybe will someday be more here
        self.menu_bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.menu_bar.pack(fill="x", padx=20, pady=(15, 0)) 
        
        self.nav_btn_hub = ctk.CTkButton(self.menu_bar, text="Device Center", font=("Segoe UI", 16, "bold"), fg_color=self.bg_secondary, border_color=self.accent_color, border_width=1, hover_color="#1A1A1A", text_color="#ffffff", width=140, height=35, command=self.show_main_menu)
        self.nav_setting = ctk.CTkButton(self.menu_bar, text="Settings", font=("Segoe UI", 16, "bold"), fg_color="transparent", hover_color="#1A1A1A", text_color="#666666", width=120, height=35, command=self.show_settings_menu)
        self.btn_scan = ctk.CTkButton(self.menu_bar, text="⟳ Scan", font=("Segoe UI", 15, "bold"), fg_color=self.accent_color, text_color="#000000", hover_color="#E5A100", width=100, height=35, command=self.start_scan)
        
        self.nav_btn_hub.pack(side="left", padx=10)
        self.nav_setting.pack(side="right", padx=10)
        self.btn_scan.pack(side="right", padx=(10, 5)) 

        self.separator = ctk.CTkFrame(self, fg_color=self.border_color, height=1)
        self.separator.pack(fill="x", padx=30, pady=(15, 0))

        # Top menu bar when are you in stream deck menu, with bvack button
        self.back_bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.btn_back = ctk.CTkButton(self.back_bar, text="⮜ Back", font=("Segoe UI", 14, "bold"), fg_color="transparent", border_color=self.border_color, border_width=1, hover_color="#1A1A1A", text_color="#ffffff", width=80, command=self.show_main_menu)
        self.state_label = ctk.CTkLabel(self.back_bar, text="PAGE", text_color=self.accent_color, font=("Segoe UI", 28, "bold"))
        self.btn_back.pack(side="left", padx=5)
        self.state_label.pack(side="left", padx=20)


        # Window for main, the first thing you see when you open app
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=30, pady=20)

        self.main_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.devices_grid_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.devices_grid_frame.pack(pady=30) 
        self.device_buttons = [] 

        self.custom_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.macro_area = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        self.macro_area.pack(side="left", fill="both", expand=True)
        self.macro_grid = ctk.CTkFrame(self.macro_area, fg_color="transparent")
        self.macro_grid.pack(expand=True) 
        
        self.ui_macro_buttons = {}
        for i in range(1, 7):
            gk = f"GPIO{i}"
            btn = ctk.CTkButton(self.macro_grid, text=f"BUTTON {i}\n--", command=lambda k=gk: self.start_listening(k), height=110, width=170, corner_radius=15, fg_color=self.bg_secondary, border_color=self.border_color, border_width=1, hover_color="#1A1A1A", font=("Segoe UI", 13, "bold"), text_color="#BBBBBB")
            btn.grid(row=(i-1)//3, column=(i-1)%3, padx=10, pady=10)
            self.ui_macro_buttons[gk] = btn

        self.app_sidebar = ctk.CTkFrame(self.custom_frame, fg_color="transparent", width=350)
        self.app_sidebar.pack(side="right", fill="y", padx=(20, 0))
        lbl_sidebar = ctk.CTkLabel(self.app_sidebar, text="DRAG APP TO BUTTON", font=("Segoe UI", 14, "bold"), text_color=self.accent_color)
        lbl_sidebar.pack(pady=(0, 5))
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self.filter_apps)
        self.search_entry = ctk.CTkEntry(self.app_sidebar, textvariable=self.search_var, placeholder_text="Search apps...", fg_color=self.bg_secondary, border_color=self.border_color)
        self.search_entry.pack(fill="x", pady=(0, 5))
        
        self.btn_add_app = ctk.CTkButton(self.app_sidebar, text="+ Add app/game", font=("Segoe UI", 12, "bold"), fg_color="transparent", border_color=self.border_color, border_width=1, hover_color="#1A1A1A", text_color="#AAAAAA", command=self.add_custom_app)
        self.btn_add_app.pack(fill="x", pady=(0, 10))

        self.app_scroll = ctk.CTkScrollableFrame(self.app_sidebar, fg_color=self.bg_secondary, border_color=self.border_color, border_width=1, width=350)
        self.app_scroll.pack(fill="both", expand=True)

        self.settings_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.settings_info = ctk.CTkLabel(self.settings_frame, text="THE HIVE", font=("Segoe UI", 32, "bold"), text_color=self.accent_color)
        self.settings_info.pack(pady=(40, 10))
        ctk.CTkLabel(self.settings_frame, text="Hive control center", font=("Segoe UI", 14), text_color="#666666").pack()
        self.ver_label = ctk.CTkLabel(self.settings_frame, text="v2026.01 Alpha", font=("Consolas", 12), text_color="#444444")
        self.ver_label.pack(side="bottom", pady=20)

        self.main_frame.pack(fill="both", expand=True)
        self.after(500, self.start_scan)

    def skrij_v_tray(self):
        self.withdraw()

    def load_settings(self):
        default_macros = {"GPIO1": ['ctrl', 'c'], "GPIO2": ['ctrl', 'v'], "GPIO3": ['win', 'd'], "GPIO4": ['space'], "GPIO5": ['alt', 'f4'], "GPIO6": ['enter']}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f: return json.load(f)
            except: return default_macros
        return default_macros

    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f: json.dump(self.macros, f, indent=4)
        except Exception as e: print(f"Failed to save settings: {e}")

    def get_display_text(self, gk):
        action = self.macros.get(gk, [])
        if isinstance(action, list): return '+'.join(action).upper()
        else:
            raw_name = os.path.basename(action).replace(".lnk", "").replace(".url", "")
            return raw_name.upper()[:12] + ".." if len(raw_name) > 12 else raw_name.upper()

    def osvezi_macro_gumbe(self):
        for i in range(1, 7):
            gk = f"GPIO{i}"
            if gk in self.ui_macro_buttons: self.ui_macro_buttons[gk].configure(text=f"BUTTON {i}\n{self.get_display_text(gk)}")

    def add_custom_app(self):
        file_path = filedialog.askopenfilename(title="Select Game or App Executable", filetypes=[("Executables & Shortcuts", "*.exe *.url *.lnk *.bat"), ("All Files", "*.*")])
        if file_path:
            clean_name = os.path.basename(file_path).rsplit(".", 1)[0]
            self.installed_apps[clean_name] = file_path
            if clean_name not in self.app_names:
                self.app_names.append(clean_name)
                self.app_names.sort()
            self.search_var.set(""); self.populate_apps()

    def populate_apps(self, search_text=""):
        for widget in self.app_scroll.winfo_children(): widget.destroy()
        search_text = search_text.lower()
        for app_name in self.app_names:
            if search_text in app_name.lower():
                lbl = ctk.CTkLabel(self.app_scroll, text=f"  {app_name}", anchor="w", font=("Segoe UI", 12), cursor="hand2", text_color="#FFFFFF", fg_color="#1A1A1A", corner_radius=5)
                lbl.pack(fill="x", pady=2, padx=2, ipady=4)
                lbl.bind("<ButtonPress-1>", lambda e, a=app_name: self.on_drag_start(e, a))
                lbl.bind("<B1-Motion>", self.on_drag_motion)
                lbl.bind("<ButtonRelease-1>", self.on_drag_stop)
                if hasattr(lbl, "_label"):
                    lbl._label.bind("<ButtonPress-1>", lambda e, a=app_name: self.on_drag_start(e, a))
                    lbl._label.bind("<B1-Motion>", self.on_drag_motion)
                    lbl._label.bind("<ButtonRelease-1>", self.on_drag_stop)

    def filter_apps(self, *args): self.populate_apps(self.search_var.get())

    def on_drag_start(self, event, app_name):
        self.dragging_app = app_name
        if self.drag_window is not None: self.drag_window.destroy()
        self.drag_window = ctk.CTkToplevel(self)
        self.drag_window.overrideredirect(True); self.drag_window.attributes("-topmost", True); self.drag_window.attributes("-alpha", 0.85) 
        lbl = ctk.CTkLabel(self.drag_window, text=f"  {app_name} ", font=("Segoe UI", 13, "bold"), fg_color=self.accent_color, text_color="#000000", corner_radius=5)
        lbl.pack(ipadx=10, ipady=5)
        self.drag_window.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")

    def on_drag_motion(self, event):
        if self.drag_window is not None: self.drag_window.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")

    def on_drag_stop(self, event):
        if self.drag_window is not None: self.drag_window.destroy(); self.drag_window = None
        if not self.dragging_app: return
        x, y = event.x_root, event.y_root
        for gk, btn in self.ui_macro_buttons.items():
            bx, by = btn.winfo_rootx(), btn.winfo_rooty()
            bw, bh = btn.winfo_width(), btn.winfo_height()
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.macros[gk] = self.installed_apps[self.dragging_app]
                self.save_settings()
                btn.configure(text=f"BUTTON {gk[4:]}\n{self.get_display_text(gk)}")
                break 
        self.dragging_app = None

    def show_custom_menu(self):
        self.menu_bar.pack_forget(); self.separator.pack_forget()
        self.back_bar.pack(fill="x", padx=30, pady=(20, 0), before=self.container)
        self.state_label.configure(text="STREAM DECK")
        self.main_frame.pack_forget(); self.settings_frame.pack_forget(); self.custom_frame.pack(fill="both", expand=True) 

    def show_main_menu(self):
        self.back_bar.pack_forget()
        self.menu_bar.pack(fill="x", padx=20, pady=(15, 0), before=self.container)
        self.separator.pack(fill="x", padx=30, pady=(15, 0), before=self.container)
        self.custom_frame.pack_forget(); self.settings_frame.pack_forget(); self.main_frame.pack(fill="both", expand=True) 

    def show_settings_menu(self):
        self.menu_bar.pack_forget(); self.separator.pack_forget()
        self.back_bar.pack(fill="x", padx=30, pady=(20, 0), before=self.container)
        self.state_label.configure(text="SETTINGS")
        self.main_frame.pack_forget(); self.custom_frame.pack_forget(); self.settings_frame.pack(fill="both", expand=True) 

    def add_device_button(self, name, command):
        final_name = name
        while any(btn.cget("text") == final_name for btn in self.device_buttons): final_name += " "
        btn = ctk.CTkButton(self.devices_grid_frame, text=final_name, command=command, fg_color=self.bg_secondary, border_color=self.accent_color, border_width=1, hover_color="#1A1A1A", width=180, height=140, corner_radius=20, font=("Segoe UI", 18, "bold"))
        btn.grid(row=len(self.device_buttons)//3, column=len(self.device_buttons)%3, padx=20, pady=20)
        self.device_buttons.append(btn)

    def clear_devices(self):
        for btn in self.device_buttons: btn.destroy()
        self.device_buttons.clear()

    def start_listening(self, gk):
        self.listening_for = gk
        for k, btn in self.ui_macro_buttons.items():
            if k == gk: btn.configure(text="RECORDING...", fg_color="#332200", border_color=self.accent_color)
            else: btn.configure(state="disabled")
        self.focus_set(); self.bind("<KeyPress>", self.record_key) 

    def record_key(self, event):
        if not self.listening_for: return
        mod = []
        if event.state & 0x0004: mod.append("ctrl")
        if event.state & 0x0001: mod.append("shift")
        if event.state & 0x20000: mod.append("alt")
        key = event.keysym.lower()
        if "control" in key or "shift" in key or "alt" in key: return 
        if key == "return": key = "enter"
        self.macros[self.listening_for] = mod + [key]
        self.save_settings()
        for k, btn in self.ui_macro_buttons.items():
            btn.configure(state="normal", fg_color=self.bg_secondary, border_color=self.border_color, text=f"BUTTON {k[4:]}\n{self.get_display_text(k)}")
        self.listening_for = None; self.unbind("<KeyPress>")

    def start_scan(self):
        self.btn_scan.configure(state="disabled", text="Scanning...")
        threading.Thread(target=self.scan_ports, daemon=True).start()

    def scan_ports(self):
        ports = list(serial.tools.list_ports.comports())
        for p in sorted(ports, key=lambda x: x.device, reverse=True):
            if p.device in self.active_connections: continue
            try:
                s = serial.Serial(p.device, 115200, timeout=1)
                time.sleep(1.5)
                s.reset_input_buffer(); s.write(bytes([0xAA]))
                odgovor = s.read(2)
                if len(odgovor) == 2 and odgovor[0] == 0xAB and odgovor[1] == 0xAC:
                    disp_name = "StreamDeck"
                    self.active_connections[p.device] = {"serial": s, "name": disp_name}
                    self.installed_apps = get_start_menu_apps()
                    self.app_names = sorted(list(self.installed_apps.keys()))
                    self.macros = self.load_settings()
                    self.after(0, self.osvezi_macro_gumbe)
                    self.after(0, self.populate_apps)
                    self.after(0, lambda n=disp_name: self.add_device_button(n, self.show_custom_menu))
                    threading.Thread(target=self.read_serial, args=(s, p.device), daemon=True).start()
                else:
                    s.write(bytes([0x00])); s.close()
            except: continue
        self.after(0, lambda: self.btn_scan.configure(state="normal", text="⟳ Scan"))

    def read_serial(self, ser_conn, port_name):
        while self.running and port_name in self.active_connections:
            try:
                if ser_conn.in_waiting > 0:
                    raw_byte = ser_conn.read(1)
                    if not raw_byte: continue
                    ukaz = ord(raw_byte)
                    if ukaz == 0x11: self.after(0, lambda: change_volume("UP"))
                    elif ukaz == 0x12: self.after(0, lambda: change_volume("DOWN"))
                    elif ukaz == 0x07: self.after(0, lambda: change_volume("BTN_EN"))    
                    else:
                        gpio_kljuc = f"GPIO{ukaz}"
                        if gpio_kljuc in self.macros: 
                            action = self.macros[gpio_kljuc]
                            if isinstance(action, list): pyautogui.hotkey(*action) 
                            elif isinstance(action, str):
                                try: os.startfile(action)  
                                except: pass
            except:
                if port_name in self.active_connections: del self.active_connections[port_name]
                if ser_conn: ser_conn.close()
                self.after(0, self.handle_disconnect); break 
            time.sleep(0.001)

    def handle_disconnect(self):
        self.clear_devices()
        for port, data in self.active_connections.items(): self.add_device_button(data["name"], self.show_custom_menu)
        if len(self.active_connections) == 0:
            self.installed_apps, self.app_names, self.macros = {}, [], {}
            self.populate_apps(); self.show_main_menu()


#For tray main proces
def prikazi_okno(icon, item):
    global app
    app.after(0, app.deiconify)

def popoln_izhod(icon, item):
    global app, tray_ikona
    tray_ikona.stop()
    if app:
        app.running = False
        for port, data in app.active_connections.items():
            try: data["serial"].close()
            except: pass
        app.after(0, app.destroy)

def zazeni_tk_v_ozadju():
    global app
    app = TheHiveAPP()
    app.mainloop()

if __name__ == "__main__":
    threading.Thread(target=zazeni_tk_v_ozadju, daemon=True).start()
    
    try:
        slika_ico = Image.open(dobi_pot("logo.ico"))
        meni = pystray.Menu(
            item('Odpri', prikazi_okno, default=True),
            item('Izhod', popoln_izhod)
        )
        tray_ikona = pystray.Icon("TheHive", slika_ico, "Hive Center", meni)
        
        tray_ikona.run()
    except Exception as e:
        print(f"Tray ikona se ni mogla zagnati: {e}")