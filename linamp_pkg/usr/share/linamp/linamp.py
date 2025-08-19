#!/usr/bin/env python3

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist, QAudioProbe, QAudioFormat, QAudioBuffer
from PyQt5.QtMultimediaWidgets import QVideoWidget
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QHBoxLayout,
    QVBoxLayout, QSizePolicy, QSlider, QListWidget, QLayout, QDialog, QPushButton, QAbstractItemView, QListWidgetItem
)
from PyQt5.QtCore import Qt, QPoint, QRect, QEvent, QSize, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer, QUrl, QStandardPaths
from PyQt5.QtGui import QPixmap, QMouseEvent, QMovie, QCursor, QFont, QColor, QPainter, QImage, QIcon
import random
import struct
import json
import os

# Mutagen kütüphanesi için gerekli import'lar
# Bu kütüphane şarkının varsa tag bilgilerini okuyup arayüze resim bastırır
from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError, APIC
from io import BytesIO

# --- Sabitler (Resimlerin bulunduğu klasör) ---
# Program kurulduktan sonraki varsayılan dizin
INSTALLED_IMAGE_FOLDER = "/usr/share/linamp/buttons/"
INSTALLED_ICON_PATH = "/usr/share/linamp/linamp.png" # Yeni sabit

# Eğer kurulmuş dizin varsa onu kullan, yoksa script'in çalıştığı dizindeki 'buttons' klasörünü kullan.
if os.path.exists(INSTALLED_IMAGE_FOLDER):
    IMAGE_FOLDER = INSTALLED_IMAGE_FOLDER
else:
    IMAGE_FOLDER = "buttons/"

# Yeni ikon yolu belirleme mantığı
if os.path.exists(INSTALLED_ICON_PATH):
    ICON_PATH = INSTALLED_ICON_PATH
else:
    ICON_PATH = os.path.join(os.path.dirname(__file__), "linamp.png")

# Veritabanı dosya yolu için sabitler, doğrudan ana dizinde oluşturulacak şekilde değiştirildi
HOME_DIR = os.path.expanduser("~")
APP_DATA_DIR = os.path.join(HOME_DIR, ".LinAMP")
DB_FILE_PATH = os.path.join(APP_DATA_DIR, "temp.json")

# --- Özel Buton Sınıfı (Normal resimli) ---
class ImageButton(QLabel):
    action_triggered = pyqtSignal()

    def __init__(self, normal_img, cursor_img=None, pressed_img=None, active_img=None, parent=None, is_toggle=False, is_externally_persistent_controlled=False):
        super().__init__(parent)
        
        self.normal_pixmap = QPixmap(IMAGE_FOLDER + normal_img)
        self.cursor_pixmap = QPixmap(IMAGE_FOLDER + cursor_img) if cursor_img else self.normal_pixmap
        self.pressed_pixmap = QPixmap(IMAGE_FOLDER + pressed_img) if pressed_img else self.normal_pixmap
        self.active_pixmap = QPixmap(IMAGE_FOLDER + active_img) if active_img else self.normal_pixmap
        
        self.is_toggle = is_toggle
        self._is_active = False
        self._is_persistent_pressed = False
        self.is_externally_persistent_controlled = is_externally_persistent_controlled

        self.setPixmap(self.normal_pixmap)
        self.setFixedSize(self.normal_pixmap.size())
        self.setScaledContents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("border: none;")

        self.installEventFilter(self)

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        if self._is_active != value:
            self._is_active = value
            self._update_pixmap()

    def set_persistent_pressed(self, pressed: bool):
        if self._is_persistent_pressed != pressed:
            self._is_persistent_pressed = pressed
            self._update_pixmap()

    def _update_pixmap(self):
        if self._is_persistent_pressed:
            self.setPixmap(self.pressed_pixmap)
        elif self.is_toggle and self._is_active:
            self.setPixmap(self.active_pixmap)
        elif self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.setPixmap(self.cursor_pixmap)
        else:
            self.setPixmap(self.normal_pixmap)

    def eventFilter(self, obj, event):
        if obj == self:
            if self._is_persistent_pressed and not self.is_toggle:
                if event.type() == QEvent.Enter or event.type() == QEvent.Leave:
                    return True
                return False
            
            if event.type() == QEvent.Enter:
                if not (self.is_toggle and self.is_active):
                    self.setPixmap(self.cursor_pixmap)
                return True
            elif event.type() == QEvent.Leave:
                self._update_pixmap()
                return True
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.setPixmap(self.pressed_pixmap)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    if self.is_toggle:
                        self.is_active = not self.is_active
                        self._update_pixmap()
                    elif self.is_externally_persistent_controlled:
                        pass 
                    else:
                        self._update_pixmap()
                    
                    self.action_triggered.emit()
                    return True
        return super().eventFilter(obj, event)

# --- Özel Animasyonlu Buton Sınıfı (GIF için) ---
class AnimatedButton(QLabel):
    action_triggered = pyqtSignal()

    def __init__(self, normal_img, cursor_img=None, pressed_img=None, gif_animation=None, parent=None):
        super().__init__(parent)
        
        self.normal_pixmap = QPixmap(IMAGE_FOLDER + normal_img)
        self.cursor_pixmap = QPixmap(IMAGE_FOLDER + cursor_img) if cursor_img else self.normal_pixmap
        self.pressed_pixmap = QPixmap(IMAGE_FOLDER + pressed_img) if pressed_img else self.normal_pixmap
        
        self.gif_movie = QMovie(IMAGE_FOLDER + gif_animation) if gif_animation else None
        
        self.setPixmap(self.normal_pixmap)
        self.setFixedSize(self.normal_pixmap.size())
        self.setScaledContents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("border: none;")
        
        if self.gif_movie:
            self.gif_movie.setScaledSize(self.normal_pixmap.size())
            self.gif_movie.setCacheMode(QMovie.CacheAll)
            self.gif_movie.frameChanged.connect(self.update)

        self.is_playing_gif = False
        self.installEventFilter(self)

    def start_animation(self):
        if self.gif_movie and not self.is_playing_gif:
            self.setMovie(self.gif_movie)
            self.gif_movie.start()
            self.is_playing_gif = True

    def stop_animation(self):
        if self.gif_movie and self.is_playing_gif:
            self.gif_movie.stop()
            self.setMovie(None) 
            self.is_playing_gif = False
            self._update_static_pixmap()

    def _update_static_pixmap(self):
        if self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.setPixmap(self.cursor_pixmap)
        else:
            self.setPixmap(self.normal_pixmap)

    def eventFilter(self, obj, event):
        if obj == self:
            if self.is_playing_gif:
                if event.type() == QEvent.Enter or event.type() == QEvent.Leave:
                    return True 
                
            if event.type() == QEvent.Enter:
                if not self.is_playing_gif:
                    self.setPixmap(self.cursor_pixmap)
                return True
            elif event.type() == QEvent.Leave:
                if not self.is_playing_gif:
                    self.setPixmap(self.normal_pixmap)
                return True
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.setPixmap(self.pressed_pixmap)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton:
                    self.action_triggered.emit()
                    return True
        return super().eventFilter(obj, event)

# --- Başlık Çubuğu Butonları İçin Özel QLabel Alt Sınıfı ---
class _TitleBarButton(QLabel):
    def __init__(self, text, parent, object_name):
        super().__init__(text, parent)
        self.setObjectName(object_name)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.normal_style = f"""
            QLabel#{self.objectName()} {{
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-size: 14pt;
                font-family: "Segoe UI Symbol", "DejaVu Sans", "Arial";
            }}
        """
        self.hover_style = "background-color: #444444; color: #ffffff;"
        self.close_hover_style = "background-color: #e81123; color: #ffffff;"
        self.setStyleSheet(self.normal_style)

    def enterEvent(self, event):
        if self.objectName() == "CloseButton":
            self.setStyleSheet(self.close_hover_style)
        else:
            self.setStyleSheet(self.hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.normal_style)
        super().leaveEvent(event)

# --- Özel Başlık Çubuğu Sınıfı ---
class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(30)

        self.setStyleSheet("""
            #CustomTitleBar {
                background-color: #222222;
                color: #ffffff;
                border-bottom: 1px solid #333333;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            #TitleLabel {
                font-family: Arial;
                font-size: 10pt;
                font-weight: bold;
                padding-left: 10px;
                color: #ffffff;
            }
        """)

        title_bar_layout = QHBoxLayout(self)
        title_bar_layout.setContentsMargins(5, 0, 0, 0) # Sol kenardan boşluk bırak
        title_bar_layout.setSpacing(5) # İkon ve yazı arası boşluk

        # İkonu ekle
        self.icon_label = QLabel(self)
        if os.path.exists(ICON_PATH):
            pixmap = QPixmap(ICON_PATH)
            scaled_pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation) # İkon boyutunu ayarla
            self.icon_label.setPixmap(scaled_pixmap)
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setScaledContents(True)

        self.title_label = QLabel("LinAMP", self)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setFont(QFont("Arial", 10, QFont.Bold))

        self.minimize_button = self._create_title_bar_button("−", "minimize_btn")
        self.close_button = self._create_title_bar_button("✕", "close_btn")
        self.close_button.setObjectName("CloseButton")

        self.minimize_button.mouseReleaseEvent = lambda e: self.parent_window.showMinimized()
        self.close_button.mouseReleaseEvent = lambda e: self.parent_window.close()

        title_bar_layout.addWidget(self.icon_label) # İkonu ekle
        title_bar_layout.addWidget(self.title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(self.minimize_button)
        title_bar_layout.addWidget(self.close_button)

        self.old_pos = None

    def _create_title_bar_button(self, text, object_name):
        btn = _TitleBarButton(text, self, object_name)
        return btn

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.parent_window.move(self.parent_window.pos() + delta)
            self.old_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None
        super().mouseReleaseEvent(event)

    def set_title_text(self, text):
        self.title_label.setText(text)

# --- Custom VU Meter Bar Class ---
class VUMeterBar(QWidget):
    def __init__(self, bar_color=QColor("#0071ff"), parent=None):
        super().__init__(parent)
        self._level = 0.0
        self._peak_hold_level = 0.0
        self._peak_hold_timer = QTimer(self)
        self._peak_hold_timer.setSingleShot(True)
        self._peak_hold_timer.timeout.connect(self._decay_peak_hold)
        
        self.bar_color = bar_color
        self.setFixedSize(250, 15) 
        self.setStyleSheet("background-color: #333333; border: none; border-radius: 3px;")

    def set_level(self, level):
        level = max(0.0, min(1.0, level))
        if self._level != level:
            self._level = level
            self.update()

            if level > self._peak_hold_level:
                self._peak_hold_level = level
                self._peak_hold_timer.start(500)
            elif not self._peak_hold_timer.isActive():
                 self._peak_hold_level = level
                 self.update()
                 self._peak_hold_timer.stop()
                 
    def _decay_peak_hold(self):
        self._peak_hold_level = max(0.0, self._peak_hold_level * 0.8)
        if self._peak_hold_level > 0.01:
            self._peak_hold_timer.start(50)
        else:
            self._peak_hold_level = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        bar_width = int(rect.width() * self._level)
        
        painter.setBrush(QColor(self.bar_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect.left(), rect.top(), bar_width, rect.height())

        if self._peak_hold_level > 0.0:
            peak_pixel_width = 2
            peak_x_pos = int(rect.width() * self._peak_hold_level)
            
            painter.setBrush(QColor(255, 255, 0, 200))
            painter.drawRect(peak_x_pos - peak_pixel_width, rect.top(), peak_pixel_width, rect.height())

        super().paintEvent(event)

# --- Özel QSlider Alt Sınıfı (Tıklama ile pozisyon değiştirme için) ---
class ClickableSlider(QSlider):
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.orientation() == Qt.Horizontal:
                value = self.minimum() + ((self.maximum() - self.minimum()) * event.x()) / self.width()
            else:
                value = self.minimum() + ((self.maximum() - self.minimum()) * (self.height() - event.y())) / self.height()
            
            self.setValue(int(value))
        super().mousePressEvent(event)


# --- Yeni Hakkında Penceresi Sınıfı ---
class AboutWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LinAMP - About")
        self.setFixedSize(400, 250)
        # Çerçevesiz pencere ayarını kaldırıldı
        # self.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #2e2e2e;
                border: 1px solid #444;
                border-radius: 5px;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #555555;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #4a4a4a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("LinAMP mp3 player")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title, alignment=Qt.AlignCenter)

        # Yeni metin bloğu
        info_text = QLabel(
            "Licence: GNU GPLv3\n"
            "Script language: Python3\n" # Yazım hatası düzeltildi
            "GUI: Qt\n"
            "Platform: Debian based linux systems\n"
            "Author: A. Serhat KILIÇOĞLU (with help from Google Gemini AI)\n"
            "Github: www.github.com/shampuan"
        )
        info_text.setFont(QFont("Arial", 9))
        info_text.setAlignment(Qt.AlignLeft) # Sola hizalandı
        layout.addSpacing(15) # Bir satır boşluk ekler
        layout.addWidget(info_text, alignment=Qt.AlignLeft)
        
        description = QLabel(
            "A simple and lightweight program to play your mp3 archives.\n"
            "This program comes with absolutely no warranty."
        )
        description.setFont(QFont("Arial", 9))
        description.setAlignment(Qt.AlignLeft) # Sola hizalandı
        layout.addWidget(description, alignment=Qt.AlignLeft)

        layout.addStretch(1)

        close_button = QPushButton("Kapat")
        close_button.setFixedSize(100, 30)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)
        
# --- Sürükle-Bırak Özelliği İçin Özel QListWidget Sınıfı ---
class CustomPlaylistWidget(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event):
        # Sadece dosyaları veya kendi içindeki öğeleri kabul et
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        # Sadece dosyaları veya kendi içindeki öğeleri kabul et
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.mp3', '.wav', '.ogg', '.flac')):
                    file_paths.append(url.toLocalFile())
            self.files_dropped.emit(file_paths)
            event.acceptProposedAction()
        else:
            # İçerideki sürükle-bırak işlemi için temel sınıfın dropEvent'ini kullan
            super().dropEvent(event)
            event.acceptProposedAction()


# --- Ana Pencere Sınıfı ---
class MusicPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinAMP")
        
        self.setFixedWidth(400) 

        # Yeni başlık çubuğu için pencere ikonunu ayarla
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.main_container = QWidget()
        self.setCentralWidget(self.main_container)
        self.main_container.setStyleSheet("""
            QWidget {
                background-color: #2e2e2e;
                border-radius: 5px;
                border: 1px solid #444;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 4px;
                background: #000000;
                margin: 0px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #bbbbbb;
                border: 1px solid #777;
                width: 10px;
                height: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
            
            #progress_slider::sub-page:horizontal {
                background: #0071ff;
            }
            #progress_slider::add-page:horizontal {
                background: #000000;
            }

            #volume_slider::sub-page:horizontal {
                background: #bb9c00;
            }
            #volume_slider::add-page:horizontal {
                background: #000000;
            }

            QListWidget {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                color: #ffffff;
                selection-background-color: #555555;
                selection-color: #ffffff;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #3a3a3a;
                color: #ffffff;
            }
            QListWidget::item:alternate {
                background-color: #353535;
            }
            QListWidget::item:hover {
                background-color: #4a4a4a;
            }
            QListWidget::item:selected {
                background-color: #555555;
                color: #ffffff;
            }
        """)
        
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setWindowTitle("LinAMP")

        # ------------- Kontrol Elemanlarının Tanımlanması -------------
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volume_slider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(25)
        self.volume_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.progress_slider = ClickableSlider(Qt.Horizontal)
        self.progress_slider.setObjectName("progress_slider")
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_slider.setTracking(False)

        self.shuffle_button = ImageButton(
            "shuffle_normal.png", 
            "shuffle_cursor.png", 
            "shuffle_basık.png", 
            "shuffle_basık.png",
            is_toggle=True
        )
        self.shuffle_button.action_triggered.connect(self.on_shuffle_button_action)
        
        self.repeat_button = ImageButton(
            "repeat_normal.png", 
            "repeat_cursor.png", 
            "repeat_basık.png", 
            "repeat_basık.png",
            is_toggle=True
        )
        self.repeat_button.action_triggered.connect(self.on_repeat_button_action)

        self.album_art_label = QLabel(self)
        self.album_art_label.setFixedSize(64, 64)
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setWordWrap(True)
        self.album_art_label.setText("No\nAlbum\nArt") 
        self.album_art_label.setFont(QFont("Arial", 8))
        self.album_art_label.setStyleSheet("QLabel { color: #aaaaaa; border: 1px solid #555; background-color: #333; border-radius: 3px; }")

        self.prev_button = ImageButton(
            "önceki_normal.png",
            "önceki_cursor.png",
            "önceki_basık.png"
        )
        self.prev_button.action_triggered.connect(self.on_prev_button_action)

        self.play_button = ImageButton(
            "play_normal.png",
            "play_cursor.png",
            "play_basık.png",
            is_externally_persistent_controlled=True
        )
        self.play_button.action_triggered.connect(self.on_play_button_action)

        self.pause_button = AnimatedButton(
            "pause_normal.png",
            "pause_cursor.png",
            "pause_basık_low.png",
            "pause_basık_animated.gif"
        )
        self.pause_button.action_triggered.connect(self.on_pause_button_action)

        self.next_button = ImageButton(
            "sonraki_normal.png",
            "sonraki_cursor.png",
            "sonraki_basık.png"
        )
        self.next_button.action_triggered.connect(self.on_next_button_action)

        self.stop_button = ImageButton(
            "stop_normal.png",
            "stop_cursor.png",
            "stop_basık.png"
        )
        self.stop_button.action_triggered.connect(self.on_stop_button_action)
        # -----------------------------------------------------------------

        # 2. İlerleme Çubuğu - Ses Çubuğu
        sliders_row_layout = QHBoxLayout()
        sliders_row_layout.setContentsMargins(10, 10, 10, 5)
        sliders_row_layout.setSpacing(10)
        
        sliders_row_layout.addWidget(self.progress_slider, stretch=85)
        sliders_row_layout.addWidget(self.volume_slider, stretch=15)
        main_layout.addLayout(sliders_row_layout)

        # YENİ: Time Display ve About Butonu
        self.about_button = QPushButton("About")
        self.about_button.setFixedSize(QSize(60, 20)) 
        self.about_button.setFont(QFont("Arial", 8, QFont.Bold))
        self.about_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #4a4a4a;
                border-radius: 3px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #5a5a5a;
            }
        """)
        self.about_button.clicked.connect(self.show_about_dialog)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont("Arial", 9))
        self.time_label.setStyleSheet("color: #aaaaaa; padding: 2px 0;")
        self.time_label.setAlignment(Qt.AlignCenter)

        time_display_layout = QHBoxLayout()
        # Kenar boşluğunu sağdan 10 piksel olacak şekilde ayarla
        time_display_layout.setContentsMargins(0, 0, 10, 0)
        time_display_layout.addStretch(1)
        time_display_layout.addWidget(self.time_label)
        time_display_layout.addStretch(1)
        time_display_layout.addWidget(self.about_button)
        main_layout.addLayout(time_display_layout)


        # 3. Karışık Mod - Tekrarla Modu (Alt Alta ve Sola Yaslı) - VU Metreler - Albüm Kapağı (Sağa Yaslı)
        mode_buttons_vbox = QVBoxLayout()
        mode_buttons_vbox.setContentsMargins(0, 0, 0, 0)
        mode_buttons_vbox.setSpacing(5)
        mode_buttons_vbox.addWidget(self.shuffle_button, alignment=Qt.AlignLeft)
        mode_buttons_vbox.addWidget(self.repeat_button, alignment=Qt.AlignLeft)
        mode_buttons_vbox.addStretch(1)

        self.left_vu_meter = VUMeterBar(QColor("#0071ff"))
        self.right_vu_meter = VUMeterBar(QColor("#0071ff"))

        left_label = QLabel("L")
        left_label.setFont(QFont("Arial", 10, QFont.Bold))
        left_label.setStyleSheet("color: white; qproperty-indent: 0; margin-right: 8px;") 
        
        left_channel_layout = QHBoxLayout()
        left_channel_layout.setContentsMargins(0,0,0,0)
        left_channel_layout.setSpacing(0)
        left_channel_layout.addWidget(left_label, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        left_channel_layout.addWidget(self.left_vu_meter)
        left_channel_layout.addStretch(1)

        right_label = QLabel("R")
        right_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_label.setStyleSheet("color: white; margin-right: 5px; qproperty-indent: 0;")
        
        right_channel_layout = QHBoxLayout()
        right_channel_layout.setContentsMargins(0,0,0,0)
        right_channel_layout.setSpacing(0)
        right_channel_layout.addWidget(right_label, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        right_channel_layout.addWidget(self.right_vu_meter)
        right_channel_layout.addStretch(1)

        vu_meters_vbox = QVBoxLayout()
        vu_meters_vbox.setContentsMargins(0, 0, 0, 0)
        vu_meters_vbox.setSpacing(1) 
        vu_meters_vbox.addLayout(left_channel_layout)
        vu_meters_vbox.addLayout(right_channel_layout)

        mode_and_album_row_layout = QHBoxLayout()
        mode_and_album_row_layout.setContentsMargins(10, 2, 10, 2) 
        mode_and_album_row_layout.setSpacing(10)

        mode_and_album_row_layout.addLayout(mode_buttons_vbox)

        mode_and_album_row_layout.addStretch(1)
        mode_and_album_row_layout.addLayout(vu_meters_vbox)
        mode_and_album_row_layout.addStretch(1)

        mode_and_album_row_layout.addWidget(self.album_art_label, alignment=Qt.AlignRight | Qt.AlignVCenter)
        
        main_layout.addLayout(mode_and_album_row_layout)

        # 4. Oynatıcı Kontrol Düğmeleri (Önceki-Play-Pause-Sonraki-Stop)
        player_buttons_layout = QHBoxLayout()
        player_buttons_layout.setContentsMargins(10, 5, 10, 10)
        player_buttons_layout.setSpacing(10)
        player_buttons_layout.addStretch(1)
        player_buttons_layout.addWidget(self.prev_button)
        player_buttons_layout.addWidget(self.play_button)
        player_buttons_layout.addWidget(self.pause_button)
        player_buttons_layout.addWidget(self.next_button)
        player_buttons_layout.addWidget(self.stop_button)
        player_buttons_layout.addStretch(1)
        main_layout.addLayout(player_buttons_layout)
        
        # 5. Playlist Widget'i
        self.playlist_widget = CustomPlaylistWidget() # BURADA YENİ SINIFI KULLANIYORUZ
        self.playlist_widget.setMinimumHeight(100)
        self.playlist_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.playlist_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        main_layout.addWidget(self.playlist_widget)
        
        self.playlist_widget.itemDoubleClicked.connect(self._playlist_item_double_clicked)
        
        # Sürükle-bırak sonrası medya listesini güncellemek için sinyal bağlantısı
        self.playlist_widget.model().rowsMoved.connect(self._rebuild_media_playlist_on_move)
        
        # Yeni şarkıların eklenmesi için sinyal bağlantısı
        self.playlist_widget.files_dropped.connect(self._add_files_to_playlist)


        # --- QMediaPlayer ve QMediaPlaylist Entegrasyonu ---
        self.media_player = QMediaPlayer(self)
        self.media_playlist = QMediaPlaylist(self)
        self.media_player.setPlaylist(self.media_playlist)
        self.media_player.setVolume(self.volume_slider.value())

        self.auto_advance_pending = False
        
        self._ignoring_position_updates = False
        self._seek_ignore_timer = QTimer(self)
        self._seek_ignore_timer.setSingleShot(True)
        self._seek_ignore_timer.timeout.connect(lambda: setattr(self, '_ignoring_position_updates', False))


        # --- VU Metre için QAudioProbe ---
        self.audio_probe = QAudioProbe(self)
        self.audio_probe.setSource(self.media_player)
        self.audio_probe.audioBufferProbed.connect(self._process_audio_buffer)

        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
        self.media_player.positionChanged.connect(self.update_progress_slider_position)
        self.media_player.durationChanged.connect(self.update_progress_slider_range)
        self.progress_slider.sliderMoved.connect(self.on_progress_slider_moved_by_user)
        self.progress_slider.sliderReleased.connect(self.on_progress_slider_released_by_user)
        self.media_player.stateChanged.connect(self.on_media_player_state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_player_status_changed)
        
        self.media_playlist.currentIndexChanged.connect(self._playlist_current_index_changed)
        self.media_playlist.setPlaybackMode(QMediaPlaylist.Sequential)

        # Time display için bağlantılar
        self.media_player.positionChanged.connect(self._update_time_display)
        self.media_player.durationChanged.connect(self._update_time_display)

        # Uygulama başlatıldığında ayarları yükle
        self.load_state()

    def show_about_dialog(self):
        dialog = AboutWindow(self)
        dialog.exec_()
        
    # --- Yeni Drag-and-Drop ve Deletion Metotları ---
    def keyPressEvent(self, event):
        """Klavye tuş basmalarını işler, özellikle Silme (Delete) tuşu için."""
        if event.key() == Qt.Key_Delete and self.playlist_widget.hasFocus():
            self._delete_selected_items()
        super().keyPressEvent(event)

    def _delete_selected_items(self):
        """Seçilen öğeleri çalma listesinden ve mediaplayer'dan kaldırır."""
        selected_items = self.playlist_widget.selectedItems()
        if not selected_items:
            return

        # Oynatılan şarkı siliniyorsa durdur
        current_index = self.media_playlist.currentIndex()
        
        # Öğeleri sondan başa doğru silerek indeks kaymalarını önle
        rows = sorted([self.playlist_widget.row(item) for item in selected_items], reverse=True)
        
        for row in rows:
            if row == current_index:
                 self.media_player.stop()
                 current_index = -1
            self.playlist_widget.takeItem(row)
            self.media_playlist.removeMedia(row)

        self.save_state()

    def _add_files_to_playlist(self, file_paths):
        """Playlist'e dosya ekler, duplicates kontrolü yaparak."""
        for file_path in file_paths:
            if file_path not in [self.playlist_widget.item(i).data(Qt.UserRole) for i in range(self.playlist_widget.count())]:
                list_item = QListWidgetItem(os.path.basename(file_path))
                list_item.setData(Qt.UserRole, file_path) # Dosya yolunu item'a kaydet
                self.playlist_widget.addItem(list_item)
                self.media_playlist.addMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        
        if self.media_playlist.mediaCount() > 0 and self.media_playlist.currentIndex() == -1:
            self.media_playlist.setCurrentIndex(0)
        
        if self.media_player.state() == QMediaPlayer.StoppedState and self.media_playlist.mediaCount() > 0:
            self.play_button.set_persistent_pressed(False)
            self.pause_button.stop_animation()
        self.save_state() # Yeni playlisti kaydet


    def _rebuild_media_playlist_on_move(self, parent, start, end, destination, row):
        """QListWidget'in güncel sırasına göre QMediaPlaylist'i yeniden oluşturur."""
        current_media = self.media_player.currentMedia()
        
        # Yeniden oluşturma daha güvenli
        self.media_playlist.clear()
        
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            # Item'e önceden kaydedilen dosya yolunu al
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                 self.media_playlist.addMedia(QMediaContent(QUrl.fromLocalFile(file_path)))

        if current_media:
            # Yeniden oluşturulan playlistteki eski şarkıyı bul ve çalmaya devam et
            for i in range(self.media_playlist.mediaCount()):
                if self.media_playlist.media(i).canonicalUrl() == current_media.canonicalUrl():
                    self.media_playlist.setCurrentIndex(i)
                    if self.media_player.state() == QMediaPlayer.PlayingState:
                        self.media_player.play()
                    break

        self.save_state()


    def add_to_playlist(self, file_path):
        if file_path not in [item.data(Qt.UserRole) for item in self.playlist_widget.findItems("", Qt.MatchContains)]:
            list_item = QListWidgetItem(os.path.basename(file_path))
            list_item.setData(Qt.UserRole, file_path) # Dosya yolunu item'a kaydet
            self.playlist_widget.addItem(list_item)
            self.media_playlist.addMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        else:
            pass

    # --- QMediaPlaylist ile Senkronizasyon Metotları ---
    def _playlist_current_index_changed(self, index):
        if index >= 0 and index < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(index) 
            
            current_media = self.media_playlist.media(index)
            if current_media.canonicalUrl().isLocalFile():
                file_path = current_media.canonicalUrl().toLocalFile()
                file_name = file_path.split('/')[-1].split('\\')[-1]
                self.setWindowTitle(f"LinAMP - {file_name}")
                self._load_album_art(file_path) 
            else:
                self.setWindowTitle("LinAMP")
                self.album_art_label.clear() 
                self.album_art_label.setText("No Album Art")
        else:
            self.setWindowTitle("LinAMP")
            if self.media_player.state() != QMediaPlayer.StoppedState:
                self.media_player.stop()
            self.album_art_label.clear() 
            self.album_art_label.setText("No Album Art")


    def _playlist_item_double_clicked(self, item):
        row = self.playlist_widget.row(item)
        if self.media_playlist.currentIndex() != row:
            self.media_playlist.setCurrentIndex(row)
        
        if self.media_player.state() != QMediaPlayer.PlayingState:
            self.media_player.play()
    
    def update_progress_slider_range(self, duration):
        self.progress_slider.setMaximum(duration)
        self._update_time_display(duration_ms=duration)

    def update_progress_slider_position(self, position):
        if self._ignoring_position_updates:
            return
        if not self.progress_slider.isSliderDown():
            self.progress_slider.setValue(position)
            self._update_time_display(position_ms=position)


    def on_progress_slider_moved_by_user(self, position):
        pass 

    def on_progress_slider_released_by_user(self):
        position = self.progress_slider.value()
        self._ignoring_position_updates = True
        self.media_player.setPosition(position)
        self._seek_ignore_timer.start(1000)

    def on_media_player_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_button.set_persistent_pressed(True)
            self.pause_button.stop_animation()
        elif state == QMediaPlayer.PausedState:
            self.play_button.set_persistent_pressed(True)
            self.pause_button.start_animation()
            self.left_vu_meter.set_level(0.0)
            self.right_vu_meter.set_level(0.0)
        elif state == QMediaPlayer.StoppedState:
            self.play_button.set_persistent_pressed(False)
            self.pause_button.stop_animation()
            self.left_vu_meter.set_level(0.0)
            self.right_vu_meter.set_level(0.0)
            self.progress_slider.setValue(0)
            self._update_time_display(0, 0) 
            if self.media_playlist.currentIndex() == -1 or self.media_playlist.mediaCount() == 0:
                 self.setWindowTitle("LinAMP")
                 self.album_art_label.clear() 
                 self.album_art_label.setText("No Album Art")

    def on_media_player_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            pass
        elif status == QMediaPlayer.LoadedMedia:
            pass
        elif status == QMediaPlayer.NoMedia:
            self.album_art_label.clear()
            self.album_art_label.setText("No Album Art")
        elif status == QMediaPlayer.InvalidMedia:
            self.album_art_label.clear()
            self.album_art_label.setText("No Album Art")

    def _update_time_display(self, position_ms=None, duration_ms=None):
        if position_ms is None:
            position_ms = self.media_player.position()
        if duration_ms is None:
            duration_ms = self.media_player.duration()

        if duration_ms <= 0:
            self.time_label.setText("00:00 / 00:00")
            return

        current_seconds = position_ms // 1000
        total_seconds = duration_ms // 1000

        current_minutes = current_seconds // 60
        current_remaining_seconds = current_seconds % 60

        total_minutes = total_seconds // 60
        total_remaining_seconds = total_seconds % 60

        time_str = (f"{current_minutes:02d}:{current_remaining_seconds:02d} / "
                    f"{total_minutes:02d}:{total_remaining_seconds:02d}")
        self.time_label.setText(time_str)

    # Albüm kapağını yükleme metodu
    def _load_album_art(self, file_path):
        self.album_art_label.clear() 
        self.album_art_label.setText("No Album Art") 

        try:
            audio = MP3(file_path)
            for tag_name in audio.tags.keys():
                if tag_name.startswith('APIC'):
                    apic_tag = audio.tags[tag_name]
                    if isinstance(apic_tag, APIC):
                        image_data = apic_tag.data
                        
                        image = QImage()
                        if image.loadFromData(image_data):
                            pixmap = QPixmap.fromImage(image)
                            scaled_pixmap = pixmap.scaled(self.album_art_label.size(), 
                                                           Qt.KeepAspectRatio, 
                                                           Qt.SmoothTransformation)
                            self.album_art_label.setPixmap(scaled_pixmap)
                            self.album_art_label.setText("") 
                            return
                        else:
                            break 
        except ID3NoHeaderError:
            pass
        except Exception as e:
            pass
        
        self.album_art_label.setText("No Album Art")


    def _process_audio_buffer(self, buffer: QAudioBuffer):
        if self.media_player.state() != QMediaPlayer.PlayingState:
            self.left_vu_meter.set_level(0.0)
            self.right_vu_meter.set_level(0.0)
            return

        fmt = buffer.format()
        
        if fmt.sampleSize() != 16 or fmt.sampleType() != QAudioFormat.SignedInt:
            self.left_vu_meter.set_level(0.0)
            self.right_vu_meter.set_level(0.0)
            return

        data_bytes = buffer.constData().asarray(buffer.byteCount())
        
        num_samples = len(data_bytes) // 2 
        
        try:
            samples = struct.unpack(f'<{num_samples}h', data_bytes) 
        except struct.error as e:
            self.left_vu_meter.set_level(0.0)
            self.right_vu_meter.set_level(0.0)
            return
        
        max_amplitude = 2**15 - 1 

        left_peak = 0
        right_peak = 0
        
        num_channels = fmt.channelCount()
        if num_channels >= 1:
            for i in range(0, num_samples, num_channels):
                left_peak = max(left_peak, abs(samples[i]))
        if num_channels >= 2:
            for i in range(1, num_samples, num_channels):
                right_peak = max(right_peak, abs(samples[i]))

        norm_left = left_peak / max_amplitude if max_amplitude > 0 else 0
        norm_right = right_peak / max_amplitude if max_amplitude > 0 else 0
        
        self.left_vu_meter.set_level(norm_left)
        self.right_vu_meter.set_level(norm_right)


    def on_play_button_action(self):
        if self.media_playlist.mediaCount() == 0:
            return

        if self.media_player.state() == QMediaPlayer.PlayingState:
            pass
        elif self.media_player.state() == QMediaPlayer.PausedState:
            self.media_player.play()
        elif self.media_player.state() == QMediaPlayer.StoppedState:
            if self.media_playlist.currentIndex() == -1:
                self.media_playlist.setCurrentIndex(0) 
            self.media_player.play()

    def on_pause_button_action(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        elif self.media_player.state() == QMediaPlayer.PausedState:
            self.media_player.play()
        else:
            pass
        
    def on_stop_button_action(self):
        self.media_player.stop()
        self.left_vu_meter.set_level(0.0)
        self.right_vu_meter.set_level(0.0)
        self.progress_slider.setValue(0)
        self._update_time_display(0, 0) 

    def on_prev_button_action(self):
        if self.media_playlist.mediaCount() == 0:
            return
        
        was_playing = (self.media_player.state() == QMediaPlayer.PlayingState)

        self.media_playlist.previous()
        if was_playing:
            self.media_player.play()
        else:
            self.media_player.setPosition(0)

    def on_next_button_action(self):
        if self.media_playlist.mediaCount() == 0:
            return

        was_playing = (self.media_player.state() == QMediaPlayer.PlayingState)
        
        self.media_playlist.next()
        if was_playing:
            self.media_player.play()
        else:
            self.media_player.setPosition(0)

    def on_shuffle_button_action(self):
        if self.shuffle_button.is_active:
            self.media_playlist.setPlaybackMode(QMediaPlaylist.Random)
        else:
            if self.repeat_button.is_active:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Loop)
            else:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Sequential)
        self.save_state()
        
    def on_repeat_button_action(self):
        if self.repeat_button.is_active:
            self.media_playlist.setPlaybackMode(QMediaPlaylist.Loop)
        else:
            if self.shuffle_button.is_active:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Random)
            else:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Sequential)
        self.save_state()

    def load_state(self):
        """Uygulama ayarlarını ve çalma listesini bir JSON dosyasından yükler."""
        # Klasör ve dosyanın varlığını program başlar başlamaz kontrol et ve oluştur
        if not os.path.exists(APP_DATA_DIR):
            try:
                os.makedirs(APP_DATA_DIR)
            except OSError:
                return

        if not os.path.exists(DB_FILE_PATH):
            try:
                with open(DB_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except IOError:
                return

        try:
            with open(DB_FILE_PATH, 'r', encoding='utf-8') as f:
                state = json.load(f)

            volume = state.get('volume', 25)
            self.volume_slider.setValue(volume)
            self.media_player.setVolume(volume)

            shuffle_mode = state.get('shuffle_mode', False)
            repeat_mode = state.get('repeat_mode', False)
            
            self.shuffle_button.is_active = shuffle_mode
            self.repeat_button.is_active = repeat_mode
            
            if shuffle_mode:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Random)
            elif repeat_mode:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Loop)
            else:
                self.media_playlist.setPlaybackMode(QMediaPlaylist.Sequential)
            
            playlist_files = state.get('playlist', [])
            self.media_playlist.clear()
            self.playlist_widget.clear()
            for file_path in playlist_files:
                if os.path.exists(file_path):
                    list_item = QListWidgetItem(os.path.basename(file_path))
                    list_item.setData(Qt.UserRole, file_path) # Dosya yolunu item'a kaydet
                    self.playlist_widget.addItem(list_item)
                    self.media_playlist.addMedia(QMediaContent(QUrl.fromLocalFile(file_path)))

            if self.media_playlist.mediaCount() > 0:
                self.media_playlist.setCurrentIndex(0)
            
        except (IOError, json.JSONDecodeError):
            try:
                 with open(DB_FILE_PATH, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except IOError:
                pass


    def save_state(self):
        """Uygulama ayarlarını ve çalma listesini bir JSON dosyasına kaydeder."""
        state = {
            'playlist': [item.data(Qt.UserRole) for item in [self.playlist_widget.item(i) for i in range(self.playlist_widget.count())] if item.data(Qt.UserRole)],
            'volume': self.volume_slider.value(),
            'shuffle_mode': self.shuffle_button.is_active,
            'repeat_mode': self.repeat_button.is_active
        }

        try:
            with open(DB_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
        except IOError:
            pass

    def closeEvent(self, event):
        self.save_state()

        if self.media_player.state() != QMediaPlayer.StoppedState:
            self.media_player.stop()
        
        self.audio_probe.setSource(None)
        self.media_playlist.clear()

        super().closeEvent(event)


# --- Uygulamayı Başlatma ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyleSheet("""
        QScrollBar:vertical {
            border: 1px solid #444;
            background: #2e2e2e;
            width: 8px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #555;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
        }
        QScrollBar::sub-line:vertical {
            sub-line-length: 0px;
        }
        QScrollBar::add-line:vertical {
            sub-line-length: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QScrollBar:horizontal {
            border: 1px solid #444;
            background: #2e2e2e;
            height: 8px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            background: #555;
            min-width: 20px;
            border-radius: 4px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
    """)

    player = MusicPlayer()
    player.show()
    sys.exit(app.exec_())
