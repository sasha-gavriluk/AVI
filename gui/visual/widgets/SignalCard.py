from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect
from utils.OtherUtils import _handle_error
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class SignalCard(QFrame):
    def __init__(self, asset_name, parent=None):
        super().__init__(parent)
        self.asset_name = asset_name
        self.init_ui()

    def init_ui(self):
        self.setObjectName("SignalCard")
        # Base styling for the card - Dark glossy theme
        self.setStyleSheet("""
            QFrame#SignalCard {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E222D, stop:1 #131722);
                border-radius: 12px;
                border: 1px solid #2A2E39;
            }
            QFrame#SignalCard:hover {
                border: 1px solid #363A45;
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2A2E39, stop:1 #1E222D);
            }
        """)
        self.setMinimumSize(260, 170)
        self.setMaximumSize(320, 210)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header: Asset Name & Market State
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Asset label with bold modern font
        self.asset_label = QLabel(self.asset_name)
        self.asset_label.setStyleSheet("font-family: 'Segoe UI', Arial, sans-serif; font-size: 18px; font-weight: bold; color: #D1D4DC; background: transparent;")
        
        # State label as a small badge
        self.state_label = QLabel("UNKNOWN")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setStyleSheet("""
            background-color: #2A2E39;
            color: #787B86;
            padding: 4px 10px;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        """)
        
        header_layout.addWidget(self.asset_label)
        header_layout.addStretch()
        header_layout.addWidget(self.state_label)
        layout.addLayout(header_layout)
        
        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #2A2E39;")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        
        # Body: Signal & Confidence
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 10, 0, 10)
        
        self.signal_label = QLabel("WAIT")
        self.signal_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.signal_label.setStyleSheet("""
            font-family: 'Segoe UI', sans-serif;
            font-size: 26px;
            font-weight: 900;
            color: #787B86;
            background: transparent;
            letter-spacing: 1px;
        """)
        
        self.conf_label = QLabel("0%")
        self.conf_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.conf_label.setStyleSheet("""
            font-family: 'Segoe UI', sans-serif;
            font-size: 16px;
            font-weight: bold;
            color: #787B86;
            background: transparent;
        """)
        
        body_layout.addWidget(self.signal_label)
        body_layout.addStretch()
        body_layout.addWidget(self.conf_label)
        layout.addLayout(body_layout)
        
        # Footer: Reason/Info
        self.reason_label = QLabel("Очікування даних...")
        self.reason_label.setWordWrap(True)
        self.reason_label.setStyleSheet("""
            font-family: 'Segoe UI', sans-serif;
            font-size: 11px;
            color: #8A919E;
            background: transparent;
        """)
        self.reason_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(self.reason_label)
        layout.addStretch()

        # Add drop shadow for depth
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    @_handle_error
    def update_signal(self, data: dict):
        state = data.get("market_state", "UNKNOWN")
        self.state_label.setText(state.upper())
        
        # Colors for Market State
        state_colors = {
            "TREND": ("#22AB94", "rgba(34, 171, 148, 0.15)"),    # Greenish text, very dim green bg
            "FLAT": ("#2962FF", "rgba(41, 98, 255, 0.15)"),      # Blue text, dim blue bg
            "EXPLOSION": ("#FF9800", "rgba(255, 152, 0, 0.15)")  # Orange text, dim orange bg
        }
        
        text_color, bg_color = state_colors.get(state, ("#787B86", "#2A2E39"))
        self.state_label.setStyleSheet(f"""
            background-color: {bg_color};
            color: {text_color};
            padding: 4px 10px;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 10px;
            font-weight: bold;
            border: 1px solid {text_color};
        """)

        signal = data.get("signal", "NEUTRAL")
        self.signal_label.setText(signal)
        
        # Colors and glow for Signal
        if signal == "BUY":
            sig_color = "#22AB94" # TradingView bright green
            glow_color = QColor(34, 171, 148, 160)
            self.conf_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {sig_color}; background: transparent;")
        elif signal == "SELL":
            sig_color = "#F23645" # TradingView bright red
            glow_color = QColor(242, 54, 69, 160)
            self.conf_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {sig_color}; background: transparent;")
        else:
            sig_color = "#787B86" # Gray
            glow_color = QColor(120, 123, 134, 100)
            self.conf_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #787B86; background: transparent;")
            
        self.signal_label.setStyleSheet(f"""
            font-family: 'Segoe UI', sans-serif;
            font-size: 28px;
            font-weight: 900;
            color: {sig_color};
            background: transparent;
            letter-spacing: 1px;
        """)
        
        # Add glow effect specifically to signal text
        sig_shadow = QGraphicsDropShadowEffect(self)
        sig_shadow.setBlurRadius(12)
        sig_shadow.setOffset(0, 0)
        sig_shadow.setColor(glow_color)
        self.signal_label.setGraphicsEffect(sig_shadow)
        
        conf = data.get("confidence", 0.0)
        self.conf_label.setText(f"{int(conf * 100)}% CONF")

        reason = data.get("block_reason")
        if not reason:
            if signal in ["BUY", "SELL"]:
                # Якщо FCryptoLogic віддає перелік спрацьованих тригерів — показуємо їх
                fired = data.get("active_signals")
                if fired:
                    parts = [f"{s.get('name')} (вага {s.get('weight')}→{s.get('contribution')})" for s in fired]
                    reason = " | ".join(parts)
                else:
                    # Інакше — чесний мінімум із наявних полів (без вигаданих "Ідеальних умов")
                    state = data.get("market_state", "")
                    triggers = data.get("active_triggers", 0)
                    reason = f"{state} · тригерів: {triggers} · {int(conf * 100)}%"
            else:
                reason = "Очікування сигналу"

        self.reason_label.setText(reason)
