# model.py
import torch
import torch.nn as nn

class TrafficLSTM(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, output_dim=1, num_layers=1):
        super(TrafficLSTM, self).__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # x: (batch_size, seq_len, input_dim)
        out, _ = self.lstm(x)
        out = out[:, -1, :]  # take the last time step
        out = self.fc(out)
        return out
