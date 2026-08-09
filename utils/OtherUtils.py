# ------------------------------
# Декоратор для обробки помилок
# ------------------------------

def _handle_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
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