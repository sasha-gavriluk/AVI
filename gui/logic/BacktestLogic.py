import os
import json
import traceback
import sys
import random
import time
import shutil
from io import StringIO
from PyQt6.QtCore import QThread, pyqtSignal
from utils.DataBaseManager import DataBaseManager
from utils.algorithms.backtesting.TradingCopilot import TradingCopilot

#==================================
# BacktestLogic
#==================================
class BacktestLogic:
    # ----------------------------------
    # __init__, ініціалізація логіки бектесту
    # ----------------------------------
    # Параметри:
    # copilot_logic: екземпляр CopilotLogic
    def __init__(self, copilot_logic):
        self.copilot = copilot_logic.trading_copilot
        self.last_run_context = {}
        from utils.PathManager import PathManager
        self.meta_config_path = PathManager.get_strategy_meta_path()
        self.meta_data = self._load_meta_data()

    # ----------------------------------
    # _load_meta_data, зчитування конфігу індикаторів
    # ----------------------------------
    # Параметри: немає
    def _load_meta_data(self):
        if not os.path.exists(self.meta_config_path):
            print(f"Попередження: Файл конфігурації {self.meta_config_path} не знайдено.")
            return {"categories": []}
        try:
            with open(self.meta_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Помилка зчитування конфігу: {e}")
            return {"categories": []}

    # ----------------------------------
    # get_tables, отримання таблиць з БД
    # ----------------------------------
    # Параметри: немає
    def get_tables(self):
        tables_list = []
        try:
            dbm = DataBaseManager(use_default=True)
            tables = dbm.get_all_tables()
            dbm.disconnect()
            for t in tables:
                t_lower = t.lower()
                if "backtest" not in t_lower and "auto_learn" not in t_lower and not t.startswith("sqlite_"):
                    tables_list.append(t)
        except Exception as e:
            pass
        return tables_list


class StringCapture:
    def __init__(self, signal):
        self.signal = signal
    def write(self, text):
        stripped = text.strip()
        if stripped:
            self.signal.emit(stripped)
    def flush(self):
        pass


class BacktestWorker(QThread):
    log_message = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    finished_error = pyqtSignal(str)
    
    def __init__(self, code: str, db_path: str, table_name: str, result_table: str, copilot=None, parent=None):
        super().__init__(parent)
        self.code = code
        self.db_path = db_path
        self.table_name = table_name
        self.result_table = result_table
        self.copilot = copilot
        self.prediction_context = {}
    
    def run(self):
        try:
            from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
            from utils.algorithms.backtesting.MarketRunner import MarketRunner
            db_name = os.path.basename(self.db_path)
            
            local_ns = {
                "Indicator": Indicator,
                "Pattern": Pattern,
                "Algorithm": Algorithm,
                "Strategy": Strategy,
            }
            
            if self.copilot:
                self.log_message.emit("<b>🧠 Copilot аналізує стратегію...</b>")
                report = self.copilot.analyze(self.code)
                tf = self.table_name.split("_")[-1] if "_" in self.table_name else "1h"
                indicators_used = [details['arg'] for var, details in report.get("variables", {}).items() if details.get('arg')]
                prediction = self.copilot.predict_success_chance(self.table_name, tf, indicators_used)
                
                if prediction.get("status") == "exact_match":
                    msg = f"Точний збіг (WR: {prediction.get('win_rate', 0):.1f}%, PF: {prediction.get('profit_factor', 0):.2f})"
                elif prediction.get("status") == "similar_match":
                    msg = "Аналіз на основі досвіду"
                else:
                    msg = prediction.get("message", "Невідомо")
                    
                self.log_message.emit(f"<b>📈 Прогноз AI:</b> <span style='color: #89B4FA'>{msg}</span>")
                if prediction.get("summary"):
                    self.log_message.emit(f"<pre style='color: #A6ADC8; font-size: 11px;'>{prediction.get('summary')}</pre>")
                
                self.log_message.emit("<b>🔄 Запуск бектесту...</b>")
                
                self.prediction_context = {
                    "indicators_used": indicators_used,
                    "prediction": prediction,
                    "asset": self.table_name,
                    "logic_snapshot": report.get("logic_snapshot", {})
                }
            
            self.log_message.emit("Виконую код стратегії...")
            exec(self.code, local_ns)
            
            strategy = local_ns.get("strategy")
            if strategy is None:
                self.finished_error.emit("Об'єкт 'strategy' не було створено після exec().\nПеревірте рядок: strategy = Strategy(...)")
                return
            
            self.log_message.emit(f"Стратегію створено. Запускаю MarketRunner...")
            self.log_message.emit(f"Таблиця з даними: '{self.table_name}'")
            
            runner = MarketRunner(
                strategy=strategy,
                db_path=db_name,
                db_table_path=self.table_name,
            )
            
            old_stdout = sys.stdout
            sys.stdout = StringCapture(self.log_message)
            try:
                trades_df = runner.run(self.result_table)
                total_trades = len(trades_df) if trades_df is not None else 0
                if total_trades > 0:
                    winning_trades = len(trades_df[trades_df['Profit'] > 0])
                    win_rate = (winning_trades / total_trades) * 100.0
                    gross_profit = trades_df[trades_df['Profit'] > 0]['Profit'].sum()
                    gross_loss = abs(trades_df[trades_df['Profit'] < 0]['Profit'].sum())
                    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
                    total_profit = trades_df['Profit'].sum()
                    
                    self.log_message.emit(f"<br><span style='color: #32d74b; font-weight: bold;'>📊 ПІДСУМОК БЕКТЕСТУ:</span>")
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Всього угод: <b>{total_trades}</b></span>")
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Успішних: <b>{winning_trades} ({win_rate:.1f}%)</b></span>")
                    profit_color = "#32d74b" if total_profit >= 0 else "#ff453a"
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Чистий прибуток: <b style='color: {profit_color};'>{total_profit:.2f}</b></span>")
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Profit Factor: <b>{profit_factor:.2f}</b></span><br>")
                else:
                    self.log_message.emit(f"<br><span style='color: #ff9f0a; font-weight: bold;'>📊 ПІДСУМОК БЕКТЕСТУ:</span> <span style='color: #e5e5ea;'>Угод не знайдено.</span><br>")
            finally:
                sys.stdout = old_stdout
            
            self.finished_ok.emit(self.result_table)
        except Exception as e:
            self.finished_error.emit(traceback.format_exc())


class AutoLearnWorker(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    finished = pyqtSignal()
    
    def __init__(self, db_path, table_name, meta_data, total_runs=1000, direction_mode="MIXED", parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.table_name = table_name
        self.meta_data = meta_data
        self.total_runs = total_runs
        self.direction_mode = direction_mode
        self.is_running = True
        
    def run(self):
        try:
            from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
            from utils.algorithms.backtesting.MarketRunner import MarketRunner
            
            copilot = TradingCopilot(db_path=self.db_path)
            current_run_results = []
            db_name = os.path.basename(self.db_path)
            
            all_items = []
            for cat in self.meta_data.get("categories", []):
                all_items.extend(cat.get("items", []))
                
            if not all_items:
                self.log_message.emit("Помилка: Немає доступних індикаторів.")
                return
                
            total_runs = self.total_runs
            for i in range(total_runs):
                if not self.is_running: break
                    
                self.log_message.emit(f"<br><b>--- Генерація стратегії {i+1}/{total_runs} ---</b>")
                
                from utils.algorithms.backtesting.StrategyGenerator import StrategyGenerator
                generator = StrategyGenerator(copilot=copilot)
                
                direction = random.choice(["BUY", "SELL"]) if self.direction_mode == "MIXED" else self.direction_mode
                code_str = generator.generate(direction=direction)
                
                if code_str.startswith("# Помилка"):
                    self.log_message.emit(f"Пропуск: {code_str}")
                    continue
                    
                local_ns = {
                    "Indicator": Indicator, "Pattern": Pattern,
                    "Algorithm": Algorithm, "Strategy": Strategy,
                }
                
                try:
                    exec(code_str, local_ns)
                    strategy = local_ns.get("strategy")
                except Exception as e:
                    self.log_message.emit(f"Помилка генерації коду: {e}")
                    continue
                    
                report = copilot.analyze(code_str)
                indicators_used = [details['arg'] for var, details in report.get("variables", {}).items() if details.get('arg')]
                logic_snapshot = report.get("logic_snapshot", {})
                
                test_name = f"auto_learn_{int(time.time())}_{i}"
                from utils.PathManager import PathManager
                save_dir = os.path.join(PathManager.get_strategies_dir(), 'auto_learn')
                os.makedirs(save_dir, exist_ok=True)
                file_path = os.path.join(save_dir, f"{test_name}.py")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code_str)
                
                runner = MarketRunner(strategy=strategy, db_path=db_name, db_table_path=self.table_name)
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                
                try:
                    trades_df = runner.run(test_name)
                    sys.stdout = old_stdout
                    
                    total_trades = len(trades_df) if trades_df is not None else 0
                    if total_trades > 0:
                        winning_trades = len(trades_df[trades_df['Profit'] > 0])
                        win_rate = (winning_trades / total_trades) * 100.0
                        gross_profit = trades_df[trades_df['Profit'] > 0]['Profit'].sum()
                        gross_loss = abs(trades_df[trades_df['Profit'] < 0]['Profit'].sum())
                        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
                    else:
                        win_rate, profit_factor = 0.0, 0.0
                        
                    perf = {"win_rate": win_rate, "profit_factor": profit_factor, "total_trades": total_trades}
                    tf = self.table_name.split("_")[-1] if "_" in self.table_name else "1h"
                    copilot.record_backtest_result(
                        context={"asset": self.table_name, "timeframe": tf},
                        indicators=indicators_used, performance=perf,
                        note=f"Авто навчання {i+1}/{total_runs} [{direction}]", logic_snapshot=logic_snapshot
                    )
                    
                    self.log_message.emit(f"✅ Успіх. Угод: {total_trades}, PF: {profit_factor:.2f}, WR: {win_rate:.1f}%")
                    current_run_results.append({
                        "name": test_name, "path": file_path, "profit_factor": profit_factor,
                        "win_rate": win_rate, "total_trades": total_trades
                    })
                except Exception as e:
                    sys.stdout = old_stdout
                    self.log_message.emit(f"❌ Помилка: {str(e)[:100]}")
                    
                self.progress_update.emit(i+1, total_runs)
                
            if current_run_results:
                self.log_message.emit("<b>🔄 Аналіз та збереження Топ-5 стратегій...</b>")
                from utils.PathManager import PathManager
                top5_dir = os.path.join(PathManager.get_strategies_dir(), 'top5')
                os.makedirs(top5_dir, exist_ok=True)
                metadata_file = os.path.join(top5_dir, 'top5_metadata.json')
                
                global_top5 = []
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            global_top5 = json.load(f)
                    except: pass
                        
                import math
                def goldilocks_score(x):
                    pf = x.get('profit_factor', 0)
                    wr = x.get('win_rate', 0)
                    trades = x.get('total_trades', 0)
                    if trades < 10 or pf < 1.0: return 0
                    return pf * (wr / 100.0) * math.log10(trades)
                    
                global_top5.extend(current_run_results)
                global_top5 = [x for x in global_top5 if x.get('total_trades', 0) >= 10 and x.get('profit_factor', 0) >= 1.0]
                global_top5.sort(key=goldilocks_score, reverse=True)
                global_top5 = global_top5[:5]
                
                valid_basenames = []
                for strat in global_top5:
                    src_path = strat.get("path")
                    if src_path and os.path.exists(src_path):
                        base_name = os.path.basename(src_path)
                        dst_path = os.path.join(top5_dir, base_name)
                        valid_basenames.append(base_name)
                        if src_path != dst_path:
                            try:
                                shutil.copy2(src_path, dst_path)
                                strat["path"] = dst_path
                            except Exception as e:
                                self.log_message.emit(f"❌ Помилка копіювання топу: {e}")
                                
                for f_name in os.listdir(top5_dir):
                    if f_name.endswith('.py') and f_name not in valid_basenames:
                        try: os.remove(os.path.join(top5_dir, f_name))
                        except: pass
                                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(global_top5, f, indent=4, ensure_ascii=False)
                    
                if global_top5:
                    self.log_message.emit(f"🏆 Топ-5 оновлено: найвищий Profit Factor {global_top5[0]['profit_factor']:.2f} (Угод: {global_top5[0]['total_trades']})")
                else:
                    self.log_message.emit("ℹ️ Жодна стратегія не пройшла фільтр Топ-5 (потрібно PF > 1.0 та Угод >= 10)")
                
                from utils.PathManager import PathManager
                auto_learn_dir = os.path.join(PathManager.get_strategies_dir(), 'auto_learn')
                if os.path.exists(auto_learn_dir):
                    try:
                        shutil.rmtree(auto_learn_dir)
                        self.log_message.emit("🧹 Папку auto_learn очищено від непотрібних скриптів.")
                    except Exception as e:
                        self.log_message.emit(f"❌ Помилка видалення auto_learn: {e}")
            
            self.finished.emit()
        except Exception as e:
            self.log_message.emit(f"❌ Фатальна помилка: {traceback.format_exc()}")
            self.finished.emit()

    def stop(self):
        self.is_running = False


class WfvWorker(QThread):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()
    
    def __init__(self, code: str, db_path: str, table_name: str, parent=None):
        super().__init__(parent)
        self.code = code
        self.db_path = db_path
        self.table_name = table_name
        
    def run(self):
        try:
            from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
            from core.services.backtest_service import BacktestService
            
            local_ns = {
                "Indicator": Indicator, "Pattern": Pattern,
                "Algorithm": Algorithm, "Strategy": Strategy,
            }
            exec(self.code, local_ns)
            strategy = local_ns.get("strategy")
            
            service = BacktestService(self.db_path)
            results = service.run_wfv(strategy, self.table_name, num_windows=5, train_ratio=0.7)
            
            html = ["<div style='font-family: monospace; font-size: 13px;'>"]
            html.append("<table style='width: 100%; text-align: left; border-collapse: collapse;'>")
            html.append("<tr style='border-bottom: 1px solid #444;'><th>Вікно</th><th>Train PF</th><th>Test PF</th><th>Test WR</th><th>Robust?</th></tr>")
            
            total_robust = 0
            for r in results:
                window = r['window']
                train_pf = r['train_pf']
                test_pf = r['test_pf']
                test_wr = r['test_wr']
                robust = r['is_robust']
                
                if robust:
                    total_robust += 1
                    rob_str = "<span style='color:#32d74b'>✅ Так</span>"
                else:
                    rob_str = "<span style='color:#ff453a'>❌ Ні</span>"
                    
                html.append(f"<tr style='border-bottom: 1px solid #333;'>")
                html.append(f"<td>{window}</td><td>{train_pf:.2f}</td><td>{test_pf:.2f}</td><td>{test_wr:.1f}%</td><td>{rob_str}</td>")
                html.append(f"</tr>")
                
            html.append("</table>")
            robustness_pct = (total_robust / len(results)) * 100 if results else 0
            color = "#32d74b" if robustness_pct >= 60 else "#ff453a"
            html.append(f"<br><span style='font-weight:bold; color:{color}'>Надійність: {robustness_pct:.1f}% ({total_robust}/{len(results)} вікон)</span>")
            html.append("</div><br>")
            
            self.log_message.emit("".join(html))
        except Exception as e:
            self.log_message.emit(f"<div style='color: #ff453a'>Помилка WFV: {traceback.format_exc()}</div>")
        finally:
            self.finished.emit()
