import torch
import torch.nn as nn


#------------------------------
# Допоміжний клас-енкодер
#------------------------------

class _WindowEncoder(nn.Module):
    "Один енкодер для одного розміру контекстного вікна (Conv1d + LSTM -> embedding)"

    #------------------------------
    # Ініціалізація енкодера
    #------------------------------

    def __init__(self, num_features=5, hidden_size=32, embed_size=32):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels=num_features, out_channels=16, kernel_size=3, padding=1)
        self.relu = nn.ReLU()
        self.pool = nn.MaxPool1d(kernel_size=2)
        self.lstm = nn.LSTM(input_size=16, hidden_size=hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, embed_size)

    #------------------------------
    # Прямий прохід
    #------------------------------

    def forward(self, x):
        "Прямий прохід (batch, seq_len, features)"
        x = x.transpose(1, 2)
        x = self.pool(self.relu(self.conv1(x)))
        x = x.transpose(1, 2)
        _, (h_n, _) = self.lstm(x)
        return self.relu(self.fc(h_n[-1]))


#------------------------------
# Головний клас нейромережі RS
#------------------------------

class ArchitectureNN(nn.Module):
    "Мультивіконна мережа рівнів (RS, Фаза Б). Приймає 5 вікон різної довжини і комбінує ембединги в 4 виходи (h_res, h_sup, t_res, t_sup)."
    WINDOW_SIZES = [1000, 500, 200, 100, 50]

    def __init__(self, seq_len=1000, num_features=5, embed_size=32):
        # seq_len приймається лише для сумісності виклику ArchitectureNN(seq_len=...),
        # реальні розміри вікон фіксовані у WINDOW_SIZES.
        super(ArchitectureNN, self).__init__()

        self.encoders = nn.ModuleList([
            _WindowEncoder(num_features=num_features, embed_size=embed_size)
            for _ in self.WINDOW_SIZES
        ])

        combined = embed_size * len(self.WINDOW_SIZES)
        self.fc1 = nn.Linear(combined, 64)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(64, 4)
        self.sigmoid = nn.Sigmoid()

    def forward(self, windows):
        """windows: список з 5 тензорів (batch, window_len, features), у порядку WINDOW_SIZES."""
        embeds = [enc(w) for enc, w in zip(self.encoders, windows)]
        combined = torch.cat(embeds, dim=1)
        x = self.dropout(self.relu(self.fc1(combined)))
        return self.sigmoid(self.fc2(x))
