import os
import json

from PyQt6 import QtWidgets

#-----------------------------------
# Глобальні реєстри движка
#-----------------------------------

_ELEMENTS = {}   # id -> QWidget (побудовані елементи, доступ через get)
_HANDLERS = {}   # ім'я -> callable (обробники подій, вказані в JSON)
_BUILDERS = {}   # тип -> callable (кастомні білдери власних віджетів)
_STYLES = {}     # ім'я стилю -> опис (з styles.json)

# Ключі, які движок трактує особливо. Усе інше з вузла — це параметри
# віджета (застосовуються як Qt-сеттери) або події (ключі on_*).
_SPECIAL = {"id", "type", "children", "style", "layout", "$include"}

# Базова тека для файлів опису (виставляється при build)
_BASE_DIR = None

# Типи layout для дітей
_LAYOUTS = {
    "v": QtWidgets.QVBoxLayout,
    "h": QtWidgets.QHBoxLayout,
    "grid": QtWidgets.QGridLayout,
}


#-----------------------------------
# Декоратор обробки помилок побудови (у стилі utils.other_utils._handle_error):
# одна зламана нода не валить усе вікно — друкуємо id/type і йдемо далі
#-----------------------------------

def _safe_build(func):

    def wrapper(node, *args, **kwargs):
        try:
            return func(node, *args, **kwargs)
        except Exception as e:
            ident = (node or {}).get("id") or (node or {}).get("type") or "?"
            print(f"[engine] Помилка побудови елемента '{ident}': {e}")
            return None

    return wrapper


#-----------------------------------
# Реєстрація власного білдера типу (для нестандартних віджетів)
#-----------------------------------

def element(type_name):

    def deco(func):
        _BUILDERS[type_name] = func
        return func

    return deco


#-----------------------------------
# Реєстрація обробника події (для прив'язки, вказаної в JSON)
#-----------------------------------

def handler(name):

    def deco(func):
        _HANDLERS[name] = func
        return func

    return deco


#-----------------------------------
# Прив'язка обробника з коду (напр. метод містка): engine.bind("explorer.refresh", self.refresh)
#-----------------------------------

def bind(name, func):

    _HANDLERS[name] = func


#-----------------------------------
# Визначення/створення віджета за типом.
# Спочатку власні білдери, потім будь-який клас із PyQt6.QtWidgets за іменем.
#-----------------------------------

def _resolve_widget(type_name):

    if type_name in _BUILDERS:
        return _BUILDERS[type_name]()

    cls = getattr(QtWidgets, type_name, None)
    if cls is None:
        raise ValueError(f"Невідомий тип віджета: '{type_name}'")

    return cls()


#-----------------------------------
# Застосування довільного параметра вузла.
# on_<signal> -> connect до обробника; інакше foo_bar -> widget.setFooBar(value)
#-----------------------------------

def _apply_param(widget, key, value):

    if key.startswith("on_"):
        signal = getattr(widget, key[3:], None)
        cb = _HANDLERS.get(value)
        if signal is not None and cb is not None:
            signal.connect(cb)
        return

    setter = "set" + "".join(part.capitalize() for part in key.split("_"))
    method = getattr(widget, setter, None)
    if method is not None:
        method(value)


#-----------------------------------
# Перетворення опису стилю (з styles.json) у QSS-рядок
#-----------------------------------

def _style_to_qss(spec):

    props = []
    for key, val in spec.items():
        if key == "bg":        props.append(f"background-color: {val}")
        elif key == "fg":      props.append(f"color: {val}")
        elif key == "radius":  props.append(f"border-radius: {val}px")
        elif key == "padding": props.append("padding: " + " ".join(f"{p}px" for p in str(val).split()))
        elif key == "border":  props.append(f"border: 1px solid {val}")
        else:                  props.append(f"{key}: {val}")
    return "; ".join(props)


def _apply_style(widget, style_name):

    spec = _STYLES.get(style_name)
    if spec:
        widget.setStyleSheet(_style_to_qss(spec))


#-----------------------------------
# Читання JSON-файлу опису (відносно базової теки, розширення .json необов'язкове)
#-----------------------------------

def _load(name):

    path = os.path.join(_BASE_DIR, name)
    if not path.endswith(".json"):
        path += ".json"

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


#-----------------------------------
# Побудова одного вузла опису (рекурсивно з дітьми)
#-----------------------------------

@_safe_build
def _build_node(node):

    # підключення іншого файлу опису як піддерева
    if "$include" in node:
        return _build_node(_load(node["$include"]))

    widget = _resolve_widget(node["type"])

    node_id = node.get("id")
    if node_id:
        _ELEMENTS[node_id] = widget

    if "style" in node:
        _apply_style(widget, node["style"])

    for key, value in node.items():
        if key not in _SPECIAL:
            _apply_param(widget, key, value)

    children = node.get("children")
    if children:
        if isinstance(widget, QtWidgets.QTabWidget):
            # Спеціальна обробка для QTabWidget
            for child in children:
                child_widget = _build_node(child)
                if child_widget is not None:
                    tab_title = child.get("tab_title", "Tab")
                    widget.addTab(child_widget, tab_title)
        else:
            # Звичайна обробка (layout)
            layout_cls = _LAYOUTS.get(node.get("layout", "v"), QtWidgets.QVBoxLayout)
            layout = layout_cls()
            for child in children:
                child_widget = _build_node(child)
                if child_widget is not None:
                    layout.addWidget(child_widget)
            widget.setLayout(layout)

    return widget


#-----------------------------------
# Публічне API
#-----------------------------------

def load_styles(path):

    global _STYLES
    with open(path, "r", encoding="utf-8") as f:
        _STYLES = json.load(f)


def build(root_path, styles_path=None):
    """Побудувати дерево віджетів з кореневого файлу опису. Повертає кореневий QWidget."""

    global _BASE_DIR
    _BASE_DIR = os.path.dirname(os.path.abspath(root_path))

    if styles_path:
        load_styles(styles_path)

    with open(root_path, "r", encoding="utf-8") as f:
        root_node = json.load(f)

    return _build_node(root_node)


def get(element_id):
    """Повернути сирий Qt-віджет за його id (для прив'язки подій, додавання дітей тощо)."""

    return _ELEMENTS.get(element_id)


def reset():
    """Очистити реєстр елементів (напр. перед повною перебудовою UI)."""

    _ELEMENTS.clear()
