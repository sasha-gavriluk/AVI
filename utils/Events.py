from typing import Callable
from utils.OtherUtils import _handle_error

#------------------------------
# Глобальна шина подій
#------------------------------

class EventBus:
    "Глобальна шина подій (EventBus) для комунікації між компонентами без їх прямої зв'язності (Publisher/Subscriber)"
    
    _instance = None
    
    #------------------------------
    # Ініціалізація синглтона
    #------------------------------

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance
        
    #------------------------------
    # Підписка на події
    #------------------------------

    @_handle_error
    def subscribe(self, event_type: str, callback: Callable):
        "Підписатися на певну подію"
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            
    @_handle_error
    def unsubscribe(self, event_type: str, callback: Callable):
        "Відписатися від події"
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                
    #------------------------------
    # Публікація подій
    #------------------------------

    @_handle_error
    def publish(self, event_type: str, *args, **kwargs):
        "Опублікувати подію (викликати всі колбеки підписників)"
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Помилка виконання EventBus колбеку для події {event_type}: {e}")

# Глобальний екземпляр
event_bus = EventBus()
