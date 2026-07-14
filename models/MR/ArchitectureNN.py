import torch
import torch.nn as nn

class ArchitectureNN(nn.Module):
    """
    Нейромережа для класифікації Ринкового Режиму (Market Regime).
    Вхід: Ковзне вікно з N свічок (OHLCV).
    Вихід: 3 значення від 0 до 1:
      1. Trend_Strength
      2. Flat_Quality
      3. Explosion_Risk
    """
    def __init__(self, seq_len=1000, num_features=5):
        super(ArchitectureNN, self).__init__()
        
        self.conv1 = nn.Conv1d(in_channels=num_features, out_channels=32, kernel_size=3, padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool1d(kernel_size=2)
        
        self.conv2 = nn.Conv1d(in_channels=32, out_channels=64, kernel_size=3, padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool1d(kernel_size=2)
        
        self.lstm = nn.LSTM(input_size=64, hidden_size=64, num_layers=2, batch_first=True, dropout=0.2)
        
        self.fc1 = nn.Linear(64, 32)
        self.relu3 = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        
        # 3 класи на виході замість 2
        self.fc2 = nn.Linear(32, 3)
        
        # Sigmoid для незалежних ймовірностей 
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = x.transpose(1, 2)
        x = self.conv1(x)
        x = self.relu1(x)
        x = self.pool1(x)
        
        x = self.conv2(x)
        x = self.relu2(x)
        x = self.pool2(x)
        
        x = x.transpose(1, 2)
        
        lstm_out, (h_n, c_n) = self.lstm(x)
        last_out = lstm_out[:, -1, :]
        
        x = self.fc1(last_out)
        x = self.relu3(x)
        x = self.dropout(x)
        x = self.fc2(x)
        
        out = self.sigmoid(x)
        return out
