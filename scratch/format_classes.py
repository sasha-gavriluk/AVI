import os

file_path = "/home/sasha/My/Avi/Code/utils/algorithms/DataProcessing.py"
with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
current_class = ""

def get_method_name(line):
    return line.strip().split('(')[0].split('def ')[1]

def get_class_desc(cls):
    if cls == "PatternDetector": return "Клас для виявлення свічкових патернів"
    if cls == "AlgorithmProcessor": return "Клас для алгоритмічної обробки та розрахунку рівнів"
    if cls == "BacktestAlgorithmProcessor": return "Клас алгоритмічної обробки, адаптований для бектесту"
    if cls == "DataProcessingManager": return "Головний менеджер для оркестрації обробки даних"
    return "Клас обробки даних"

def get_method_desc(method):
    if method == "__init__": return "Ініціалізація"
    if method == "process_data": return "Головний метод обробки даних"
    if method.startswith("detect_"): return f"Виявлення {method.replace('detect_', '').replace('_', ' ')}"
    if method.startswith("find_"): return f"Пошук {method.replace('find_', '').replace('_', ' ')}"
    if method.startswith("calculate_"): return f"Розрахунок {method.replace('calculate_', '').replace('_', ' ')}"
    if method.startswith("cluster_"): return f"Кластеризація {method.replace('cluster_', '').replace('_', ' ')}"
    if method.startswith("combine_"): return f"Об'єднання {method.replace('combine_', '').replace('_', ' ')}"
    if method.startswith("is_"): return f"Перевірка {method.replace('is_', '').replace('_', ' ')}"
    return f"Метод {method}"

for i, line in enumerate(lines):
    if line.startswith("class "):
        current_class = line.strip().split('(')[0].split(':')[0].split('class ')[1]
        
        if current_class != "IndicatorProcessor":
            # Check if header already exists
            has_header = False
            for j in range(len(new_lines)-1, max(-1, len(new_lines)-5), -1):
                if "=====" in new_lines[j]:
                    has_header = True
                    break
                    
            if not has_header:
                new_lines.append("# ==================================\n")
                new_lines.append(f"# {get_class_desc(current_class)}\n")
                new_lines.append("# ==================================\n\n")
            
    if line.startswith("    def ") and current_class != "IndicatorProcessor":
        method_name = get_method_name(line)
        
        # Check if header already exists
        has_header = False
        for j in range(len(new_lines)-1, max(-1, len(new_lines)-5), -1):
            if "----" in new_lines[j]:
                has_header = True
                break
                
        if not has_header:
            new_lines.append("    # ----------------------------------\n")
            new_lines.append(f"    # {get_method_desc(method_name)}\n")
            new_lines.append("    # ----------------------------------\n\n")
            
    new_lines.append(line)
    
    # Add class docstring if missing
    if line.startswith("class ") and current_class != "IndicatorProcessor":
        if i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if not next_line.startswith('"""') and not next_line.startswith("'''"):
                new_lines.append(f'    """{get_class_desc(current_class)}"""\n')
            
    # Add method docstring if missing
    if line.startswith("    def ") and current_class != "IndicatorProcessor":
        if i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if not next_line.startswith('"""') and not next_line.startswith("'''"):
                new_lines.append(f'        """{get_method_desc(method_name)}"""\n')

with open(file_path, 'w') as f:
    f.writelines(new_lines)
