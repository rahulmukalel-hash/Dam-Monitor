main_code = '''import kivy
kivy.require('2.0.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle

import socket
import threading
import time
from datetime import datetime

class DamMonitorApp(App):
    def build(self):
        self.title = "Dam Water Level Monitor"
        self.client_socket = None
        self.running = False
        
        # ഹിസ്റ്ററി സ്റ്റോറേജ്
        self.level_history = []
        self.alarm_history = []

        root = BoxLayout(orientation='vertical', padding=12, spacing=10)
        
        # പശ്ചാത്തല നിറം (Dark Slate Theme)
        with root.canvas.before:
            Color(0.08, 0.11, 0.16, 1)
            self.bg_rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._update_rect, pos=self._update_rect)

        # 1. Header (Title, Connection Status & Last Updated Time)
        header_box = BoxLayout(size_hint_y=0.12, orientation='vertical', spacing=2)
        title_lbl = Label(text="DAM LEVEL MONITOR", font_size='20sp', bold=True, color=(1, 1, 1, 1))
        
        status_time_box = BoxLayout(size_hint_y=None, height=22)
        self.status_lbl = Label(text="STATUS: DISCONNECTED", font_size='12sp', bold=True, color=(0.9, 0.3, 0.3, 1), halign='left')
        self.last_update_lbl = Label(text="Last Updated: --:--:--", font_size='12sp', color=(0.7, 0.8, 0.9, 1), halign='right')
        
        self.status_lbl.bind(size=self.status_lbl.setter('text_size'))
        self.last_update_lbl.bind(size=self.last_update_lbl.setter('text_size'))
        
        status_time_box.add_widget(self.status_lbl)
        status_time_box.add_widget(self.last_update_lbl)

        header_box.add_widget(title_lbl)
        header_box.add_widget(status_time_box)
        root.add_widget(header_box)

        # 2. Main Center Display (Water Level & Visual Bar)
        center_box = BoxLayout(orientation='vertical', size_hint_y=0.46, spacing=8, padding=10)
        with center_box.canvas.before:
            Color(0.13, 0.17, 0.23, 1)
            self.c_rect = RoundedRectangle(size=center_box.size, pos=center_box.pos, radius=[12])
        center_box.bind(size=self._update_center_rect, pos=self._update_center_rect)

        self.level_val_lbl = Label(text="0.00 m", font_size='48sp', bold=True, color=(0.3, 0.8, 1, 1))
        
        # Water Gauge Bar (685.0m to 695.0m range)
        self.gauge = ProgressBar(max=100, value=0, size_hint_y=None, height=22)
        
        range_box = BoxLayout(size_hint_y=None, height=20)
        range_min = Label(text="Min: 685.15 m", font_size='11sp', color=(0.7, 0.7, 0.7, 1), halign='left')
        range_max = Label(text="Max: 694.00 m", font_size='11sp', color=(0.7, 0.7, 0.7, 1), halign='right')
        range_min.bind(size=range_min.setter('text_size'))
        range_max.bind(size=range_max.setter('text_size'))
        range_box.add_widget(range_min)
        range_box.add_widget(range_max)

        self.alarm_banner = Label(text="NORMAL", font_size='15sp', bold=True, color=(0.3, 0.9, 0.4, 1))

        center_box.add_widget(self.level_val_lbl)
        center_box.add_widget(self.gauge)
        center_box.add_widget(range_box)
        center_box.add_widget(self.alarm_banner)
        root.add_widget(center_box)

        # 3. Connection Settings (IP & Port Inputs)
        conn_box = GridLayout(cols=2, size_hint_y=0.18, spacing=8, padding=[5, 5, 5, 5])
        
        conn_box.add_widget(Label(text="Server IP:", size_hint_x=0.3, color=(0.9, 0.9, 0.9, 1)))
        self.ip_input = TextInput(text="192.168.1.100", multiline=False, size_hint_x=0.7)
        
        conn_box.add_widget(Label(text="Port:", size_hint_x=0.3, color=(0.9, 0.9, 0.9, 1)))
        self.port_input = TextInput(text="8080", multiline=False, size_hint_x=0.7)
        root.add_widget(conn_box)

        # Connect / Disconnect Button
        self.conn_btn = Button(text="CONNECT", size_hint_y=0.11, background_color=(0.15, 0.65, 0.35, 1), bold=True, font_size='16sp')
        self.conn_btn.bind(on_release=self.toggle_connection)
        root.add_widget(self.conn_btn)

        # 4. History Logs Buttons (Alarm History & Level History)
        hist_box = BoxLayout(size_hint_y=0.13, spacing=10)
        
        btn_alarm_hist = Button(text="ALARM LOG", background_color=(0.75, 0.3, 0.2, 1), bold=True)
        btn_alarm_hist.bind(on_release=self.show_alarm_history)
        
        btn_level_hist = Button(text="LEVEL LOG", background_color=(0.2, 0.5, 0.75, 1), bold=True)
        btn_level_hist.bind(on_release=self.show_level_history)

        hist_box.add_widget(btn_alarm_hist)
        hist_box.add_widget(btn_level_hist)
        root.add_widget(hist_box)

        return root

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _update_center_rect(self, instance, value):
        self.c_rect.pos = instance.pos
        self.c_rect.size = instance.size

    def toggle_connection(self, instance):
        if not self.running:
            self.start_client()
        else:
            self.stop_client()

    def start_client(self):
        self.running = True
        self.conn_btn.text = "DISCONNECT"
        self.conn_btn.background_color = (0.8, 0.2, 0.2, 1)
        self.status_lbl.text = "STATUS: CONNECTING..."
        self.status_lbl.color = (1, 0.8, 0.2, 1)
        threading.Thread(target=self.client_worker, daemon=True).start()

    def stop_client(self):
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.conn_btn.text = "CONNECT"
        self.conn_btn.background_color = (0.15, 0.65, 0.35, 1)
        self.status_lbl.text = "STATUS: DISCONNECTED"
        self.status_lbl.color = (0.9, 0.3, 0.3, 1)

    def client_worker(self):
        ip = self.ip_input.text.strip()
        try:
            port = int(self.port_input.text.strip())
        except:
            port = 8080

        while self.running:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5.0)
                self.client_socket.connect((ip, port))
                Clock.schedule_once(lambda dt: self.set_status("STATUS: CONNECTED", (0.2, 0.9, 0.4, 1)))

                while self.running:
                    data = self.client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                    val_str = data.strip().replace('\\n', '').replace('\\r', '')
                    Clock.schedule_once(lambda dt, v=val_str: self.update_display(v))
            except Exception:
                Clock.schedule_once(lambda dt: self.set_status("STATUS: RETRYING...", (1, 0.6, 0.1, 1)))
                time.sleep(3)

    def set_status(self, text, color):
        self.status_lbl.text = text
        self.status_lbl.color = color

    def update_display(self, val_str):
        try:
            val = float(val_str)
            self.level_val_lbl.text = f"{val:.2f} m"
            
            # Progress bar calculation (685.0 to 695.0)
            pct = max(0, min(100, ((val - 685.0) / 10.0) * 100))
            self.gauge.value = pct

            # Current Timestamp Update
            current_time = datetime.now().strftime("%H:%M:%S")
            self.last_update_lbl.text = f"Last Updated: {current_time}"

            self.level_history.append(f"[{current_time}] {val:.2f} m")
            if len(self.level_history) > 100:
                self.level_history.pop(0)

            # High/Low Level Alert Checks
            if val >= 693.50:
                self.alarm_banner.text = "ALARM: HIGH WATER LEVEL!"
                self.alarm_banner.color = (1, 0.2, 0.2, 1)
                self.alarm_history.append(f"[{current_time}] HIGH LEVEL ALARM: {val:.2f} m")
            elif val <= 685.50:
                self.alarm_banner.text = "ALARM: LOW WATER LEVEL!"
                self.alarm_banner.color = (1, 0.5, 0.1, 1)
                self.alarm_history.append(f"[{current_time}] LOW LEVEL ALARM: {val:.2f} m")
            else:
                self.alarm_banner.text = "STATUS: NORMAL"
                self.alarm_banner.color = (0.3, 0.9, 0.4, 1)

        except ValueError:
            pass

    def show_alarm_history(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        txt = "\\n".join(self.alarm_history[-20:]) if self.alarm_history else "No alarms recorded."
        lbl = Label(text=txt, size_hint_y=None, color=(1, 0.4, 0.4, 1))
        lbl.bind(texture_size=lbl.setter('size'))
        scroll.add_widget(lbl)
        content.add_widget(scroll)

        close_btn = Button(text="CLOSE", size_hint_y=None, height=45)
        popup = Popup(title="Alarm History Log", content=content, size_hint=(0.85, 0.7))
        close_btn.bind(on_release=popup.dismiss)
        content.add_widget(close_btn)
        popup.open()

    def show_level_history(self, instance):
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        txt = "\\n".join(self.level_history[-25:]) if self.level_history else "No data received yet."
        lbl = Label(text=txt, size_hint_y=None, color=(0.8, 0.9, 1, 1))
        lbl.bind(texture_size=lbl.setter('size'))
        scroll.add_widget(lbl)
        content.add_widget(scroll)

        close_btn = Button(text="CLOSE", size_hint_y=None, height=45)
        popup = Popup(title="Water Level History Log", content=content, size_hint=(0.85, 0.7))
        close_btn.bind(on_release=popup.dismiss)
        content.add_widget(close_btn)
        popup.open()

if __name__ == '__main__':
    DamMonitorApp().run()
'''

with open('main.py', 'w') as f:
    f.write(main_code)

print(">>> [SUCCESS] Updated main.py created with Last Updated Time display!")
