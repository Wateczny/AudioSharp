from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock

import os
import yt_dlp
import re
import threading
import logging


default_config = {
    'format': 'best',
    'codec': 'mp3',
    'bitrate': 192,
    'thumbnail': True,
}


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) == 8: # #AARRGGBB
        a = int(hex_color[0:2], 16) / 255.0
        r = int(hex_color[2:4], 16) / 255.0
        g = int(hex_color[4:6], 16) / 255.0
        b = int(hex_color[6:8], 16) / 255.0
        return (r, g, b, a)
    
    elif len(hex_color) == 6: # #RRGGBB
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b, 1.0)
    
    else:
        raise ValueError("Invalid hex color format")


BACKGROUND_COLOR = hex_to_rgb("#303446")
BUTTON_COLOR = hex_to_rgb("#5F6789")
POPUP_COLOR = hex_to_rgb("#414559")
TEXT_COLOR = hex_to_rgb("#c6d0f5")


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        from app import load_config
        self.config = load_config()

        self.url = ""

        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        with layout.canvas.before:
            Color(*BACKGROUND_COLOR)
            self.rect = Rectangle(size=(800, 600), pos=layout.pos)
            layout.bind(size=self._update_rect, pos=self._update_rect)

        app_name_label = Label(text="AudioPipe", font_size=90, color=TEXT_COLOR)
        layout.add_widget(app_name_label)

        self.currently_downloading_label = Label(text="", color=TEXT_COLOR, size_hint_y=None, height=1)
        layout.add_widget(self.currently_downloading_label)

        self.url_input = TextInput(hint_text="", multiline=False, size_hint_y=None, height=40)
        layout.add_widget(self.url_input)

        self.progress_bar = ProgressBar(max=100, size_hint_y=None, height=20)
        layout.add_widget(self.progress_bar)

        download_button = Button(text="Download", size_hint=(1, 0.2), background_color=BUTTON_COLOR)
        download_button.bind(on_press=self.download)
        layout.add_widget(download_button)

        settings_button = Button(text="Settings", size_hint=(1, 0.2), background_color=BUTTON_COLOR)
        settings_button.bind(on_press=self.show_settings)
        layout.add_widget(settings_button)

        self.add_widget(layout)
        logging.info("Main initialized")

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def download(self, instance):
        self.url = self.url_input.text.strip()

        if self.url:
            if self.is_valid(self.url):
                threading.Thread(target=self.youtube_dl, args=(self.url,)).start()
            else:
                self.show_popup("Error", "Invalid URL!")
                logging.error(f"{self.url} is not a valid URL!")
        else:
            self.show_popup("Error", "You didn't enter URL!")

    def youtube_dl(self, url):
        def hook(d):
            match d['status']:
                case 'downloading':
                    percent = d.get('_percent_str', '0%')
                    percent = re.sub(r'\x1b\[[0-9;]*m', '', percent)
                    percent = percent.strip('%')
                    try:
                        Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', float(percent)))
                    except ValueError:
                        Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', 0))
                    if 'filename' in d:
                        filename = d['filename']
                        Clock.schedule_once(lambda dt: setattr(self.currently_downloading_label, 'text', f"Downloading: {filename}"))
                case "finished":
                    if 'filename' in d:
                        filename = d['filename']
                        Clock.schedule_once(lambda dt: setattr(self.currently_downloading_label, 'text', f"Finished: {filename}"))
                    else:
                        Clock.schedule_once(lambda dt: setattr(self.currently_downloading_label, 'text', "Download has finished!"))
                    
                    if 'playlist' in url:
                        if d.get('filename') is None:
                            Clock.schedule_once(lambda dt: self.show_popup("Success", "Playlist has been downloaded!"))
                    else:
                        Clock.schedule_once(lambda dt: self.show_popup("Success", "Audio has been downloaded!"))
                    
                    Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', 100))

                case "error":
                    Clock.schedule_once(lambda dt: self.show_popup("Error", "An error occurred while downloading!"))
                    Clock.schedule_once(lambda dt: setattr(self.currently_downloading_label, 'text', "Error occurred!"))
                    logging.error(f"Error status code: {d['status']}")

        options = {
            'format': str(self.config['format']),
            'outtmpl': os.path.join('./downloads', f"%(title)s.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': str(self.config['codec']),
                'preferredquality': str(self.config['bitrate']),
            }],
            'embedthumbnail': bool(self.config['thumbnail']),
            'quiet': False,
            'progress_hooks': [hook]
        }

        if 'playlist' in url:
            options['noplaylist'] = False
        else:
            options['noplaylist'] = True

        with yt_dlp.YoutubeDL(options) as yt:
            try:
                info_dict = yt.extract_info(url, download=False)
                if 'entries' in info_dict:
                    playlist_name = info_dict.get('title', 'Playlist')
                    Clock.schedule_once(lambda dt: setattr(self.currently_downloading_label, 'text', f"{playlist_name} (Playlist)"))
                else:
                    title = info_dict.get('title', 'Unknown')
                    Clock.schedule_once(lambda dt: setattr(self.currently_downloading_label, 'text', title))
                yt.download([url])
            except Exception as e:
                logging.error(f"Failed to download: {e}")
                Clock.schedule_once(lambda dt: self.show_popup("Error", f"Failed to download: {e}"))

    def is_valid(self, url):
        pattern = (
            r'https?://(?:www\.)?youtube\.com/'
            r'(watch\?v=[a-zA-Z0-9_-]+|playlist\?list=[a-zA-Z0-9_-]+|'
            r'[a-zA-Z0-9_-]+)'
            r'|https?://youtu\.be/[a-zA-Z0-9_-]+'
        )
        return bool(re.match(pattern, url))
    
    def show_settings(self, instance):
        self.manager.current = 'settings'

    def show_popup(self, title, message):
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=message)
        close_button = Button(text="Close", size_hint=(1, 0.2), background_color=POPUP_COLOR)
        popup_layout.add_widget(popup_label)
        popup_layout.add_widget(close_button)

        popup = Popup(title=title, content=popup_layout, size_hint=(0.75, 0.5))
        close_button.bind(on_press=popup.dismiss)
        popup.open()


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        from app import load_config
        BACKGROUND_COLOR = hex_to_rgb("#1e1e2e")
        BUTTON_COLOR = hex_to_rgb("#353551")

        super().__init__(**kwargs)
        self.config = load_config()

        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        with layout.canvas.before:
            Color(*BACKGROUND_COLOR)
            self.rect = Rectangle(size=(800, 600), pos=layout.pos)
            layout.bind(size=self._update_rect, pos=self._update_rect)
        scrollview = ScrollView()

        settings_layout = BoxLayout(orientation='vertical', size_hint_y=None)
        settings_layout.bind(minimum_height=settings_layout.setter('height'))

        self.settings_inputs = {}
        for key, value in self.config.items():
            box = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
            label = Label(text=key, size_hint_x=0.4, color=(1, 1, 1, 1))
            input_field = TextInput(text=str(value), multiline=False, size_hint_x=0.6)
            self.settings_inputs[key] = input_field
            box.add_widget(label)
            box.add_widget(input_field)
            settings_layout.add_widget(box)

        scrollview.add_widget(settings_layout)
        layout.add_widget(scrollview)

        save_button = Button(text="Save", size_hint=(1, 0.2), background_color=BUTTON_COLOR)
        save_button.bind(on_press=self.save_settings)
        layout.add_widget(save_button)
        
        back_button = Button(text="Back", size_hint=(1, 0.2), background_color=BUTTON_COLOR)
        back_button.bind(on_press=self.back_to_main)
        layout.add_widget(back_button)

        self.add_widget(layout)
        logging.info("Settings initialized")

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def save_settings(self, instance):
        from app import save_config
        
        for key, input_field in self.settings_inputs.items():
            value = input_field.text
            if value.isdigit():
                value = int(value)
            elif value.lower() in ['true', 'false']:
                value = value.lower() == 'true'
            self.config[key] = value
        save_config(self.config)
        self.show_popup("Success", "Settings saved successfully.")

    def show_popup(self, title, message):
        POPUP_COLOR = hex_to_rgb("#414559")
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=message)
        close_button = Button(text="Close", size_hint=(1, 0.2), background_color=POPUP_COLOR)
        popup_layout.add_widget(popup_label)
        popup_layout.add_widget(close_button)

        popup = Popup(title=title, content=popup_layout, size_hint=(0.75, 0.5))
        close_button.bind(on_press=popup.dismiss)
        popup.open()

    def back_to_main(self, instance):
        self.manager.current = 'main'


def load_config():
    import os, toml
    config = {}

    if os.path.exists('config.toml'):
        try:
            with open('config.toml', 'r') as f:
                config = toml.load(f)
        except Exception as e:
            print(f"Error reading config.toml: {e}")
            print("Loading default settings.")
            config = default_config
    else:
        print("config.toml not found, creating a new one with default config.")
        with open('config.toml', 'w') as f:
            toml.dump(default_config, f)
        config = default_config
    return config

def save_config(config):
    import toml
    with open('config.toml', 'w') as f:
        toml.dump(config, f)

class AudioPipe(App):
    def __init__(self, **kwargs):
        import os
        if not os.path.exists('./downloads'):
            os.makedirs('./downloads')
        
        self.main_screen = MainScreen(name='main')
        self.settings_screen = SettingsScreen(name='settings')
        super().__init__(**kwargs)

    def build(self):
        sm = ScreenManager()
        
        sm.add_widget(self.main_screen)
        sm.add_widget(self.settings_screen)

        return sm

if __name__ == '__main__':
    AudioPipe().run()
