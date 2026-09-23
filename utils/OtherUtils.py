# ------------------------------
# Декоратор для обробки помилок
# ------------------------------

import inspect
import functools

def _handle_error(func):
    try:
        sig = inspect.signature(func)
    except ValueError:
        sig = None

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if sig is not None:
            params = list(sig.parameters.values())
            has_var_pos = any(p.kind == p.VAR_POSITIONAL for p in params)
            has_var_kw = any(p.kind == p.VAR_KEYWORD for p in params)
            
            allowed_pos = len([p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
            
            if not has_var_pos:
                args_to_pass = args[:allowed_pos]
            else:
                args_to_pass = args
                
            if not has_var_kw:
                allowed_kw = {p.name for p in params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}
                kwargs_to_pass = {k: v for k, v in kwargs.items() if k in allowed_kw}
            else:
                kwargs_to_pass = kwargs
        else:
            args_to_pass = args
            kwargs_to_pass = kwargs

        try:
            return func(*args_to_pass, **kwargs_to_pass)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return None
    return wrapper

#-----------------------------------
# Декоратор для запису даних в базу даних
#-----------------------------------

def _save_to_db(func):
    def wrapper(*args, **kwargs):
        instance = args[0]
        output = func(*args, **kwargs)

        if output is not None:
            result, table_name = output
            instance.db_manager.insert_data_from_pandas_auto(table_name=table_name, df=result)

        return output
    return wrapper