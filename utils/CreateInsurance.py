import os
import json

RULES_JSON_CONTENT = """{
  "SMA": {
    "type": "trend",
    "role": "filter",
    "buy_conditions": [
      {
        "op": ">",
        "value": "close",
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "<",
        "value": "close",
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "MACD",
        "Engulfing"
      ],
      "moderate": [
        "ATR_14",
        "BOS",
        "Hammer"
      ],
      "avoid": [
        "EMA",
        "WMA"
      ]
    }
  },
  "EMA": {
    "type": "trend",
    "role": "filter",
    "buy_conditions": [
      {
        "op": ">",
        "value": "close",
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "<",
        "value": "close",
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "MACD",
        "Shooting_Star"
      ],
      "moderate": [
        "ATR_14",
        "CHOCH",
        "Evening_Star"
      ],
      "avoid": [
        "SMA",
        "WMA"
      ]
    }
  },
  "EMA_Cross": {
    "type": "trend",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "ADX",
        "Volume_Avg"
      ],
      "moderate": [
        "MACD",
        "ATR_14"
      ],
      "avoid": [
        "SMA_Cross",
        "Market_State_Linear"
      ]
    }
  },
  "SMA_Cross": {
    "type": "trend",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "ADX",
        "Volume_Avg"
      ],
      "moderate": [
        "MACD",
        "ATR_14"
      ],
      "avoid": [
        "EMA_Cross",
        "Market_State_Linear"
      ]
    }
  },
  "MACD": {
    "type": "oscillator",
    "role": "signal",
    "buy_conditions": [
      {
        "op": ">",
        "value": 0,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "<",
        "value": 0,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "EMA",
        "RSI_14",
        "Engulfing"
      ],
      "moderate": [
        "ADX",
        "ATR_14"
      ],
      "avoid": [
        "Stochastic",
        "CCI"
      ]
    }
  },
  "ADX": {
    "type": "trend_strength",
    "role": "filter",
    "buy_conditions": [
      {
        "op": ">",
        "value": 25,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": 25,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "EMA_Cross",
        "MACD",
        "BOS"
      ],
      "moderate": [
        "RSI_14",
        "Engulfing"
      ],
      "avoid": [
        "Market_State_Linear"
      ]
    }
  },
  "RSI_14": {
    "type": "oscillator",
    "role": "filter",
    "buy_conditions": [
      {
        "op": "<",
        "value": 30,
        "tolerance": 5
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": 70,
        "tolerance": 5
      }
    ],
    "symbiosis": {
      "strong": [
        "BOS",
        "Hammer",
        "NGRAM_ROAD"
      ],
      "moderate": [
        "EMA_20",
        "Market_State_Linear",
        "Engulfing"
      ],
      "avoid": [
        "CHOCH",
        "Shooting_Star"
      ]
    }
  },
  "Stochastic": {
    "type": "oscillator",
    "role": "filter",
    "buy_conditions": [
      {
        "op": "<",
        "value": 20,
        "tolerance": 2
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": 80,
        "tolerance": 2
      }
    ],
    "symbiosis": {
      "strong": [
        "EMA",
        "Morning_Star",
        "Evening_Star"
      ],
      "moderate": [
        "MACD",
        "Market_State_Linear"
      ],
      "avoid": [
        "RSI_14",
        "CCI"
      ]
    }
  },
  "CCI": {
    "type": "oscillator",
    "role": "filter",
    "buy_conditions": [
      {
        "op": "<",
        "value": -100,
        "tolerance": 10
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": 100,
        "tolerance": 10
      }
    ],
    "symbiosis": {
      "strong": [
        "SMA_Cross",
        "Hammer",
        "Shooting_Star"
      ],
      "moderate": [
        "ATR_14",
        "Volume_Avg"
      ],
      "avoid": [
        "RSI_14",
        "Stochastic"
      ]
    }
  },
  "WilliamsR": {
    "type": "oscillator",
    "role": "filter",
    "buy_conditions": [
      {
        "op": "<",
        "value": -80,
        "tolerance": 5
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": -20,
        "tolerance": 5
      }
    ],
    "symbiosis": {
      "strong": [
        "EMA",
        "Engulfing"
      ],
      "moderate": [
        "MACD",
        "ADX"
      ],
      "avoid": [
        "RSI_14",
        "Stochastic"
      ]
    }
  },
  "ATR": {
    "type": "volatility",
    "role": "filter",
    "buy_conditions": [
      {
        "op": ">",
        "value": 0,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": 0,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Bollinger_Upper",
        "Bollinger_Lower",
        "BOS"
      ],
      "moderate": [
        "MACD",
        "EMA_Cross"
      ],
      "avoid": []
    }
  },
  "Bollinger_Upper": {
    "type": "volatility_band",
    "role": "signal",
    "buy_conditions": [],
    "sell_conditions": [
      {
        "op": ">",
        "value": "close",
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "Shooting_Star",
        "Evening_Star"
      ],
      "moderate": [
        "ATR",
        "Volume_Avg"
      ],
      "avoid": [
        "Bollinger_Lower",
        "Keltner_Upper"
      ]
    }
  },
  "Bollinger_Lower": {
    "type": "volatility_band",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "<",
        "value": "close",
        "tolerance": 0
      }
    ],
    "sell_conditions": [],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "Hammer",
        "Morning_Star"
      ],
      "moderate": [
        "ATR",
        "Volume_Avg"
      ],
      "avoid": [
        "Bollinger_Upper",
        "Keltner_Lower"
      ]
    }
  },
  "Keltner_Upper": {
    "type": "volatility_band",
    "role": "signal",
    "buy_conditions": [],
    "sell_conditions": [
      {
        "op": ">",
        "value": "close",
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "Shooting_Star"
      ],
      "moderate": [
        "ATR",
        "MACD"
      ],
      "avoid": [
        "Bollinger_Upper"
      ]
    }
  },
  "Keltner_Lower": {
    "type": "volatility_band",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "<",
        "value": "close",
        "tolerance": 0
      }
    ],
    "sell_conditions": [],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "Hammer"
      ],
      "moderate": [
        "ATR",
        "MACD"
      ],
      "avoid": [
        "Bollinger_Lower"
      ]
    }
  },
  "Volume_Avg": {
    "type": "volume",
    "role": "filter",
    "buy_conditions": [
      {
        "op": ">",
        "value": "volume",
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": ">",
        "value": "volume",
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "BOS",
        "CHOCH",
        "Engulfing"
      ],
      "moderate": [
        "EMA_Cross",
        "MACD"
      ],
      "avoid": []
    }
  },
  "Market_State_Linear": {
    "type": "algorithm",
    "role": "filter",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Hammer",
        "Shooting_Star",
        "RSI_14"
      ],
      "moderate": [
        "MACD",
        "ATR"
      ],
      "avoid": [
        "EMA_Cross",
        "SMA_Cross"
      ]
    }
  },
  "Order_Blocks": {
    "type": "algorithm_smc",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "FVG",
        "CHOCH",
        "BOS"
      ],
      "moderate": [
        "RSI_14",
        "Volume_Avg"
      ],
      "avoid": [
        "MACD",
        "EMA_Cross"
      ]
    }
  },
  "WCE": {
    "type": "algorithm",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Market_State_Linear",
        "ATR"
      ],
      "moderate": [
        "RSI_14"
      ],
      "avoid": [
        "Order_Blocks"
      ]
    }
  },
  "BOS": {
    "type": "algorithm_smc",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "NGRAM_ROAD",
        "Market_State_Linear"
      ],
      "moderate": [
        "EMA",
        "ATR"
      ],
      "avoid": [
        "CHOCH"
      ]
    }
  },
  "CHOCH": {
    "type": "algorithm_smc",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Order_Blocks",
        "FVG",
        "Volume_Avg"
      ],
      "moderate": [
        "MACD",
        "ATR"
      ],
      "avoid": [
        "BOS",
        "RSI_14"
      ]
    }
  },
  "FVG": {
    "type": "algorithm_smc",
    "role": "filter",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Order_Blocks",
        "CHOCH",
        "Hammer"
      ],
      "moderate": [
        "BOS",
        "Volume_Avg"
      ],
      "avoid": [
        "SMA_Cross",
        "MACD"
      ]
    }
  },
  "NGRAM_ROAD": {
    "type": "algorithm_ai",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "BOS",
        "RSI_14",
        "Market_State_Linear"
      ],
      "moderate": [
        "ATR",
        "Volume_Avg"
      ],
      "avoid": [
        "WCE",
        "Order_Blocks"
      ]
    }
  },
  "Hammer": {
    "type": "pattern",
    "role": "signal",
    "direction": "buy_only",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "Bollinger_Lower",
        "FVG"
      ],
      "moderate": [
        "BOS",
        "Market_State_Linear"
      ],
      "avoid": [
        "Shooting_Star",
        "Evening_Star"
      ]
    }
  },
  "Inverted_Hammer": {
    "type": "pattern",
    "role": "signal",
    "direction": "buy_only",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "Keltner_Lower"
      ],
      "moderate": [
        "Market_State_Linear",
        "Volume_Avg"
      ],
      "avoid": [
        "Hanging_Man",
        "Shooting_Star"
      ]
    }
  },
  "Shooting_Star": {
    "type": "pattern",
    "role": "signal",
    "direction": "sell_only",
    "buy_conditions": [],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "Bollinger_Upper",
        "Order_Blocks"
      ],
      "moderate": [
        "MACD",
        "Market_State_Linear"
      ],
      "avoid": [
        "Hammer",
        "Morning_Star"
      ]
    }
  },
  "Engulfing": {
    "type": "pattern",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Volume_Avg",
        "MACD",
        "BOS"
      ],
      "moderate": [
        "RSI_14",
        "Market_State_Linear"
      ],
      "avoid": [
        "Doji"
      ]
    }
  },
  "Morning_Star": {
    "type": "pattern",
    "role": "signal",
    "direction": "buy_only",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "Bollinger_Lower"
      ],
      "moderate": [
        "Volume_Avg",
        "ATR"
      ],
      "avoid": [
        "Evening_Star",
        "Three_Black_Crows"
      ]
    }
  },
  "Evening_Star": {
    "type": "pattern",
    "role": "signal",
    "direction": "sell_only",
    "buy_conditions": [],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Stochastic",
        "Bollinger_Upper"
      ],
      "moderate": [
        "Volume_Avg",
        "ATR"
      ],
      "avoid": [
        "Morning_Star",
        "Three_White_Soldiers"
      ]
    }
  },
  "Hanging_Man": {
    "type": "pattern",
    "role": "signal",
    "direction": "sell_only",
    "buy_conditions": [],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "RSI_14",
        "Keltner_Upper"
      ],
      "moderate": [
        "Market_State_Linear",
        "Volume_Avg"
      ],
      "avoid": [
        "Inverted_Hammer",
        "Hammer"
      ]
    }
  },
  "Three_White_Soldiers": {
    "type": "pattern",
    "role": "signal",
    "direction": "buy_only",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [],
    "symbiosis": {
      "strong": [
        "ADX",
        "Volume_Avg",
        "Market_State_Linear"
      ],
      "moderate": [
        "BOS",
        "MACD"
      ],
      "avoid": [
        "Three_Black_Crows",
        "Evening_Star"
      ]
    }
  },
  "Three_Black_Crows": {
    "type": "pattern",
    "role": "signal",
    "direction": "sell_only",
    "buy_conditions": [],
    "sell_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "ADX",
        "Volume_Avg",
        "Market_State_Linear"
      ],
      "moderate": [
        "CHOCH",
        "MACD"
      ],
      "avoid": [
        "Three_White_Soldiers",
        "Morning_Star"
      ]
    }
  },
  "WCE_ANOMALY": {
    "type": "algorithm",
    "role": "signal",
    "buy_conditions": [
      {
        "op": "==",
        "value": 1,
        "tolerance": 0
      }
    ],
    "sell_conditions": [
      {
        "op": "==",
        "value": -1,
        "tolerance": 0
      }
    ],
    "symbiosis": {
      "strong": [
        "Market_State_Linear",
        "RSI_14"
      ],
      "moderate": [
        "Volume_Avg"
      ],
      "avoid": [
        "EMA_Cross"
      ]
    }
  }
}
"""

STRATEGY_META_JSON_CONTENT = """{
  "categories": [
    {
      "name": "Трендові Індикатори",
      "items": [
        {
          "id": "sma",
          "class": "Indicator",
          "name": "Simple Moving Average (SMA)",
          "description": "Проста ковзна середня. Колонка: SMA_{period}. Числове значення.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 500}
          ]
        },
        {
          "id": "ema",
          "class": "Indicator",
          "name": "Exponential Moving Average (EMA)",
          "description": "Експоненційна ковзна середня. Колонка: EMA_{period}. Числове значення.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 500}
          ]
        },
        {
          "id": "ema_cross",
          "class": "Indicator",
          "name": "EMA Cross (Перетин EMA)",
          "description": "Перетин двох EMA. Колонка: EMA_Cross_{fast}_{slow}. Повертає 1 (бичачий), -1 (ведмежий), 0.",
          "params": [
            {"name": "fast", "label": "Швидка", "type": "int", "default": 10, "min": 2, "max": 200},
            {"name": "slow", "label": "Повільна", "type": "int", "default": 50, "min": 5, "max": 500}
          ]
        },
        {
          "id": "sma_cross",
          "class": "Indicator",
          "name": "SMA Cross (Перетин SMA)",
          "description": "Перетин двох SMA. Колонка: SMA_Cross_{fast}_{slow}. Повертає 1, -1, 0.",
          "params": [
            {"name": "fast", "label": "Швидка", "type": "int", "default": 10, "min": 2, "max": 200},
            {"name": "slow", "label": "Повільна", "type": "int", "default": 50, "min": 5, "max": 500}
          ]
        },
        {
          "id": "macd",
          "class": "Indicator",
          "name": "MACD",
          "description": "Осцилятор конвергенції/дивергенції. Колонка: MACD_{fast}_{slow}_{signal}. Числове значення.",
          "params": [
            {"name": "fast", "label": "Швидка", "type": "int", "default": 12, "min": 2, "max": 100},
            {"name": "slow", "label": "Повільна", "type": "int", "default": 26, "min": 5, "max": 200},
            {"name": "signal", "label": "Сигнал", "type": "int", "default": 9, "min": 2, "max": 50}
          ]
        },
        {
          "id": "adx",
          "class": "Indicator",
          "name": "ADX (Сила Тренду)",
          "description": "Average Directional Index. Колонка: ADX_{period}. >25 = сильний тренд.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 14, "min": 2, "max": 100}
          ]
        }
      ]
    },
    {
      "name": "Осцилятори",
      "items": [
        {
          "id": "rsi",
          "class": "Indicator",
          "name": "RSI (Індекс відносної сили)",
          "description": "Relative Strength Index. Колонка: RSI_{period}. Числове значення 0-100. <30 = перепроданість, >70 = перекупленість.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 14, "min": 2, "max": 100}
          ]
        },
        {
          "id": "stochastic",
          "class": "Indicator",
          "name": "Stochastic",
          "description": "Стохастичний осцилятор. Колонка: Stochastic_K_{k}. Числове значення 0-100.",
          "params": [
            {"name": "k", "label": "K-Період", "type": "int", "default": 14, "min": 2, "max": 100},
            {"name": "d", "label": "D-Згладж.", "type": "int", "default": 3, "min": 1, "max": 20}
          ]
        },
        {
          "id": "cci",
          "class": "Indicator",
          "name": "CCI (Індекс товарного каналу)",
          "description": "Commodity Channel Index. Колонка: CCI_{period}. >100 = перекупленість, <-100 = перепроданість.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 200}
          ]
        },
        {
          "id": "williamsr",
          "class": "Indicator",
          "name": "Williams %R",
          "description": "Williams Percent Range. Колонка: WilliamsR_{period}. Числове значення -100..0.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 14, "min": 2, "max": 100}
          ]
        }
      ]
    },
    {
      "name": "Волатильність і Канали",
      "items": [
        {
          "id": "atr",
          "class": "Indicator",
          "name": "ATR (Середній Діапазон)",
          "description": "Average True Range. Колонка: ATR_{period}. Числове значення (розмір свічки).",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 14, "min": 2, "max": 100}
          ]
        },
        {
          "id": "bollinger_upper",
          "class": "Indicator",
          "name": "Bollinger Upper Band",
          "description": "Верхня лінія смуг Боллінджера. Колонка: Bollinger_Upper_{period}_{std}.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 200},
            {"name": "std", "label": "Ст. відх.", "type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.1}
          ]
        },
        {
          "id": "bollinger_lower",
          "class": "Indicator",
          "name": "Bollinger Lower Band",
          "description": "Нижня лінія смуг Боллінджера. Колонка: Bollinger_Lower_{period}_{std}.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 200},
            {"name": "std", "label": "Ст. відх.", "type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.1}
          ]
        },
        {
          "id": "keltner_upper",
          "class": "Indicator",
          "name": "Keltner Upper Channel",
          "description": "Верхня лінія каналу Келтнера. Колонка: Keltner_Upper_{period}.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 200}
          ]
        },
        {
          "id": "keltner_lower",
          "class": "Indicator",
          "name": "Keltner Lower Channel",
          "description": "Нижня лінія каналу Келтнера. Колонка: Keltner_Lower_{period}.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 200}
          ]
        },
        {
          "id": "volume_avg",
          "class": "Indicator",
          "name": "Volume Average (Ковзне Об'єму)",
          "description": "Ковзна середня обсягу. Колонка: Volume_Avg_{period}. Числове значення.",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 2, "max": 200}
          ]
        }
      ]
    },
    {
      "name": "Алгоритмічні (Smart Money)",
      "items": [
        {
          "id": "market_state_linear",
          "class": "Algorithm",
          "name": "Market State Linear (Стан Ринку)",
          "description": "Лінійна кластеризація стану ринку. Повертає: 1 (висхідний тренд), -1 (низхідний), 0 (флет), 3 (хаос/висока волатильність).",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 20, "min": 5, "max": 200}
          ]
        },
        {
          "id": "order_blocks",
          "class": "Algorithm",
          "name": "Order Blocks (Ордер-блоки)",
          "description": "Виявлення ордер-блоків Smart Money. Повертає: 1 (бичачий OB), -1 (ведмежий OB), 0 (немає).",
          "params": []
        },
        {
          "id": "wce",
          "class": "Algorithm",
          "name": "WCE (Wrap Candle Engine)",
          "description": "Власний алгоритм аналізу послідовностей. Повертає числовий сигнал (зазвичай 1, -1, або 0).",
          "params": [
            {"name": "period", "label": "Період", "type": "int", "default": 10, "min": 2, "max": 100}
          ]
        },
        {
          "id": "bos",
          "class": "Algorithm",
          "name": "BOS (Break of Structure)",
          "description": "Прорив структури ринку. Повертає True/False. Потребує розрахунку Market Structure.",
          "params": []
        },
        {
          "id": "choch",
          "class": "Algorithm",
          "name": "CHoCH (Change of Character)",
          "description": "Зміна характеру ринку. Повертає True/False. Потребує розрахунку Market Structure.",
          "params": []
        },
        {
          "id": "fvg",
          "class": "Algorithm",
          "name": "FVG (Fair Value Gap)",
          "description": "Незаповнений ціновий розрив. Колонка: FVG_Up / FVG_Down.",
          "params": []
        },
        {
          "id": "ngram_road",
          "class": "Algorithm",
          "name": "NGram Prediction (AI Прогноз)",
          "description": "AI-прогноз наступного руху через N-грами. Повертає: 1 (вгору), -1 (вниз), 0. Колонка: NGRAM_ROAD_{road}.",
          "params": [
            {"name": "road", "label": "Дорога (прогноз)", "type": "int", "default": 1, "min": 1, "max": 5}
          ]
        },
        {
          "id": "wce_anomaly",
          "class": "Algorithm",
          "name": "WCE Anomaly (Ефект гумки)",
          "description": "Контртрендовий вхід при зниженні аномальності WCE. Повертає: 1 (BUY), -1 (SELL), 0. Колонка: WCE_ANOMALY_{peak_threshold}_{norm_threshold}.",
          "params": [
            {"name": "peak_threshold", "label": "Пік Аномалії", "type": "int", "default": 6, "min": 3, "max": 12},
            {"name": "norm_threshold", "label": "Норма", "type": "int", "default": 3, "min": 0, "max": 5}
          ]
        }
      ]
    },
    {
      "name": "Свічкові Патерни",
      "items": [
        {
          "id": "hammer",
          "class": "Pattern",
          "name": "Hammer (Молот)",
          "description": "Бичачий розворотний патерн. Колонка: Hammer. Повертає 0 або 1.",
          "params": []
        },
        {
          "id": "inverted_hammer",
          "class": "Pattern",
          "name": "Inverted Hammer (Перевернутий Молот)",
          "description": "Бичачий розворотний патерн. Колонка: Inverted_Hammer. Повертає True/False.",
          "params": []
        },
        {
          "id": "shooting_star",
          "class": "Pattern",
          "name": "Shooting Star (Зоря, що падає)",
          "description": "Ведмежий розворотний патерн. Колонка: Shooting_Star. Повертає 0 або 1.",
          "params": []
        },
        {
          "id": "engulfing",
          "class": "Pattern",
          "name": "Engulfing (Поглинання)",
          "description": "Двосторонній розворотний патерн. Колонка: Engulfing. Повертає 1 (бичачий), -1 (ведмежий), 0.",
          "params": []
        },
        {
          "id": "morning_star",
          "class": "Pattern",
          "name": "Morning Star (Ранкова Зоря)",
          "description": "Бичачий розворот (3 свічки). Колонка: Morning_Star. Повертає 0 або 1.",
          "params": []
        },
        {
          "id": "evening_star",
          "class": "Pattern",
          "name": "Evening Star (Вечірня Зоря)",
          "description": "Ведмежий розворот (3 свічки). Колонка: Evening_Star. Повертає 0 або 1.",
          "params": []
        },
        {
          "id": "hanging_man",
          "class": "Pattern",
          "name": "Hanging Man (Повішений)",
          "description": "Ведмежий розворотний патерн. Колонка: Hanging_Man. Повертає 0 або 1.",
          "params": []
        },
        {
          "id": "three_white_soldiers",
          "class": "Pattern",
          "name": "Three White Soldiers (Три Солдати)",
          "description": "Сильний бичачий патерн (3 зростаючих свічки). Колонка: Three_White_Soldiers. Повертає 0 або 1.",
          "params": []
        },
        {
          "id": "three_black_crows",
          "class": "Pattern",
          "name": "Three Black Crows (Три Ворони)",
          "description": "Сильний ведмежий патерн (3 спадних свічки). Колонка: Three_Black_Crows. Повертає 0 або 1.",
          "params": []
        }
      ]
    }
  ]
}

"""

class Insurance:
    @staticmethod
    def ensure_files_exist(base_dir=None):
        if base_dir is None:
            from utils.PathManager import PathManager
            base_dir = PathManager.get_user_data_dir()
            
        config_dir = os.path.join(base_dir, 'data', 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        rules_path = os.path.join(config_dir, 'rules.json')
        meta_path = os.path.join(config_dir, 'strategy_meta.json')
        
        if not os.path.exists(rules_path):
            with open(rules_path, 'w', encoding='utf-8') as f:
                f.write(RULES_JSON_CONTENT)
            print("Insurance: Created missing rules.json")
            
        if not os.path.exists(meta_path):
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write(STRATEGY_META_JSON_CONTENT)
            print("Insurance: Created missing strategy_meta.json")
            
    @staticmethod
    def get_rules_content():
        return json.loads(RULES_JSON_CONTENT)
        
    @staticmethod
    def get_meta_content():
        return json.loads(STRATEGY_META_JSON_CONTENT)
