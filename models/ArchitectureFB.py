import torch
import torch.nn as nn

class ArchitectureNN(nn.Module):
    """
    Нейромережа для класифікації Хибних Пробоїв (False Breakout).
    Вхід: Ковзне вікно з N свічок (OHLCV).
    Вихід: 2 значення від 0 до 1 (FB_Bullish, FB_Bearish).
    """
    def __init__(self, seq_len=1000, num_features=5):
        super(ArchitectureNN, self).__init__()
        
        # CNN для витягування мікропатернів (тіні, різкі пробої)
        self.conv1 = nn.Conv1d(in_channels=num_features, out_channels=32, kernel_size=3, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2)
        
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2)
        
        # LSTM для аналізу тренду та контексту збору ліквідності
        self.lstm = nn.LSTM(input_size=64, hidden_size=64, num_layers=2, batch_first=True, dropout=0.2)
        
        # Повнозв'язна мережа для прийняття фінального рішення
        self.fc1 = nn.Linear(64, 32)
        self.relu3 = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(32, 2)
        
        # Використовуємо Sigmoid, бо нам потрібна ймовірність від 0 до 1 для двох незалежних класів
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # x shape: (batch, seq_len, num_features)
        x = x.transpose(1, 2) # (batch, num_features, seq_len) для Conv1d
        
        x = self.conv1(x)
        x = self.relu1(x)
        x = self.pool1(x)
        
        x = self.conv2(x)
        x = self.relu2(x)
        x = self.pool2(x)
        
        x = x.transpose(1, 2) # (batch, new_seq_len, channels) для LSTM
        
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # Беремо останній вихід LSTM (останню свічку)
        last_out = lstm_out[:, -1, :]
        
        x = self.fc1(last_out)
        x = self.relu3(x)
        x = self.dropout(x)
        x = self.fc2(x)
        
        out = self.sigmoid(x)
        return out
