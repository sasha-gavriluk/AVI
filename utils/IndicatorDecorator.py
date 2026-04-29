import types
import pandas as pd

from utils.algorithms.WrapCandleEngine import WCE
from utils.other_utils import _handle_error

#-----------------------------------
# Клас декоратор для обчислення індикаторів та WCE
#-----------------------------------

class IndicatorDecorator:
    def __init__(self, func):
        self.func = func

    #--------------------------------
    # Метод для підтримки виклику декорованої функції як методу клас
    #--------------------------------

    def __get__(self, instance, owner):

        if instance is None:
            return self
        
        return types.MethodType(self, instance)
    
    #--------------------------------
    # Виклик декорованої функції та обробка результату
    #--------------------------------
    
    def __call__(self, *args, **kwargs):

        instasnce = args[0]
        output = self.func(*args, **kwargs)

        if output is not None:
            result, table_name = output
            df = self._transform_WCE(instasnce, result, table_name)

            return df, table_name
        
        return output
    
    #--------------------------------
    # Метод для обчислення WCE та додавання його до DataFrame
    #--------------------------------
    
    @_handle_error
    def _transform_WCE(self, instance, raw_data, table_name):
        """Метод для обчислення WCE та додавання його до DataFrame"""

        period = 20
        df_copy = raw_data.copy()
        period_wce_for_calc = instance.db_manager.get_data_by_number_range(table_name, period)

        if period_wce_for_calc is None:
            period_wce_for_calc = pd.DataFrame()
        
        df = pd.concat([period_wce_for_calc, df_copy], ignore_index=False)

        wce = WCE(df, period=period)
        wce_sequence = wce.get_combined_sequence_v2()

        new_tokens = wce_sequence[-len(df_copy):]
        df_copy['WCE'] = new_tokens

        return df_copy



        