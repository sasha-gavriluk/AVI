import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QGroupBox, QLineEdit, QProgressBar,
                             QScrollArea, QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class TabLiveAlgorithmicVisual(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ─── HEADER ────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("🧠 ON-DEMAND NN ANALYSIS")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #F9E2AF;")
        header.addWidget(title)
        header.addStretch()

        self.btn_analyze = QPushButton("🔥  ОТРИМАТИ ПРОГНОЗ ЗАРАЗ")
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: bold; color: #11111B;
                background-color: #89B4FA; border-radius: 6px; padding: 9px 18px;
            }
            QPushButton:hover  { background-color: #B4BEFE; }
            QPushButton:disabled { background-color: #45475A; color: #6C7086; }
        """)
        self.btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.btn_analyze)
        main_layout.addLayout(header)

        # ─── ASSETS ────────────────────────────────────────────────────
        assets_group = QGroupBox("⚙️ АКТИВИ ДЛЯ АНАЛІЗУ")
        assets_group.setStyleSheet(
            "QGroupBox { border: 1px solid #313244; border-radius: 6px; "
            "padding-top: 14px; color: #A6ADC8; font-weight: bold; }"
        )
        ag_layout = QHBoxLayout(assets_group)
        lbl = QLabel("Активи (через кому):")
        lbl.setStyleSheet("color: #CDD6F4;")
        self.assets_input = QLineEdit("EURUSD_15m, USDJPY_15m, EURGBP_15m")
        self.assets_input.setStyleSheet(
            "background: #181825; color: #CDD6F4; border: 1px solid #45475A; "
            "padding: 5px; border-radius: 4px;"
        )
        ag_layout.addWidget(lbl)
        ag_layout.addWidget(self.assets_input, 1)
        main_layout.addWidget(assets_group)

        # ─── RESULTS SCROLL ────────────────────────────────────────────
        self.results_group = QGroupBox("📊 РЕЗУЛЬТАТИ ОСТАННЬОЇ СВІЧКИ")
        self.results_group.setStyleSheet(
            "QGroupBox { border: 1px solid #313244; border-radius: 6px; "
            "padding-top: 14px; color: #A6ADC8; font-weight: bold; }"
        )
        rg_outer = QVBoxLayout(self.results_group)
        rg_outer.setContentsMargins(4, 4, 4, 4)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.results_container = QWidget()
        self.results_container.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(10)

        self._show_placeholder("Натисніть кнопку для аналізу ринку...")
        self.scroll.setWidget(self.results_container)
        rg_outer.addWidget(self.scroll)
        main_layout.addWidget(self.results_group, 1)

    # ── helpers ─────────────────────────────────────────────────────────

    def _clear(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_placeholder(self, text: str, color: str = "#585B70"):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-style: italic;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_layout.addWidget(lbl)
        self.results_layout.addStretch()

    def show_loading(self):
        self._clear()
        self._show_placeholder(
            "🔄 Розраховую індикатори та аналізую нейромережами...\n"
            "Зазвичай займає 5–15 секунд.",
            "#89B4FA"
        )
        self.btn_analyze.setEnabled(False)

    # ── public ──────────────────────────────────────────────────────────

    def display_results(self, results: list):
        self.btn_analyze.setEnabled(True)
        self._clear()

        if not results:
            self._show_placeholder(
                "❌ Не вдалося отримати дані.\nПеревірте, чи завантажена історія.", "#F38BA8"
            )
            return

        for res in results:
            self.results_layout.addWidget(self._make_asset_card(res))

        self.results_layout.addStretch()

    # ── card builder ────────────────────────────────────────────────────

    def _make_asset_card(self, res: dict) -> QGroupBox:
        asset        = res.get("asset", "?")
        signal       = res.get("signal")           # "BUY" / "SELL" / None
        probs        = res.get("probabilities", {})
        price        = res.get("price", 0.0)
        market_state = res.get("market_state", "-")
        trend_str    = res.get("trend_strength", "-")
        nn_sup       = res.get("nn_support", 0.0)
        nn_res       = res.get("nn_resistance", 0.0)
        nn_fb_b      = res.get("nn_fb_bullish", 0.0)
        nn_fb_be     = res.get("nn_fb_bearish", 0.0)
        mr_trend     = res.get("mr_trend", 0.0)
        mr_exp       = res.get("mr_explosion", 0.0)
        threshold    = res.get("threshold", 0.65)
        raw_buy      = res.get("raw_buy", 0.0)
        raw_sell     = res.get("raw_sell", 0.0)
        block_reason = res.get("block_reason", "")
        active_sigs  = res.get("active_signals", [])

        border = "#A6E3A1" if signal == "BUY" else ("#F38BA8" if signal == "SELL" else "#45475A")

        box = QGroupBox()
        box.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {border}; border-radius: 6px; "
            f"padding: 10px 10px 6px 10px; margin-bottom: 4px; }}"
        )
        lay = QVBoxLayout(box)
        lay.setSpacing(5)

        # ── Asset header row ──────────────────────────────────────────
        h1 = QHBoxLayout()
        lbl_asset = QLabel(f"<b>{asset}</b>")
        lbl_asset.setStyleSheet(f"color: {border}; font-size: 14px;")
        lbl_price = QLabel(f"Ціна: {price:.5f}")
        lbl_price.setStyleSheet("color: #A6ADC8; font-size: 12px;")
        lbl_market = QLabel(f"Ринок: <b>{market_state}</b> / {trend_str}")
        lbl_market.setStyleSheet("color: #CDD6F4; font-size: 12px;")
        h1.addWidget(lbl_asset)
        h1.addWidget(lbl_price)
        h1.addStretch()
        h1.addWidget(lbl_market)
        lay.addLayout(h1)

        # ── Divider ───────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("border: 1px solid #313244;")
        lay.addWidget(line)

        # ── Recommendation ───────────────────────────────────────────
        if signal:
            clr  = "#A6E3A1" if signal == "BUY" else "#F38BA8"
            icon = "📈" if signal == "BUY" else "📉"
            rec_text = f"{icon}  РЕКОМЕНДАЦІЯ: <span style='color:{clr}; font-size:15px;'><b>{signal}</b></span>"
        elif block_reason:
            rec_text = f"<span style='color:#F38BA8;'>{block_reason}</span>"
        else:
            rec_text = "<span style='color:#585B70;'>Немає сигналу (слабкий скор)</span>"

        lbl_rec = QLabel(rec_text)
        lbl_rec.setWordWrap(True)
        lbl_rec.setStyleSheet("font-size: 13px; padding: 2px 0;")
        lay.addWidget(lbl_rec)

        # ── BUY / SELL score bars ────────────────────────────────────
        buy_val  = probs.get("buy",  0.0)
        sell_val = probs.get("sell", 0.0)

        for direction, val, clr in [("📈 ВГОРУ (BUY)", buy_val, "#A6E3A1"),
                                    ("📉 ВНИЗ (SELL)", sell_val, "#F38BA8")]:
            row = QHBoxLayout()
            lbl_dir = QLabel(direction)
            lbl_dir.setStyleSheet("color: #CDD6F4; font-size: 11px;")
            lbl_dir.setFixedWidth(110)

            pb = QProgressBar()
            pb.setValue(int(val * 100))
            pb.setTextVisible(False)
            pb.setFixedHeight(12)
            is_active = (signal == "BUY" and "BUY" in direction) or \
                        (signal == "SELL" and "SELL" in direction)
            border_clr = clr if is_active else "#313244"
            pb.setStyleSheet(
                f"QProgressBar::chunk {{ background: {clr}; border-radius: 5px; }}"
                f"QProgressBar {{ border: 1px solid {border_clr}; background: #181825; border-radius: 5px; }}"
            )

            lbl_pct = QLabel(f"{val:.0%}   (raw: {raw_buy if 'BUY' in direction else raw_sell:.2f})")
            lbl_pct.setStyleSheet("color: #A6ADC8; font-size: 11px; min-width: 110px;")

            row.addWidget(lbl_dir)
            row.addWidget(pb, 1)
            row.addWidget(lbl_pct)
            lay.addLayout(row)

        # ── NN details grid ──────────────────────────────────────────
        nn_row = QHBoxLayout()
        # Пороги тут лише для кольорового підсвічування (косметика, на угоди не
        # впливають). RS/FB більше не мають жорсткого порогу рішення в логіці —
        # 0.3 це просто умовна позначка "помітний сигнал". MR_Тренд/MR_Вибух —
        # справжні бінарні класифікатори, тому 0.5 = реальна межа рішення мережі.
        nn_items = [
            ("🔵 NN Підтримка", nn_sup,  0.3, False),
            ("🔴 NN Опір",       nn_res,  0.3, True),
            ("📗 FB Бичачий",    nn_fb_b, 0.3, False),
            ("📕 FB Ведмежий",   nn_fb_be,0.3, True),
            ("📈 MR Тренд",      mr_trend, 0.5, True),   # > 0.5 = блок
            ("⚡ MR Вибух",      mr_exp,   0.5, True),   # > 0.5 = блок
        ]
        for name, val, thresh, higher_is_bad in nn_items:
            if higher_is_bad:
                color = "#F38BA8" if val > thresh else "#A6ADC8"
            else:
                color = "#A6E3A1" if val > thresh else "#A6ADC8"

            lbl_nn = QLabel(f"<span style='color:#6C7086; font-size:10px;'>{name}:</span>"
                            f"<span style='color:{color}; font-size:11px;'> {val:.3f}</span>")
            lbl_nn.setStyleSheet("padding: 0 4px;")
            nn_row.addWidget(lbl_nn)

        nn_row.addStretch()
        lay.addLayout(nn_row)

        # ── Active signals ───────────────────────────────────────────
        if active_sigs:
            sig_title = QLabel(f"Активні сигнали ({len(active_sigs)}):")
            sig_title.setStyleSheet("color: #A6ADC8; font-size: 10px; margin-top: 3px;")
            lay.addWidget(sig_title)

            sigs_text = "   ".join(active_sigs[:10])
            lbl_sigs = QLabel(sigs_text)
            lbl_sigs.setStyleSheet("color: #585B70; font-size: 10px;")
            lbl_sigs.setWordWrap(True)
            lay.addWidget(lbl_sigs)

        return box
