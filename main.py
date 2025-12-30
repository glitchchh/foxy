import sys
import random
import math
import os
import webbrowser
from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon
from PyQt6.QtCore import Qt, QTimer, QRect, QPointF, QPoint, QSize
from PyQt6.QtGui import QPixmap, QPainter, QCursor, QAction, QIcon

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class FoxCompanion(QWidget):
    def __init__(self):
        super().__init__()

        # spriteeeee
        self.SPRITE_PATH = resource_path("fox-NESW-bright.png")
        self.ICO_PATH = resource_path("icon.ico")
        
        self.BASE_WIDTH = 48
        self.BASE_HEIGHT = 64
        self.SCALE = 2 
        self.FRAME_WIDTH = self.BASE_WIDTH * self.SCALE
        self.FRAME_HEIGHT = self.BASE_HEIGHT * self.SCALE
        self.ANIM_DELAY = 150 
        
        self.DIR_MAP = {'N': 0, 'E': 1, 'S': 2, 'W': 3}
        
        # physics
        self.WANDER_SPEED = 1.2      
        self.LOITER_SPEED = 0.8      
        self.CHASE_SPEED = 2.8       
        self.SPRINT_SPEED = 7.5      
        self.ACCELERATION = 0.15     
        
        self.current_speed = 0.0
        self.STOP_THRESHOLD = 5.0    
        self.FOLLOW_DIST = 250.0     
        self.SPRINT_DIST = 800.0     
        self.LOITER_TRIGGER = 60.0   
        self.WANDER_RADIUS = 500.0  
        
        # logic
        self.pos = QPointF(500.0, 500.0)
        self.target = QPointF(500.0, 500.0)
        self.current_dir = 'S'
        self.frame_index = 1 
        self.state = "follow"       
        self.is_loitering = False   
        self.is_moving = False      
        self.waiting_timer = 0      
        
        self.init_ui()
        self.load_sprites()
        self.init_tray()
        
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(self.ANIM_DELAY)
        
        self.logic_timer = QTimer()
        self.logic_timer.timeout.connect(self.update_logic)
        self.logic_timer.start(16) 

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 
        self.setFixedSize(self.FRAME_WIDTH, self.FRAME_HEIGHT)
        self.show()

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        if os.path.exists(self.ICO_PATH):
            self.tray_icon.setIcon(QIcon(self.ICO_PATH))
        
        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu { background: #1e1e1e; color: white; border: 1px solid #333; border-radius: 8px; padding: 5px; }
            QMenu::item { padding: 8px 25px; border-radius: 4px; }
            QMenu::item:selected { background: #444; }
            QMenu::separator { height: 1px; background: #333; margin: 5px 10px; }
        """)

        author_act = QAction("by Glitchchh", self)
        author_act.setEnabled(False)
        
        github_act = QAction("GitHub Profile", self)
        github_act.triggered.connect(lambda: webbrowser.open("https://github.com/glitchchh"))

        f_act = QAction("Follow Cursor", self)
        f_act.setCheckable(True)
        f_act.setChecked(True)
        w_act = QAction("Full Wander", self)
        w_act.setCheckable(True)

        f_act.triggered.connect(lambda: self.set_state("follow", f_act, w_act))
        w_act.triggered.connect(lambda: self.set_state("wander", w_act, f_act))

        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(QApplication.instance().quit)

        self.menu.addAction(author_act)
        self.menu.addAction(github_act)
        self.menu.addSeparator()
        self.menu.addAction(f_act)
        self.menu.addAction(w_act)
        self.menu.addSeparator()
        self.menu.addAction(exit_act)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def load_sprites(self):
        if not os.path.exists(self.SPRITE_PATH):
            print(f"Error: {self.SPRITE_PATH} not found.")
            sys.exit(1)
        self.full_sprite_sheet = QPixmap(self.SPRITE_PATH)
        if self.full_sprite_sheet.isNull(): 
            sys.exit(1)

    def set_state(self, s, active_act, inactive_act):
        self.state = s
        self.is_loitering = False
        self.waiting_timer = 0
        active_act.setChecked(True)
        inactive_act.setChecked(False)
        if s == "wander": self.pick_random_screen_target()

    def pick_random_screen_target(self):
        screen = self.screen().availableGeometry()
        self.target = QPointF(random.randint(100, screen.width()-200), random.randint(100, screen.height()-200))

    def pick_loiter_target(self, cursor_centered):
        screen = self.screen().availableGeometry()
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(150, self.WANDER_RADIUS)
            tx, ty = cursor_centered.x() + math.cos(angle)*dist, cursor_centered.y() + math.sin(angle)*dist
            if 30 <= tx <= screen.width()-150 and 30 <= ty <= screen.height()-150:
                self.target = QPointF(tx, ty)
                return
        self.target = cursor_centered

    def update_animation(self):
        if self.is_moving:
            self.frame_index = (self.frame_index + 1) % 3
        else:
            self.frame_index = 1
            self.current_dir = 'S'
        self.update()

    def update_logic(self):
        cursor_pos = QCursor.pos()
        cursor_centered = QPointF(float(cursor_pos.x() - self.FRAME_WIDTH/2), float(cursor_pos.y() - self.FRAME_HEIGHT/2))
        target_speed = 0.0

        if self.state == "follow":
            dist_to_cursor = math.hypot(cursor_centered.x() - self.pos.x(), cursor_centered.y() - self.pos.y())
            if dist_to_cursor > self.LOITER_TRIGGER:
                self.is_loitering = False
                self.waiting_timer = 0
                self.target = cursor_centered 
                target_speed = self.SPRINT_SPEED if dist_to_cursor > self.SPRINT_DIST else self.CHASE_SPEED
            else:
                dist_to_target = math.hypot(self.target.x() - self.pos.x(), self.target.y() - self.pos.y())
                if dist_to_target < self.STOP_THRESHOLD:
                    if self.waiting_timer <= 0:
                        self.waiting_timer = random.randint(180, 480) 
                        self.is_loitering = True
                        self.pick_loiter_target(cursor_centered)
                    else:
                        self.waiting_timer -= 1
                if self.is_loitering and self.waiting_timer <= 0:
                    target_speed = self.LOITER_SPEED
            
        elif self.state == "wander":
            target_speed = self.WANDER_SPEED
            if math.hypot(self.target.x() - self.pos.x(), self.target.y() - self.pos.y()) < self.STOP_THRESHOLD:
                if random.random() < 0.005: self.pick_random_screen_target()

        self.current_speed += (target_speed - self.current_speed) * self.ACCELERATION
        diff = self.target - self.pos
        distance = math.hypot(diff.x(), diff.y())

        if distance > self.STOP_THRESHOLD and self.current_speed > 0.1:
            self.is_moving = True
            direction_vec = diff / distance
            self.pos += direction_vec * self.current_speed
            dx, dy = diff.x(), diff.y()
            if abs(dy) > abs(dx): self.current_dir = 'S' if dy > 0 else 'N'
            else: self.current_dir = 'E' if dx > 0 else 'W'
        else:
            self.is_moving = False

        self.move(self.pos.toPoint())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        row = self.DIR_MAP.get(self.current_dir, 2)
        source = QRect(self.frame_index * self.BASE_WIDTH, row * self.BASE_HEIGHT, self.BASE_WIDTH, self.BASE_HEIGHT)
        painter.drawPixmap(QRect(0, 0, self.FRAME_WIDTH, self.FRAME_HEIGHT), self.full_sprite_sheet, source)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    fox = FoxCompanion()
    sys.exit(app.exec())